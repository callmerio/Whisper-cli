#!/usr/bin/env python3
"""
会话模式管理器
管理"一口气"模式和"逐步上屏"模式，协调各个组件的工作
"""

import time
import threading
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# 导入项目组件
from voice_activity_detector import VoiceActivityDetector, VoiceSegment, VoiceActivityState
from segment_processor import SegmentProcessor, ProcessedSegment, SegmentStatus
from text_input_manager import TextInputManager, InputMethod, InputRequest, InputResult
from audio_recorder import AudioRecorder
from audio_retry_manager import audio_retry_manager
from notification_utils import notification_manager
from timer_utils import Timer
import config


class SessionMode(Enum):
    """会话模式"""
    BATCH = "一口气模式"        # 完整录音后统一处理
    REALTIME = "逐步上屏模式"   # 实时分段处理并输出


class SessionState(Enum):
    """会话状态"""
    IDLE = "空闲"
    RECORDING = "录音中"
    PROCESSING = "处理中"
    COMPLETED = "完成"


@dataclass
class SessionConfig:
    """会话配置"""
    mode: SessionMode = SessionMode.BATCH
    silence_duration: float = 4.0           # 静音检测时长（秒）
    min_segment_duration: float = 1.0       # 最小分段时长（秒）
    volume_threshold: float = 0.01          # 音量阈值
    auto_output_enabled: bool = getattr(config, 'SEGMENT_ENABLE_AUTO_OUTPUT', True)  # 自动输出到光标位置
    output_method: InputMethod = InputMethod.DIRECT_TYPE  # 输出方法
    clipboard_backup: bool = getattr(config, 'DEFAULT_CLIPBOARD_BACKUP', True)       # 剪贴板备份
    enable_correction: bool = getattr(config, 'SEGMENT_ENABLE_CORRECTION', True)     # 启用纠错
    enable_dictionary: bool = getattr(config, 'SEGMENT_ENABLE_DICTIONARY', True)     # 启用词典


