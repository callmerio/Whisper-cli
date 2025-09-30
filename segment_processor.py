#!/usr/bin/env python3
"""
分段处理器
负责协调语音分段的检测、转录、后处理和输出
"""

import time
import threading
import queue
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

# 导入项目组件
from voice_activity_detector import VoiceSegment, VoiceActivityDetector
from text_input_manager import TextInputManager, InputRequest, InputMethod, InputResult
from service_registry import get_transcriber, get_corrector, get_dictionary
from timer_utils import Timer
import config


class SegmentStatus(Enum):
    """分段状态"""
    PENDING = "待处理"
    TRANSCRIBING = "转录中"
    PROCESSING = "后处理中"
    OUTPUTTING = "输出中"
    COMPLETED = "已完成"
    FAILED = "失败"


@dataclass
class ProcessedSegment:
    """处理后的分段"""
    segment_id: str
    original_audio: VoiceSegment
    raw_transcript: Optional[str] = None
    processed_transcript: Optional[str] = None
    corrected_transcript: Optional[str] = None
    final_text: Optional[str] = None
    status: SegmentStatus = SegmentStatus.PENDING
    error_message: Optional[str] = None
    processing_times: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_time: float = field(default_factory=time.time)
    completed_time: Optional[float] = None
    
    @property
    def total_processing_time(self) -> float:
        """总处理时间"""
        if self.completed_time:
            return self.completed_time - self.created_time
        return time.time() - self.created_time


class SegmentProcessor:
    """分段处理器"""
    
    def __init__(self):
        """初始化分段处理器"""
        # 核心组件
        self.transcriber = get_transcriber()
        self.corrector = get_corrector()
        self.dictionary_manager = get_dictionary()
        self.text_input_manager = TextInputManager()
        self.timer = Timer()
        
        # 配置参数
        self.enable_correction = config.ENABLE_CORRECTION
        self.enable_dictionary = getattr(config, 'SEGMENT_ENABLE_DICTIONARY', True)
        self.enable_auto_output = getattr(config, 'SEGMENT_ENABLE_AUTO_OUTPUT', True)
        
        # 处理输出方法配置（可能是字符串或枚举）
        output_method_str = getattr(config, 'SEGMENT_OUTPUT_METHOD', 'direct_type')
        if isinstance(output_method_str, InputMethod):
            self.output_method = output_method_str
        elif output_method_str == 'direct_type':
            self.output_method = InputMethod.DIRECT_TYPE
        elif output_method_str == 'clipboard':
            self.output_method = InputMethod.CLIPBOARD_PASTE
        else:
            self.output_method = InputMethod.DISABLED
            
        self.max_concurrent_segments = getattr(config, 'SEGMENT_MAX_CONCURRENT', 3)
        
        # 状态管理
        self.running = False
        self.processing_queue = queue.Queue()
        self.postprocess_queue = queue.Queue()
        self.active_segments: Dict[str, ProcessedSegment] = {}
        self.postprocess_active: Dict[str, ProcessedSegment] = {}
        self.completed_segments: List[ProcessedSegment] = []
        self.session_segments: List[str] = []  # 当前会话的分段ID列表

        # 线程管理
        self.processing_threads: List[threading.Thread] = []
        self.postprocess_threads: List[threading.Thread] = []
        self.postprocess_running = False
        self.thread_lock = threading.Lock()
        self._completion_condition = threading.Condition()
        
        # 回调函数
        self.on_segment_start: Optional[Callable[[ProcessedSegment], None]] = None
        self.on_segment_complete: Optional[Callable[[ProcessedSegment], None]] = None
        self.on_segment_output: Optional[Callable[[ProcessedSegment, str], None]] = None
        self.on_segment_error: Optional[Callable[[ProcessedSegment, str], None]] = None
        self.on_session_complete: Optional[Callable[[List[ProcessedSegment]], None]] = None
        
        print(f"🔄 分段处理器初始化完成")
        print(f"   转录器就绪: {'✅' if self.transcriber.is_ready else '❌'}") 
        print(f"   纠错器就绪: {'✅' if self.corrector.is_ready else '❌'}")
        print(f"   自动输出: {'✅' if self.enable_auto_output else '❌'}")
        if isinstance(self.output_method, InputMethod):
            print(f"   输出方法: {self.output_method.value}")
        else:
            print(f"   输出方法: {self.output_method}")
        print(f"   最大并发: {self.max_concurrent_segments}")

    def set_callbacks(self,
                     on_segment_start: Optional[Callable[[ProcessedSegment], None]] = None,
                     on_segment_complete: Optional[Callable[[ProcessedSegment], None]] = None,
                     on_segment_output: Optional[Callable[[ProcessedSegment, str], None]] = None,
                     on_segment_error: Optional[Callable[[ProcessedSegment, str], None]] = None,
                     on_session_complete: Optional[Callable[[List[ProcessedSegment]], None]] = None):
        """设置回调函数"""
        self.on_segment_start = on_segment_start
        self.on_segment_complete = on_segment_complete
        self.on_segment_output = on_segment_output
        self.on_segment_error = on_segment_error
        self.on_session_complete = on_session_complete

    def _notify_progress(self) -> None:
        with self._completion_condition:
            self._completion_condition.notify_all()

    @staticmethod
    def _short_text(text: str, limit: int = 80) -> str:
        clean = (text or "").strip()
        return clean if len(clean) <= limit else clean[: limit - 3] + "..."

    def start(self) -> bool:
        """启动分段处理器"""
        if self.running:
            return True
        
        if not self.transcriber.is_ready:
            print("❌ 转录器未就绪，无法启动分段处理器")
            return False
        
        self.running = True
        
        # 启动处理线程
        for i in range(self.max_concurrent_segments):
            thread = threading.Thread(
                target=self._processing_worker,
                args=(f"worker_{i}",),
                daemon=True,
            )
            thread.start()
            self.processing_threads.append(thread)

        self.postprocess_running = True
        post_thread = threading.Thread(
            target=self._postprocess_worker,
            args=("post_worker_0",),
            daemon=True,
        )
        post_thread.start()
        self.postprocess_threads.append(post_thread)
        
        print(f"🚀 分段处理器已启动 ({len(self.processing_threads)} 个处理线程)")
        return True

    def stop(self):
        """停止分段处理器"""
        if not self.running:
            return
        
        print("⏹️ 正在停止分段处理器...")
        self.running = False
        
        # 等待处理队列清空
        timeout = 10.0
        start_time = time.time()
        while not self.processing_queue.empty() and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        # 等待处理线程结束
        for thread in self.processing_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

        # 停止后处理线程
        self.postprocess_running = False
        while not self.postprocess_queue.empty():
            try:
                self.postprocess_queue.get_nowait()
            except queue.Empty:
                break

        for thread in self.postprocess_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        self.postprocess_threads.clear()

        # 完成当前会话
        if self.session_segments:
            self._complete_current_session()

        print("✅ 分段处理器已停止")
        self._notify_progress()
    
    def submit_segment(self, voice_segment: VoiceSegment) -> str:
        """提交语音分段进行处理"""
        if not self.running:
            return ""
        
        # 创建处理对象
        processed_segment = ProcessedSegment(
            segment_id=voice_segment.segment_id,
            original_audio=voice_segment,
            metadata={
                "audio_duration": voice_segment.duration,
                "audio_samples": len(voice_segment.audio_data),
                "submit_time": time.time()
            }
        )
        
        # 添加到活跃列表和会话列表
        with self.thread_lock:
            self.active_segments[processed_segment.segment_id] = processed_segment
            self.session_segments.append(processed_segment.segment_id)
        
        # 提交到处理队列
        try:
            self.processing_queue.put(processed_segment, timeout=1.0)
            print(f"📤 分段已提交: {processed_segment.segment_id} ({voice_segment.duration:.1f}s)")
            
            # 调用开始回调
            if self.on_segment_start:
                try:
                    self.on_segment_start(processed_segment)
                except Exception as e:
                    if config.DEBUG_MODE:
                        print(f"⚠️ 分段开始回调异常: {e}")
            
            return processed_segment.segment_id
            
        except queue.Full:
            print(f"⚠️ 处理队列已满，丢弃分段: {processed_segment.segment_id}")
            with self.thread_lock:
                self.active_segments.pop(processed_segment.segment_id, None)
                if processed_segment.segment_id in self.session_segments:
                    self.session_segments.remove(processed_segment.segment_id)
            return ""
    
    def _processing_worker(self, worker_name: str):
        """分段处理工作线程"""
        print(f"🔄 分段处理工作线程 {worker_name} 已启动")
        
        while self.running:
            try:
                # 获取待处理分段
                segment = self.processing_queue.get(timeout=1.0)
                
                # 处理分段
                self._process_segment(segment, worker_name)
                
            except queue.Empty:
                continue
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 处理线程 {worker_name} 异常: {e}")
        
        print(f"🔄 分段处理工作线程 {worker_name} 已结束")
    
    def _process_segment(self, segment: ProcessedSegment, worker_name: str):
        """处理单个分段"""
        try:
            print(f"🔄 [{worker_name}] 开始处理分段: {segment.segment_id}")
            
            # 第一步：转录
            segment.status = SegmentStatus.TRANSCRIBING
            start_time = time.time()
            
            transcript = self.transcriber.transcribe_complete_audio(segment.original_audio.audio_data)
            segment.processing_times['transcription'] = time.time() - start_time
            
            if not transcript:
                self._handle_segment_error(segment, "转录失败")
                return
            
            segment.raw_transcript = transcript
            preview = self._short_text(transcript)
            print(f"✅ [{worker_name}] 转录完成: {segment.segment_id} -> \"{preview}\"")
            
            segment.status = SegmentStatus.PROCESSING

            with self.thread_lock:
                self.postprocess_active[segment.segment_id] = segment

            self.postprocess_queue.put(segment)

        except Exception as e:
            self._handle_segment_error(segment, f"处理异常: {e}")

    def _postprocess_worker(self, worker_name: str):
        """执行词典与纠错的后台线程"""
        print(f"🔄 后处理线程 {worker_name} 已启动")

        while self.postprocess_running or not self.postprocess_queue.empty():
            try:
                segment = self.postprocess_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                processed_text = segment.raw_transcript or ""

                if self.enable_dictionary and processed_text:
                    start_time = time.time()
                    transcript_data = [
                        {
                            'text': processed_text,
                            'start': 0.0,
                            'duration': segment.original_audio.duration,
                        }
                    ]
                    processed_entries = self.dictionary_manager.process_transcript(transcript_data)
                    merged_text = ""
                    for entry in processed_entries:
                        text = entry.get('text', '').strip()
                        if text:
                            merged_text += text + " "
                    segment.processed_transcript = merged_text.strip() or processed_text
                    segment.processing_times['dictionary'] = time.time() - start_time
                    if config.DEBUG_MODE:
                        print(f"📚 [{worker_name}] 词典处理完成: {segment.segment_id}")
                else:
                    segment.processed_transcript = processed_text

                final_text = segment.processed_transcript

                if (
                    final_text
                    and self.enable_correction
                    and self.corrector.is_ready
                    and config.GEMINI_MODEL != config.GEMINI_TRANSCRIPTION_MODEL
                ):
                    start_time = time.time()
                    candidate = self.corrector.correct_transcript(final_text)
                    segment.processing_times['correction'] = time.time() - start_time
                    if candidate and candidate.strip() and candidate.strip() != final_text:
                        segment.corrected_transcript = candidate.strip()
                        final_text = segment.corrected_transcript
                        if config.DEBUG_MODE:
                            print(f"🤖 [{worker_name}] 纠错完成: {segment.segment_id}")

                segment.final_text = final_text

                if self.enable_auto_output and final_text:
                    segment.status = SegmentStatus.OUTPUTTING
                    start_time = time.time()
                    success = self._output_segment_text(segment, final_text)
                    segment.processing_times['output'] = time.time() - start_time
                    if success:
                        print(f"📝 [{worker_name}] 文本输出完成: {segment.segment_id}")
                    else:
                        print(f"⚠️ [{worker_name}] 文本输出失败: {segment.segment_id}")

                segment.status = SegmentStatus.COMPLETED
                segment.completed_time = time.time()

                with self.thread_lock:
                    self.active_segments.pop(segment.segment_id, None)
                    self.postprocess_active.pop(segment.segment_id, None)
                    self.completed_segments.append(segment)
                self._notify_progress()

                print(f"✅ [{worker_name}] 分段处理完成: {segment.segment_id} ({segment.total_processing_time:.2f}s)")

                if self.on_segment_complete:
                    try:
                        self.on_segment_complete(segment)
                    except Exception as callback_error:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 分段完成回调异常: {callback_error}")

            except Exception as exc:
                self._handle_segment_error(segment, f"后处理异常: {exc}")

            finally:
                self.postprocess_queue.task_done()

        print(f"🔄 后处理线程 {worker_name} 已结束")

    def _output_segment_text(self, segment: ProcessedSegment, text: str) -> bool:
        """输出分段文本"""
        try:
            print(f"🎯 准备自动粘贴文本到光标位置: '{text}'")
            print(f"   请确保目标应用处于前台并且光标在正确位置")
            
            request = InputRequest(
                text=text,
                method=self.output_method,
                delay_before=1.5,  # 增加延迟确保用户有足够时间切换应用
                delay_after=0.1,
                backup_to_clipboard=True,  # 启用剪贴板备份
                request_id=segment.segment_id
            )
            
            result = self.text_input_manager.input_text(request)
            success = result == InputResult.SUCCESS
            
            if success:
                print(f"✅ 文本已自动粘贴: '{text}'")
            else:
                print(f"❌ 自动粘贴失败: {result.value}")
                print(f"💡 文本已复制到剪贴板，请手动按 Cmd+V 粘贴")
                # 确保文本在剪贴板中
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    print(f"📋 文本已备份到剪贴板: '{text}'")
                except Exception as e:
                    print(f"⚠️ 剪贴板备份也失败了: {e}")
            
            # 调用输出回调
            if self.on_segment_output:
                try:
                    self.on_segment_output(segment, text)
                except Exception as e:
                    if config.DEBUG_MODE:
                        print(f"⚠️ 分段输出回调异常: {e}")
            
            return success
            
        except Exception as e:
            print(f"❌ 分段文本输出异常: {e}")
            # 异常情况下也要保证文本进入剪贴板
            try:
                import pyperclip
                pyperclip.copy(text)
                print(f"📋 异常恢复: 文本已复制到剪贴板: '{text}'")
            except:
                pass
            return False
    
    def _handle_segment_error(self, segment: ProcessedSegment, error_message: str):
        """处理分段错误"""
        segment.status = SegmentStatus.FAILED
        segment.error_message = error_message
        segment.completed_time = time.time()
        
        print(f"❌ 分段处理失败: {segment.segment_id} - {error_message}")
        
        # 移动到完成列表
        with self.thread_lock:
            self.active_segments.pop(segment.segment_id, None)
            self.postprocess_active.pop(segment.segment_id, None)
            self.completed_segments.append(segment)
        self._notify_progress()
        
        # 调用错误回调
        if self.on_segment_error:
            try:
                self.on_segment_error(segment, error_message)
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ 分段错误回调异常: {e}")
    
    def start_new_session(self):
        """开始新会话"""
        # 完成当前会话
        if self.session_segments:
            self._complete_current_session()
        
        # 重置会话状态
        with self.thread_lock:
            self.session_segments = []
        
        print("🆕 开始新的分段会话")
    
    def complete_current_session(self) -> List[ProcessedSegment]:
        """完成当前会话"""
        return self._complete_current_session()
    
    def _complete_current_session(self) -> List[ProcessedSegment]:
        """完成当前会话的内部实现"""
        if not self.session_segments:
            return []
        
        # 等待所有分段完成
        max_wait_time = 30.0  # 最多等待30秒
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            with self.thread_lock:
                pending_segments = [sid for sid in self.session_segments if sid in self.active_segments]
            
            if not pending_segments:
                break
            
            print(f"⏳ 等待 {len(pending_segments)} 个分段完成处理...")
            time.sleep(0.5)
        
        # 收集会话分段
        session_segments = []
        for segment_id in self.session_segments:
            segment = next((s for s in self.completed_segments if s.segment_id == segment_id), None)
            if segment:
                session_segments.append(segment)
        
        if session_segments:
            # 按时间排序
            session_segments.sort(key=lambda s: s.created_time)
            
            # 生成完整文本并备份到剪贴板
            full_text = self._generate_session_text(session_segments)
            if full_text:
                self._backup_session_to_clipboard(full_text)
            
            print(f"📋 会话完成: {len(session_segments)} 个分段，总计 {len(full_text)} 字符")
            
            # 调用会话完成回调
            if self.on_session_complete:
                try:
                    self.on_session_complete(session_segments)
                except Exception as e:
                    if config.DEBUG_MODE:
                        print(f"⚠️ 会话完成回调异常: {e}")
        
        # 清空会话列表
        with self.thread_lock:
            self.session_segments = []
        
        return session_segments
    
    def _generate_session_text(self, segments: List[ProcessedSegment]) -> str:
        """生成会话完整文本"""
        full_text = ""
        for segment in segments:
            if segment.final_text:
                full_text += segment.final_text + " "
        
        return full_text.strip()
    
    def _backup_session_to_clipboard(self, text: str):
        """将会话文本备份到剪贴板"""
        try:
            import pyperclip
            pyperclip.copy(text)
            print(f"📋 会话文本已备份到剪贴板 ({len(text)} 字符)")
        except Exception as e:
            print(f"⚠️ 剪贴板备份失败: {e}")
    
    def get_session_status(self) -> dict:
        """获取会话状态"""
        with self.thread_lock:
            active_count = len(self.active_segments)
            session_count = len(self.session_segments)
            completed_count = len([s for s in self.completed_segments 
                                 if s.segment_id in self.session_segments])
        
        return {
            "session_segments": session_count,
            "active_segments": active_count,
            "completed_segments": completed_count,
            "queue_size": self.processing_queue.qsize(),
            "running": self.running
        }
    
    def get_processing_stats(self) -> dict:
        """获取处理统计"""
        completed = self.completed_segments
        if not completed:
            return {}
        
        # 计算平均处理时间
        total_times = {}
        for segment in completed:
            for step, duration in segment.processing_times.items():
                if step not in total_times:
                    total_times[step] = []
                total_times[step].append(duration)
        
        avg_times = {}
        for step, times in total_times.items():
            avg_times[f"avg_{step}_time"] = sum(times) / len(times)
        
        return {
            "total_segments": len(completed),
            "successful_segments": len([s for s in completed if s.status == SegmentStatus.COMPLETED]),
            "failed_segments": len([s for s in completed if s.status == SegmentStatus.FAILED]),
            **avg_times
        }
    
    def wait_for_completion(self, timeout: float = 30.0) -> bool:
        """等待所有分段处理完成"""
        end_time = time.time() + timeout

        while time.time() < end_time:
            with self.thread_lock:
                pending_processing = bool(self.active_segments) or not self.processing_queue.empty()
                pending_post = bool(self.postprocess_active) or not self.postprocess_queue.empty()
                if not pending_processing and not pending_post:
                    return True

            remaining = end_time - time.time()
            if remaining <= 0:
                break

            with self._completion_condition:
                self._completion_condition.wait(timeout=remaining)

        print(f"⚠️ 等待分段处理完成超时: {timeout}s")
        return False