class SessionModeManager:
    """会话模式管理器"""
    
    def __init__(self):
        """初始化会话模式管理器"""
        # 组件初始化
        self.audio_recorder = AudioRecorder()
        self.vad = VoiceActivityDetector()
        self.segment_processor = SegmentProcessor()
        self.text_input_manager = TextInputManager()
        self.retry_manager = audio_retry_manager
        self.timer = Timer()
        self._last_batch_processing_info: Optional[Dict[str, Any]] = None
        self._current_batch_task_id: Optional[str] = None
        
        # 配置和状态
        self.config = SessionConfig()
        self.current_state = SessionState.IDLE
        self.state_lock = threading.Lock()
        
        # 会话数据
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self.session_audio_buffer = []
        self.session_segments: List[ProcessedSegment] = []
        
        # 实时模式的状态
        self.realtime_active = False
        self.audio_feed_thread: Optional[threading.Thread] = None
        
        # 回调函数
        self.on_session_start: Optional[Callable[[SessionMode], None]] = None
        self.on_session_complete: Optional[Callable[[List[ProcessedSegment]], None]] = None
        self.on_realtime_output: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # 设置组件回调
        self._setup_component_callbacks()

        # 确保重试管理器处于运行状态，支持批量模式异步转录
        try:
            self.retry_manager.start()
        except Exception as e:
            if config.DEBUG_MODE:
                print(f"⚠️ 重试管理器启动异常: {e}")
        
        print(f"🎛️ 会话模式管理器初始化完成")
        print(f"   默认模式: {self.config.mode.value}")
        print(f"   静音检测: {self.config.silence_duration}s")
        print(f"   自动输出: {'✅' if self.config.auto_output_enabled else '❌'}")
    
    def _setup_component_callbacks(self):
        """设置组件回调函数"""
        # VAD 回调
        self.vad.set_callbacks(
            on_segment_complete=self._on_vad_segment_complete,
            on_voice_start=self._on_voice_start,
            on_voice_stop=self._on_voice_stop,
            on_state_change=self._on_vad_state_change
        )
        
        # 分段处理器回调
        self.segment_processor.set_callbacks(
            on_segment_complete=self._on_segment_complete,
            on_segment_output=self._on_segment_output,
            on_segment_error=self._on_segment_error,
            on_session_complete=self._on_session_complete
        )
        
        # 重试管理器回调（用于一口气模式）
        self.retry_manager.set_callbacks(
            transcription_callback=self._batch_transcription_callback,
            success_callback=self._batch_success_callback,
            failure_callback=self._batch_failure_callback
        )
    
    def set_callbacks(self,
                     on_session_start: Optional[Callable[[SessionMode], None]] = None,
                     on_session_complete: Optional[Callable[[List[ProcessedSegment]], None]] = None,
                     on_realtime_output: Optional[Callable[[str], None]] = None,
                     on_error: Optional[Callable[[str], None]] = None):
        """设置回调函数"""
        self.on_session_start = on_session_start
        self.on_session_complete = on_session_complete
        self.on_realtime_output = on_realtime_output
        self.on_error = on_error
    
    def update_config(self, **kwargs):
        """更新会话配置"""
        updated = False
        
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                updated = True
                print(f"🔧 更新配置: {key} = {value}")
        
        if updated:
            self._apply_config_changes()
    
    def _apply_config_changes(self):
        """应用配置变更"""
        # 更新 VAD 配置
        self.vad.update_config(
            silence_duration=self.config.silence_duration,
            volume_threshold=self.config.volume_threshold,
            min_segment_duration=self.config.min_segment_duration
        )
        
        # 更新分段处理器配置
        self.segment_processor.enable_correction = self.config.enable_correction
        self.segment_processor.enable_dictionary = self.config.enable_dictionary
        self.segment_processor.enable_auto_output = self.config.auto_output_enabled
        self.segment_processor.output_method = self.config.output_method
        
        # 更新文本输入管理器
        self.text_input_manager.set_default_method(self.config.output_method)
    
    def start_session(self, mode: Optional[SessionMode] = None) -> bool:
        """开始新会话"""
        if self.current_state != SessionState.IDLE:
            print(f"⚠️ 无法开始会话，当前状态: {self.current_state.value}")
            return False
        
        # 更新模式
        if mode:
            self.config.mode = mode
        
        with self.state_lock:
            self.current_state = SessionState.RECORDING
            self.current_session_id = f"session_{int(time.time() * 1000)}"
            self.session_start_time = time.time()
            self.session_audio_buffer = []
            self.session_segments = []
        
        print(f"🎤 开始{self.config.mode.value}: {self.current_session_id}")
        
        # 根据模式启动相应组件
        success = False
        if self.config.mode == SessionMode.REALTIME:
            success = self._start_realtime_session()
        else:
            success = self._start_batch_session()
        
        if success:
            # 调用开始回调
            if self.on_session_start:
                try:
                    self.on_session_start(self.config.mode)
                except Exception as e:
                    if config.DEBUG_MODE:
                        print(f"⚠️ 会话开始回调异常: {e}")
        else:
            with self.state_lock:
                self.current_state = SessionState.IDLE
        
        return success
    
    def _start_realtime_session(self) -> bool:
        """启动实时模式会话"""
        try:
            print(f"🔄 启动实时模式...")
            
            # 首先启动 SegmentProcessor
            if not self.segment_processor.start():
                print("❌ SegmentProcessor启动失败")
                return False
            
            # 启动VAD
            if not self.vad.start():
                print("❌ VAD启动失败")
                self.segment_processor.stop()
                return False
            
            # 启动音频录制
            if not self.audio_recorder.start_recording():
                print("❌ 音频录制启动失败")
                self.vad.stop()
                self.segment_processor.stop()
                return False
            
            # 启动音频数据馈送线程
            self.realtime_active = True
            self.audio_feed_thread = threading.Thread(target=self._realtime_audio_feed, daemon=True)
            self.audio_feed_thread.start()
            
            print(f"✅ 实时模式启动成功")
            print(f"   SegmentProcessor: {'✅' if self.segment_processor.running else '❌'}")
            print(f"   VAD运行状态: {'✅' if self.vad.running else '❌'}")
            print(f"   静音检测: {self.config.silence_duration}s")
            print(f"   自动输出: {'✅' if self.config.auto_output_enabled else '❌'}")
            
            return True
            
        except Exception as e:
            print(f"❌ 实时模式启动失败: {e}")
            return False
    
    def _start_batch_session(self) -> bool:
        """启动一口气模式会话"""
        try:
            # 启动音频录制
            if not self.audio_recorder.start_recording():
                print("❌ 音频录制启动失败")
                return False
            
            print(f"✅ 一口气模式启动成功")
            print(f"   松开 Command 键停止录音并处理")
            
            return True
            
        except Exception as e:
            print(f"❌ 一口气模式启动失败: {e}")
            return False
    
    def _realtime_audio_feed(self):
        """实时音频数据馈送线程"""
        print("🔄 实时音频馈送线程已启动")
        last_feed_time = time.time()
        
        while self.realtime_active and self.current_state == SessionState.RECORDING:
            try:
                current_time = time.time()
                
                # 获取最新音频块
                audio_chunk = self.audio_recorder.get_latest_audio_chunk()
                if audio_chunk is not None:
                    # 馈送给 VAD
                    self.vad.feed_audio(audio_chunk)
                    last_feed_time = current_time
                else:
                    # 如果太久没有新数据，可能有问题
                    if current_time - last_feed_time > 5.0:
                        last_feed_time = current_time
                
                time.sleep(0.05)  # 增加馈送频率
                
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 音频馈送错误: {e}")
                break
        
        print("🔄 实时音频馈送线程已结束")
    
    def stop_session(self, force: bool = False) -> List[ProcessedSegment]:
        """停止当前会话"""
        if self.current_state == SessionState.IDLE:
            print("⚠️ 没有活跃的会话")
            return self.session_segments
        
        print(f"⏹️ 停止会话: {self.current_session_id}")
        
        with self.state_lock:
            self.current_state = SessionState.PROCESSING
        
        # 停止实时模式线程
        if self.realtime_active:
            self.realtime_active = False
            if self.audio_feed_thread:
                self.audio_feed_thread.join(timeout=2.0)
        
        # 停止音频录制
        final_audio = self.audio_recorder.stop_recording()

        short_recording_cancelled = False

        if self.config.mode == SessionMode.BATCH:
            recorded_seconds = self._calculate_audio_duration(final_audio)
            min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)

            if recorded_seconds <= min_duration:
                self._handle_short_batch_cancel(recorded_seconds)
                short_recording_cancelled = True
            elif final_audio is not None:
                # 一口气模式：处理完整音频
                self._process_batch_audio(final_audio)
        elif self.config.mode == SessionMode.REALTIME:
            # 实时模式：强制完成当前分段，然后停止VAD
            print("🔄 强制完成当前分段...")
            self.vad.force_segment_complete()
            self.vad.stop()
            print(f"✅ VAD已停止")

        if not short_recording_cancelled:
            # 等待所有分段处理完成
            print("⏳ 等待分段处理完成...")
            self.segment_processor.wait_for_completion()

        # 停止 SegmentProcessor
        if self.config.mode == SessionMode.REALTIME:
            self.segment_processor.stop()
            print(f"✅ SegmentProcessor已停止")
        
        with self.state_lock:
            self.current_state = SessionState.COMPLETED

        return self.session_segments

    def _calculate_audio_duration(self, audio_data) -> float:
        """根据音频数据计算时长"""
        if audio_data is None:
            return 0.0

        sample_rate = getattr(self.audio_recorder, "sample_rate", getattr(config, "SAMPLE_RATE", 16000))
        if not sample_rate:
            return 0.0

        return len(audio_data) / float(sample_rate)

    def _handle_short_batch_cancel(self, recorded_seconds: float) -> None:
        """处理批量模式下录音过短的情况"""
        min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)
        print(
            f"⚠️ 会话录音时长 {recorded_seconds:.2f}s，小于最短转录要求 {min_duration:.0f}s，已跳过转录。"
        )
        print("ℹ️ 请按住 Command 键更长时间以触发完整转录。")

        if getattr(config, "ENABLE_NOTIFICATIONS", True):
            try:
                notification_manager.show_warning_notification(
                    f"录音时长 {recorded_seconds:.2f}s，小于最短转录要求 {min_duration:.0f}s，已取消本次会话。"
                )
            except Exception as exc:
                if config.DEBUG_MODE:
                    print(f"⚠️ 警告通知发送失败: {exc}")

        with self.state_lock:
            self.session_segments = []
            self._current_batch_task_id = None
            self._last_batch_processing_info = None
    
    def _process_batch_audio(self, audio_data):
        """处理一口气模式的完整音频"""
        try:
            duration_seconds = len(audio_data) / self.audio_recorder.sample_rate if audio_data is not None else 0
            print(f"📊 处理完整音频: {duration_seconds:.2f}s")

            metadata = {
                "session_id": self.current_session_id,
                "mode": self.config.mode.value,
                "duration_seconds": duration_seconds,
                "enable_correction": self.config.enable_correction,
                "enable_dictionary": self.config.enable_dictionary,
            }

            task_id = self.retry_manager.submit_audio(
                audio_data=audio_data,
                task_id=self.current_session_id,
                force_immediate=True,
                metadata=metadata
            )

            with self.state_lock:
                self._current_batch_task_id = task_id

            print(f"⏳ 音频已提交到重试管理器: {task_id}")

        except Exception as e:
            print(f"❌ 批量音频处理失败: {e}")
            if self.on_error:
                self.on_error(f"批量处理失败: {e}")
    
    # VAD 回调方法
    def _on_vad_segment_complete(self, segment):
        """VAD 分段完成回调"""
        if config.DEBUG_MODE:
            print(f"🎙️ 语音分段完成: {segment.duration:.2f}s")
        
        # 提交到分段处理器
        self.segment_processor.submit_segment(segment)
    
    def _on_voice_start(self, timestamp: float):
        """语音开始回调"""
        if config.DEBUG_MODE:
            print(f"🎤 检测到语音开始: {timestamp:.2f}s")
    
    def _on_voice_stop(self, timestamp: float):
        """语音停止回调"""
        if config.DEBUG_MODE:
            print(f"🔇 检测到语音停止: {timestamp:.2f}s")
    
    def _on_vad_state_change(self, old_state, new_state):
        """VAD 状态变更回调"""
        if config.DEBUG_MODE:
            print(f"🔄 VAD 状态变更: {old_state.value} → {new_state.value}")
    
    # 分段处理器回调方法
    def _on_segment_complete(self, segment):
        """分段处理完成回调"""
        with self.state_lock:
            self.session_segments.append(segment)
        
        print(f"✅ 分段处理完成: {segment.segment_id} ({len(segment.final_text)} 字符)")
        
        if config.DEBUG_MODE:
            # 尝试安全地访问 transcription 属性
            if hasattr(segment, 'transcription') and segment.transcription:
                print(f"   原始转录: {segment.transcription}")
            elif hasattr(segment, 'original_text') and segment.original_text:
                print(f"   原始转录: {segment.original_text}")
            print(f"   最终文本: {segment.final_text}")
    
    def _on_segment_output(self, segment, text=None):
        """分段输出回调"""
        if self.config.auto_output_enabled and segment.final_text:
            # 自动输出到光标位置
            request = InputRequest(
                text=segment.final_text,
                method=self.config.output_method,
                backup_to_clipboard=self.config.clipboard_backup,
                request_id=segment.segment_id
            )
            
            result = self.text_input_manager.input_text(request)
            
            if result == InputResult.SUCCESS:
                print(f"📝 已输出到光标位置: {len(segment.final_text)} 字符")
            else:
                print(f"⚠️ 输出失败: {result.value}")
        
        # 调用实时输出回调
        if self.on_realtime_output:
            try:
                self.on_realtime_output(segment.final_text)
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 实时输出回调异常: {e}")
    
    def _on_segment_error(self, segment_id: str, error: str):
        """分段处理错误回调"""
        print(f"❌ 分段处理失败: {segment_id} - {error}")
        
        if self.on_error:
            try:
                self.on_error(f"分段 {segment_id} 处理失败: {error}")
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 错误回调异常: {e}")
    
    def _on_session_complete(self, segments):
        """会话完成回调"""
        print(f"🎉 会话处理完成: {len(segments)} 个分段")
        
        # 调用会话完成回调
        if self.on_session_complete:
            try:
                self.on_session_complete(segments)
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 会话完成回调异常: {e}")
    
    # 重试管理器回调方法（用于一口气模式）
    def _batch_transcription_callback(self, audio_data) -> Optional[str]:
        """批量模式的转录回调"""
        if audio_data is None or len(audio_data) == 0:
            print("❌ 批量转录失败: 音频数据为空")
            return None

        processing_times: Dict[str, float] = {}
        raw_transcript: Optional[str] = None
        processed_transcript: Optional[str] = None
        corrected_transcript: Optional[str] = None

        try:
            # 第一步：完整音频转录
            self.timer.reset()
            self.timer.start("batch_transcription")
            raw_transcript = self.segment_processor.transcriber.transcribe_complete_audio(audio_data)
        finally:
            timing = self.timer.stop("batch_transcription")
            if timing:
                processing_times['transcription'] = timing.duration_ms / 1000.0

        if not raw_transcript:
            print("❌ 批量转录失败: 未获得转录文本")
            return None

        raw_transcript = raw_transcript.strip()
        processed_transcript = raw_transcript

        # 第二步：词典处理
        if self.config.enable_dictionary and self.segment_processor.enable_dictionary:
            try:
                self.timer.start("batch_dictionary")
                transcript_data = [{
                    'text': raw_transcript,
                    'start': 0.0,
                    'duration': len(audio_data) / self.audio_recorder.sample_rate
                }]
                processed_entries = self.segment_processor.dictionary_manager.process_transcript(transcript_data)
                merged_text = ""
                for entry in processed_entries:
                    text = entry.get('text', '').strip()
                    if text:
                        merged_text += text + " "
                processed_transcript = merged_text.strip() or raw_transcript
            finally:
                timing = self.timer.stop("batch_dictionary")
                if timing:
                    processing_times['dictionary'] = timing.duration_ms / 1000.0

        final_text = processed_transcript

        # 第三步：可选纠错
        if (self.config.enable_correction and self.segment_processor.enable_correction and
                self.segment_processor.corrector.is_ready and
                config.GEMINI_MODEL != config.GEMINI_TRANSCRIPTION_MODEL):
            try:
                self.timer.start("batch_correction")
                candidate = self.segment_processor.corrector.correct_transcript(processed_transcript)
                if candidate and candidate.strip() and candidate.strip() != processed_transcript:
                    corrected_transcript = candidate.strip()
                    final_text = corrected_transcript
            finally:
                timing = self.timer.stop("batch_correction")
                if timing:
                    processing_times['correction'] = timing.duration_ms / 1000.0

        info = {
            "task_id": self._current_batch_task_id,
            "raw_transcript": raw_transcript,
            "processed_transcript": processed_transcript,
            "corrected_transcript": corrected_transcript,
            "final_text": final_text,
            "processing_times": processing_times
        }

        with self.state_lock:
            self._last_batch_processing_info = info

        if config.DEBUG_MODE:
            print(f"📝 批量转录完成: {len(final_text)} 字符")

        return final_text

    def _batch_success_callback(self, task_id: str, transcript: str):
        """批量处理成功回调"""
        final_text = (transcript or "").strip()

        with self.state_lock:
            info = self._last_batch_processing_info or {}
            self._last_batch_processing_info = None
            if self._current_batch_task_id == task_id:
                self._current_batch_task_id = None

        if not final_text:
            print("⚠️ 批量处理返回空文本")
            return

        raw_transcript = info.get('raw_transcript', final_text)
        processed_transcript = info.get('processed_transcript', raw_transcript)
        corrected_transcript = info.get('corrected_transcript')
        processing_times = info.get('processing_times', {})

        batch_segment = ProcessedSegment(
            segment_id=f"batch_{task_id}",
            original_audio=None,
            raw_transcript=raw_transcript,
            processed_transcript=processed_transcript,
            corrected_transcript=corrected_transcript,
            final_text=final_text,
            status=SegmentStatus.COMPLETED,
            processing_times={},
            metadata={
                "task_id": task_id,
                "mode": "batch"
            }
        )

        for step, duration in processing_times.items():
            batch_segment.processing_times[step] = duration

        batch_segment.completed_time = time.time()

        with self.state_lock:
            self.session_segments = [batch_segment]

        print(f"✅ 一口气模式处理完成: {len(final_text)} 字符")

        if config.ENABLE_CLIPBOARD:
            try:
                import pyperclip
                pyperclip.copy(final_text)
                print("📋 文本已复制到剪贴板")
            except Exception as e:
                print(f"⚠️ 剪贴板复制失败: {e}")

        if self.on_session_complete:
            try:
                self.on_session_complete([batch_segment])
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 会话完成回调异常: {e}")

    def _batch_failure_callback(self, task_id: str, error: str):
        """批量处理失败回调"""
        print(f"❌ 一口气模式处理失败: {error}")

        with self.state_lock:
            if self._current_batch_task_id == task_id:
                self._current_batch_task_id = None
            self._last_batch_processing_info = None

        if self.on_error:
            try:
                self.on_error(f"一口气模式失败: {error}")
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 错误回调异常: {e}")
    
    def is_ready(self) -> bool:
        """检查管理器是否准备就绪"""
        return (
            self.audio_recorder is not None and
            self.vad is not None and
            self.segment_processor is not None and
            self.text_input_manager is not None and
            self.current_state == SessionState.IDLE
        )
    
    def get_session_info(self) -> dict:
        """获取会话信息"""
        return {
            "session_id": self.current_session_id,
            "mode": self.config.mode.value,
            "state": self.current_state.value,
            "start_time": self.session_start_time,
            "segments_count": len(self.session_segments),
            "is_ready": self.is_ready(),
            "config": {
                "silence_duration": self.config.silence_duration,
                "auto_output_enabled": self.config.auto_output_enabled,
                "output_method": self.config.output_method.value,
                "enable_correction": self.config.enable_correction,
                "enable_dictionary": self.config.enable_dictionary
            }
        }
    
    def get_current_state(self):
        """获取当前状态"""
        return self.current_state
    
    def get_session_segments(self):
        """获取会话分段"""
        return self.session_segments.copy()
    
    def cleanup(self):
        """清理资源"""
        if self.current_state != SessionState.IDLE:
            self.stop_session(force=True)
        
        # 停止实时线程
        if self.realtime_active:
            self.realtime_active = False
            if self.audio_feed_thread:
                self.audio_feed_thread.join(timeout=1.0)


# 全局实例
session_mode_manager = SessionModeManager()


def test_session_mode_manager():
    """测试会话模式管理器"""
    print("🧪 测试会话模式管理器...")
    
    def on_start(mode: SessionMode):
        print(f"🚀 会话开始: {mode.value}")
    
    def on_complete(segments: List[ProcessedSegment]):
        print(f"✅ 会话完成: {len(segments)} 个分段")
    
    def on_output(text: str):
        print(f"📝 实时输出: \"{text}\"")
    
    def on_error(error: str):
        print(f"❌ 会话错误: {error}")
    
    manager = SessionModeManager()
    manager.set_callbacks(
        on_session_start=on_start,
        on_session_complete=on_complete,
        on_realtime_output=on_output,
        on_error=on_error
    )
    
    if not manager.is_ready():
        print("❌ 会话模式管理器未准备就绪")
        return
    
    print(f"📊 会话信息: {manager.get_session_info()}")
    
    # 测试配置更新
    manager.update_config(
        mode=SessionMode.REALTIME,
        silence_duration=3.0,
        auto_output_enabled=False
    )
    
    print("✅ 会话模式管理器测试完成")


if __name__ == "__main__":
    test_session_mode_manager()