def test_segment_processor():
    """测试分段处理器"""
    print("🧪 测试分段处理器...")
    
    # 创建测试用的语音分段
    import numpy as np
    
    def create_test_segment(segment_id: str, duration: float = 2.0) -> VoiceSegment:
        samples = int(duration * config.SAMPLE_RATE)
        audio_data = np.random.normal(0, 0.1, samples).astype(np.int16)
        
        return VoiceSegment(
            start_time=time.time(),
            end_time=time.time() + duration,
            audio_data=audio_data,
            duration=duration,
            segment_id=segment_id
        )
    
    def on_complete(segment: ProcessedSegment):
        print(f"✅ 分段完成: {segment.segment_id} -> \"{segment.final_text}\"")
    
    def on_error(segment: ProcessedSegment, error: str):
        print(f"❌ 分段失败: {segment.segment_id} - {error}")
    
    def on_output(segment: ProcessedSegment, text: str):
        print(f"📝 分段输出: {segment.segment_id} -> \"{text}\"")
    
    # 创建处理器
    processor = SegmentProcessor()
    processor.set_callbacks(
        on_segment_complete=on_complete,
        on_segment_error=on_error,
        on_segment_output=on_output
    )
    
    if not processor.start():
        print("❌ 分段处理器启动失败")
        return
    
    try:
        # 提交测试分段
        test_segments = [
            create_test_segment("test_1", 1.5),
            create_test_segment("test_2", 2.0),
            create_test_segment("test_3", 1.0),
        ]
        
        for segment in test_segments:
            processor.submit_segment(segment)
            time.sleep(0.5)
        
        # 等待处理完成
        print("⏳ 等待处理完成...")
        time.sleep(10)
        
        # 完成会话
        session_segments = processor.complete_current_session()
        print(f"📋 会话完成: {len(session_segments)} 个分段")
        
        # 显示统计
        stats = processor.get_processing_stats()
        print(f"📊 处理统计: {stats}")
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被中断")
    
    finally:
        processor.stop()
        print("✅ 分段处理器测试完成")


if __name__ == "__main__":
    test_segment_processor()
