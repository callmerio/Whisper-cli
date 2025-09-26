#!/usr/bin/env python3
"""
基于 Gemini-2.5-Flash 的语音转录系统主程序
使用 Gemini 进行音频转录，支持 Command 长按控制录音
"""

import time
import signal
import sys
from enum import Enum
from typing import Optional, List, Dict, Any
import threading
import pyperclip

# 导入各个模块
from hotkey_listener import HotkeyListener
from audio_recorder import AudioRecorder
from gemini_transcriber import GeminiTranscriber  # 使用 Gemini 转录器
from dictionary_manager import DictionaryManager
from gemini_corrector import GeminiCorrector
from timer_utils import Timer
from notification_utils import notification_manager
from audio_retry_manager import audio_retry_manager  # 导入重试管理器

# 导入新的会话模式组件
from session_mode_manager import SessionModeManager, SessionMode, SessionState
from text_input_manager import TextInputManager, InputMethod, InputRequest, InputResult
import config

class AppState(Enum):
    """应用状态枚举"""
    IDLE = "待机"
    RECORDING = "录音中"
    PROCESSING = "处理中"
    COMPLETE = "完成"

class GeminiVoiceTranscriptionApp:
    def __init__(self, session_mode: Optional[SessionMode] = None, **session_config):
        """初始化基于 Gemini 的语音转录应用"""
        self.state = AppState.IDLE
        self.state_lock = threading.Lock()
        
        # 会话模式配置
        self.use_new_session_mode = session_mode is not None
        
        # 处理会话模式（可能是字符串或枚举）
        if session_mode is None:
            self.session_mode = SessionMode.BATCH
        elif isinstance(session_mode, SessionMode):
            self.session_mode = session_mode
        elif session_mode == 'batch':
            self.session_mode = SessionMode.BATCH
        elif session_mode == 'realtime':
            self.session_mode = SessionMode.REALTIME
        else:
            print(f"⚠️ 未知的会话模式: {session_mode}，使用默认模式")
            self.session_mode = SessionMode.BATCH
        
        # 根据模式选择组件初始化方式
        if self.use_new_session_mode:
            # 新的会话模式管理器
            self.session_manager = SessionModeManager()
            self.session_manager.update_config(**session_config)
            self.session_manager.set_callbacks(
                on_session_start=self._on_session_start,
                on_session_complete=self._on_session_complete,
                on_realtime_output=self._on_realtime_output,
                on_error=self._on_session_error
            )
            
            # 从会话管理器获取组件引用
            self.audio_recorder = self.session_manager.audio_recorder
            self.transcriber = self.session_manager.segment_processor.transcriber
            self.dictionary_manager = self.session_manager.segment_processor.dictionary_manager
            self.gemini_corrector = self.session_manager.segment_processor.corrector
            self.text_input_manager = self.session_manager.text_input_manager
            
            print(f"🆕 使用新会话模式: {self.session_mode.value}")
        else:
            # 传统模式（向后兼容）
            self.session_manager = None
            
            # 传统组件初始化
            self.audio_recorder = AudioRecorder()
            self.transcriber = GeminiTranscriber()  # 使用 Gemini 转录器
            self.dictionary_manager = DictionaryManager()
            self.gemini_corrector = GeminiCorrector()
            self.text_input_manager = TextInputManager()
            
            # 重试管理器配置
            self.retry_manager = audio_retry_manager
            self.retry_manager.set_callbacks(
                transcription_callback=self._transcription_callback,
                success_callback=self._on_transcription_success,
                failure_callback=self._on_transcription_failure
            )
            
            print(f"📱 使用传统模式（一口气模式）")
        
        # 公共组件
        self.hotkey_listener = HotkeyListener(
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release
        )
        self.timer = Timer()
        
        # 转录数据
        self.current_session_audio = None
        self.final_transcript = None
        self._last_autopaste_text = None

        # 运行标志
        self.running = False
        
        # 超时管理
        self.recording_start_time = None
        self.timeout_thread = None
        self.timeout_stop_event = threading.Event()
        self.warning_shown = False
        
        # 状态检查
        clipboard_status = "✅" if config.ENABLE_CLIPBOARD else "❌"
        gemini_transcription_status = "✅" if self.transcriber.is_ready else "❌"
        gemini_correction_status = "✅" if config.ENABLE_GEMINI_CORRECTION and self.gemini_corrector.is_ready else "❌"
        notification_status = "✅" if config.ENABLE_NOTIFICATIONS else "❌"
        
        max_duration_hours = config.MAX_RECORDING_DURATION // 3600
        max_duration_minutes = (config.MAX_RECORDING_DURATION % 3600) // 60
        duration_text = f"{max_duration_hours}小时{max_duration_minutes}分钟" if max_duration_hours > 0 else f"{max_duration_minutes}分钟"
        
        # 显示模式特定信息
        mode_info = """
模式: 一口气模式 📱"""
        
        print(f"""
🎤 Gemini 语音转录系统 v2.0
================================
快捷键: 按住 Command 键（松开即停止）
状态: {self.state.value}{mode_info}
转录引擎: Gemini-{config.GEMINI_TRANSCRIPTION_MODEL}
纠错引擎: {config.GEMINI_MODEL}
词典: {len(self.dictionary_manager.user_dict)} 个词汇
剪贴板: {clipboard_status}
Gemini转录: {gemini_transcription_status}
Gemini纠错: {gemini_correction_status}
通知系统: {notification_status}
最大录音时长: {duration_text}
================================
        """)
    
    def _on_hotkey_press(self):
        """Command 长按触发回调"""
        with self.state_lock:
            if self.state == AppState.IDLE:
                self._start_recording()
            else:
                if config.DEBUG_MODE:
                    print(f"当前状态 {self.state.value}，忽略开始录音请求")

    def _on_hotkey_release(self):
        """Command 松开回调"""
        with self.state_lock:
            if self.state == AppState.RECORDING:
                self._stop_recording()
            else:
                if config.DEBUG_MODE:
                    print(f"当前状态 {self.state.value}，忽略停止录音请求")
    
    # ==================== 新会话模式回调函数 ====================
    
    def _on_session_start(self, mode: SessionMode):
        """会话开始回调"""
        print(f"🚀 {mode.value}会话已开始")
        
        if mode == SessionMode.REALTIME:
            print("💡 提示: 系统将在您停顿后自动处理语音并输出到光标位置")
            print("   松开 Command 键可提前结束录音")
    
    def _on_session_complete(self, segments):
        """会话完成回调"""
        total_text = ""
        for segment in segments:
            if hasattr(segment, 'final_text') and segment.final_text:
                total_text += segment.final_text + " "
        
        print(f"✅ 会话完成: {len(segments)} 个分段，总计 {len(total_text.strip())} 字符")
        
        if total_text.strip():
            print(f"📝 完整内容: {total_text.strip()}")
    
    def _on_realtime_output(self, text: str):
        """实时输出回调"""
        print(f"📝 实时输出: \"{text}\"")
    
    def _on_session_error(self, error: str):
        """会话错误回调"""
        print(f"❌ 会话错误: {error}")
        
        if config.ENABLE_NOTIFICATIONS:
            notification_manager.show_error_notification(f"会话错误: {error}")
    
    def _start_recording(self):
        """开始录音"""
        if self.state != AppState.IDLE:
            return
        
        if self.use_new_session_mode:
            # 使用新的会话模式管理器
            success = self.session_manager.start_session(self.session_mode)
            if success:
                self.state = AppState.RECORDING
                self._last_autopaste_text = None
                print(f"\n{'='*50}")
                print(f"🎤 开始{self.session_mode.value}...")
                if self.session_mode == SessionMode.REALTIME:
                    silence_duration = getattr(config, 'VAD_SILENCE_DURATION', 4.0)
                    print(f"🔇 静音检测: {silence_duration}秒后自动分段")
                    print(f"📝 自动输出: 转录完成后直接输入到光标位置")
                print(f"⏹️ 松开 Command 键停止")
                print(f"{'='*50}")
            else:
                print("❌ 录音启动失败")
            return
        
        # 传统模式逻辑
        max_duration_text = self._format_duration(config.MAX_RECORDING_DURATION)
        print(f"\n{'='*50}")
        print(f"🎤 开始录音... (松开 Command 键停止)")
        print(f"⏰ 最大录音时长: {max_duration_text}")
        print(f"🌐 转录引擎: Gemini-{config.GEMINI_TRANSCRIPTION_MODEL}")
        print(f"{'='*50}")
        
        # 清空之前的数据
        self.final_transcript = None
        self.current_session_audio = None
        self._last_autopaste_text = None
        
        # 重置超时相关状态
        self.recording_start_time = time.time()
        self.warning_shown = False
        self.timeout_stop_event.clear()
        
        # 重置计时器并开始录音计时
        self.timer.reset()
        self.timer.start("total_session")
        self.timer.start("recording")
        
        # 更新状态
        self.state = AppState.RECORDING
        
        # 启动超时检查线程
        self._start_timeout_monitoring()
        
        # 开始录音
        success = self.audio_recorder.start_recording()
        
        if success:
            # 播放录音开始提示音
            if config.ENABLE_NOTIFICATIONS:
                notification_manager.show_start_recording_notification()
        else:
            print("❌ 录音启动失败")
            self.state = AppState.IDLE
            self.timer.reset()
            self._stop_timeout_monitoring()
    
    def _stop_recording(self, auto_stopped=False):
        """停止录音"""
        if self.state != AppState.RECORDING:
            return
        
        if self.use_new_session_mode:
            # 使用新的会话模式管理器
            self.state = AppState.PROCESSING
            
            stop_reason = "自动停止（超时）" if auto_stopped else "手动停止"
            print(f"\n{'='*50}")
            print(f"⏹️ 停止{self.session_mode.value} ({stop_reason})")
            print(f"🔄 正在处理...")
            print(f"{'='*50}")
            
            # 停止会话
            segments = self.session_manager.stop_session()
            
            # 完成处理
            self._finish_session()
            return
        
        # 传统模式逻辑
        # 停止超时监控
        self._stop_timeout_monitoring()
        
        stop_reason = "自动停止（超时）" if auto_stopped else "手动停止"
        print(f"\n{'='*50}")
        print(f"⏹️  停止录音，正在处理... ({stop_reason})")
        print(f"🌐 使用 Gemini-{config.GEMINI_TRANSCRIPTION_MODEL} 转录")
        print(f"{'='*50}")
        
        # 更新状态
        self.state = AppState.PROCESSING
        
        # 停止录音计时
        recording_time = self.timer.stop("recording")
        if recording_time:
            print(f"⏱️  录音时长: {self.timer.format_duration(recording_time.duration_ms)}")
        
        # 停止录音并获取完整音频
        final_audio = self.audio_recorder.stop_recording()
        self.current_session_audio = final_audio

        # 计算录音时长，判断是否需要跳过转录
        min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)
        recorded_seconds = 0.0
        if recording_time:
            recorded_seconds = max(recorded_seconds, recording_time.duration_ms / 1000.0)
        if final_audio is not None and len(final_audio) > 0:
            sample_rate = getattr(self.audio_recorder, "sample_rate", getattr(config, "SAMPLE_RATE", 16000))
            if sample_rate:
                recorded_seconds = max(recorded_seconds, len(final_audio) / float(sample_rate))

        if recorded_seconds <= min_duration:
            self._handle_short_recording_cancel(recorded_seconds, stop_reason)
            return

        # 使用重试管理器处理音频
        if final_audio is not None and len(final_audio) > 0:
            print("🎯 提交音频到重试管理器...")
            
            # 生成任务ID
            task_id = f"session_{int(time.time() * 1000)}"
            
            # 提交到重试管理器，标记为强制立即处理（新录音覆盖机制）
            self.retry_manager.submit_audio(
                audio_data=final_audio,
                task_id=task_id,
                force_immediate=True,  # 新录音强制立即处理
                metadata={
                    "session_start": self.recording_start_time,
                    "recording_duration": recording_time.duration_ms if recording_time else 0,
                    "stop_reason": stop_reason
                }
            )
            
            # 状态保持处理中，等待回调
            print("⏳ 等待转录完成...")
        else:
            print("❌ 未录制到有效音频")
            self._finish_session()

    def _handle_short_recording_cancel(self, recorded_seconds: float, stop_reason: str):
        """处理录音时长不足的情况"""
        min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)
        print(
            f"⚠️ 录音时长 {recorded_seconds:.2f}s（{stop_reason}），小于最短转录要求 {min_duration:.0f}s。"
        )
        print("ℹ️ 本次录音已取消提交 Gemini，请按住 Command 键继续说话。")

        if getattr(config, "ENABLE_NOTIFICATIONS", True):
            try:
                notification_manager.show_warning_notification(
                    f"录音时长 {recorded_seconds:.2f}s（{stop_reason}），小于最短转录要求 {min_duration:.0f}s，已取消本次转录。"
                )
            except Exception as exc:
                if config.DEBUG_MODE:
                    print(f"⚠️ 警告通知发送失败: {exc}")

        # 停止整体会话计时并重置状态
        self.timer.stop("total_session")
        self.timer.reset()

        self.state = AppState.IDLE
        self.final_transcript = None
        self.current_session_audio = None
        self.recording_start_time = None

        print(f"{'='*50}")
        print("等待下次录音...")
        print(f"{'='*50}\n")

    def _process_transcript_result(self, raw_transcript: str):
        """处理转录结果"""
        original_transcript = (raw_transcript or "").strip()

        # 第一时间把原始转录结果粘贴到光标位置
        if original_transcript:
            self._auto_paste_text(original_transcript)

        # 开始词典优化计时
        self.timer.start("dictionary_processing")
        
        # 创建类似原系统的数据结构
        transcript_data = [{'text': raw_transcript, 'start': 0.0, 'duration': 0.0}]
        
        # 应用用户词典优化
        optimized_transcript = self.dictionary_manager.process_transcript(transcript_data)
        
        # 停止词典优化计时
        dict_time = self.timer.stop("dictionary_processing")
        if dict_time:
            print(f"⏱️  词典处理耗时: {self.timer.format_duration(dict_time.duration_ms)}")
        
        # 提取优化后的文本
        combined_text = ""
        for entry in optimized_transcript:
            text = entry.get('text', '').strip()
            if text:
                combined_text += text + " "
        
        processed_text = combined_text.strip()
        
        # 复制原始转录到剪贴板
        if processed_text and config.ENABLE_CLIPBOARD:
            self.timer.start("clipboard_copy")
            
            try:
                pyperclip.copy(processed_text)
                clipboard_time = self.timer.stop("clipboard_copy")
                
                # 使用新的通知系统
                if config.ENABLE_NOTIFICATIONS:
                    notification_manager.show_clipboard_notification(processed_text, "Gemini转录")
                else:
                    if clipboard_time:
                        print(f"📋 转录结果已复制到剪贴板 ({self.timer.format_duration(clipboard_time.duration_ms)})")
                    else:
                        print("📋 转录结果已复制到剪贴板")
                        
            except Exception as e:
                self.timer.stop("clipboard_copy")
                if config.ENABLE_NOTIFICATIONS:
                    notification_manager.show_error_notification(f"复制到剪贴板失败: {e}")
                else:
                    print(f"⚠️  复制到剪贴板失败: {e}")
        
        # Gemini 纠错处理（如果启用且不同的模型）
        if (config.ENABLE_GEMINI_CORRECTION and 
            config.GEMINI_MODEL != config.GEMINI_TRANSCRIPTION_MODEL and 
            processed_text):
            
            print(f"🤖 使用 {config.GEMINI_MODEL} 进行纠错...")
            
            # 开始 Gemini 纠错计时
            self.timer.start("gemini_correction")
            
            corrected_text = self.gemini_corrector.correct_transcript(processed_text)
            
            # 停止 Gemini 纠错计时
            correction_time = self.timer.stop("gemini_correction")
            
            if corrected_text and corrected_text.strip() != processed_text:
                # 更新转录结果
                optimized_transcript = [{
                    'start': 0.0,
                    'duration': 0.0,
                    'text': corrected_text,
                    'gemini_transcribed': True,
                    'gemini_corrected': True
                }]
                
                # 用纠错后的文本覆盖剪贴板
                if config.ENABLE_CLIPBOARD:
                    self.timer.start("clipboard_update")
                    try:
                        pyperclip.copy(corrected_text.strip())
                        clipboard_update_time = self.timer.stop("clipboard_update")
                        
                        # 使用新的通知系统显示纠错完成
                        if config.ENABLE_NOTIFICATIONS:
                            notification_manager.show_clipboard_notification(corrected_text.strip(), "纠错完成")
                        else:
                            if correction_time and clipboard_update_time:
                                print(f"✅ Gemini纠错完成 ({self.timer.format_duration(correction_time.duration_ms)})，已更新剪贴板 ({self.timer.format_duration(clipboard_update_time.duration_ms)})")
                            else:
                                print("✅ Gemini纠错完成，已更新剪贴板")
                                
                    except Exception as e:
                        self.timer.stop("clipboard_update")
                        if config.ENABLE_NOTIFICATIONS:
                            notification_manager.show_error_notification(f"更新剪贴板失败: {e}")
                        else:
                            print(f"⚠️  更新剪贴板失败: {e}")
                else:
                    if correction_time:
                        print(f"✅ Gemini纠错完成 ({self.timer.format_duration(correction_time.duration_ms)})")
                    else:
                        print("✅ Gemini纠错完成")
            else:
                if correction_time:
                    print(f"ℹ️  无需纠错 ({self.timer.format_duration(correction_time.duration_ms)})，剪贴板保持原始内容")
                else:
                    print("ℹ️  无需纠错，剪贴板保持原始内容")
        
        self.final_transcript = optimized_transcript

        # 自动粘贴最终文本（仅在内容发生变化时更新）
        final_output_text = ""
        for entry in optimized_transcript:
            text = entry.get('text', '').strip()
            if text:
                if final_output_text:
                    final_output_text += " "
                final_output_text += text

        if final_output_text and final_output_text.strip() and final_output_text.strip() != original_transcript:
            self._auto_paste_text(final_output_text.strip())
        self._finish_session()
    
    def _finish_session(self):
        """完成会话处理"""
        self.state = AppState.COMPLETE
        
        # 如果使用新会话模式，从会话管理器获取结果
        if self.use_new_session_mode and hasattr(self, 'session_manager'):
            segments = self.session_manager.get_session_segments()
            if segments:
                # 构建与传统模式兼容的结果格式
                full_text = ""
                for segment in segments:
                    if hasattr(segment, 'final_text') and segment.final_text:
                        full_text += segment.final_text + " "
                
                if full_text.strip():
                    self.final_transcript = [{
                        'text': full_text.strip(),
                        'start': 0.0,
                        'duration': 0.0,
                        'gemini_transcribed': True,
                        'gemini_corrected': True
                    }]
        
        # 停止总计时
        total_time = self.timer.stop("total_session")
        
        # 显示最终结果
        self._display_final_results()

        # 显示详细计时统计
        self._display_timing_summary()
        
        # 重置状态
        self.state = AppState.IDLE
        if total_time:
            print(f"\n{'='*50}")
            print(f"✅ 转录完成，总耗时: {self.timer.format_duration(total_time.duration_ms)}")
            print(f"等待下次录音...")
            print(f"{'='*50}\n")
        else:
            print(f"\n{'='*50}")
            print(f"✅ 转录完成，等待下次录音...")
            print(f"{'='*50}\n")

    def _auto_paste_text(self, text: str):
        """尝试自动粘贴文本到当前光标位置"""
        cleaned = (text or "").strip()
        if not cleaned or not getattr(config, 'AUTO_PASTE_ENABLED', True):
            return

        manager = getattr(self, 'text_input_manager', None)
        if not manager:
            try:
                manager = TextInputManager()
                self.text_input_manager = manager
            except Exception as exc:
                print(f"⚠️ 自动粘贴初始化失败: {exc}")
                return

        method_str = getattr(config, 'TEXT_INPUT_METHOD', 'clipboard')
        if method_str == 'direct_type':
            method = InputMethod.DIRECT_TYPE
        elif method_str == 'clipboard':
            method = InputMethod.CLIPBOARD_PASTE
        else:
            return

        if self._last_autopaste_text and self._last_autopaste_text == cleaned:
            return

        request = InputRequest(
            text=cleaned,
            method=method,
            delay_before=max(getattr(config, 'TEXT_INPUT_DELAY', 0.1), 0.1),
            delay_after=0.1,
            backup_to_clipboard=True,
            request_id=f"auto_paste_{int(time.time() * 1000)}"
        )

        result = manager.input_text(request)
        if result != InputResult.SUCCESS:
            print(f"⚠️ 自动粘贴失败: {result.value}")
        else:
            self._last_autopaste_text = cleaned

    def _display_final_results(self):
        """显示最终转录结果"""
        print(f"\n\n{'='*60}")
        print(f"🎯 最终转录结果")
        print(f"{'='*60}")
        
        if self.final_transcript:
            # 显示结果
            full_text = ""
            gemini_transcribed = False
            gemini_corrected = False
            
            for entry in self.final_transcript:
                text = entry.get('text', '').strip()
                if text:
                    full_text += text + " "
                if entry.get('gemini_transcribed', False):
                    gemini_transcribed = True
                if entry.get('gemini_corrected', False):
                    gemini_corrected = True
            
            # 显示处理信息
            process_info = []
            if gemini_transcribed:
                process_info.append(f"Gemini-{config.GEMINI_TRANSCRIPTION_MODEL}转录")
            if gemini_corrected:
                process_info.append(f"{config.GEMINI_MODEL}纠错")
            
            process_text = " + ".join(process_info) if process_info else "Gemini转录"
            
            print(f"📝 完整转录内容 ({process_text}):")
            print(f"{'-'*50}")
            print(full_text.strip())
            print(f"{'-'*50}")
            
            # 显示替换统计
            if config.DEBUG_MODE:
                self._show_replacement_stats()
                
        else:
            print(f"❌ 未获取到转录结果")
            print(f"可能原因:")
            print(f"  - 录音时间过短")
            print(f"  - 音频质量不佳")
            print(f"  - Gemini API 连接问题")
        
        print(f"{'='*60}")
    
    def _show_replacement_stats(self):
        """显示词典替换统计"""
        if not self.final_transcript:
            return
        
        total_replacements = 0
        replacement_details = []
        
        for entry in self.final_transcript:
            if 'replacements' in entry:
                for repl in entry['replacements']:
                    total_replacements += 1
                    replacement_details.append(
                        f"  {repl['original']} → {repl['replacement']} "
                        f"(相似度: {repl['similarity']:.2f})"
                    )
        
        if total_replacements > 0:
            print(f"\n🔄 词典替换统计 (共 {total_replacements} 处):")
            for detail in replacement_details:
                print(detail)
    
    def _display_timing_summary(self):
        """显示计时统计摘要"""
        if config.DEBUG_MODE:
            self.timer.print_summary("⏱️  处理时间分析")
        else:
            # 简化显示主要步骤的时间
            timings = self.timer.get_all_timings()
            if timings:
                print(f"\n⏱️  处理时间:")
                for name, timing in timings.items():
                    if name in ["recording", "gemini_transcription", "gemini_correction"]:
                        print(f"  {self._format_timing_name(name)}: {self.timer.format_duration(timing.duration_ms)}")
    
    def _format_timing_name(self, name: str) -> str:
        """格式化计时器名称显示"""
        name_map = {
            "recording": "录音时长",
            "gemini_transcription": "Gemini转录",
            "gemini_correction": "Gemini纠错",
            "dictionary_processing": "词典处理",
            "clipboard_copy": "剪贴板复制",
            "clipboard_update": "剪贴板更新",
            "total_session": "总计时间"
        }
        return name_map.get(name, name)
    
    def _format_duration(self, seconds: int) -> str:
        """格式化时长显示"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        elif minutes > 0:
            return f"{minutes}分钟{secs}秒"
        else:
            return f"{secs}秒"
    
    # 超时监控相关方法（与原版相同）
    def _start_timeout_monitoring(self):
        """启动超时监控线程"""
        if self.timeout_thread is not None and self.timeout_thread.is_alive():
            return
        
        self.timeout_thread = threading.Thread(target=self._timeout_monitor_worker, daemon=True)
        self.timeout_thread.start()
    
    def _stop_timeout_monitoring(self):
        """停止超时监控"""
        if self.timeout_thread is not None:
            self.timeout_stop_event.set()
            if self.timeout_thread.is_alive():
                self.timeout_thread.join(timeout=1.0)
    
    def _timeout_monitor_worker(self):
        """超时监控工作线程"""
        while not self.timeout_stop_event.is_set() and self.state == AppState.RECORDING:
            if self.recording_start_time is None:
                break
            
            current_time = time.time()
            elapsed_time = current_time - self.recording_start_time
            
            # 检查是否需要显示警告
            if not self.warning_shown and elapsed_time >= config.WARNING_RECORDING_DURATION:
                self._show_recording_warning(elapsed_time)
                self.warning_shown = True
            
            # 检查是否超时
            if elapsed_time >= config.MAX_RECORDING_DURATION:
                self._handle_recording_timeout(elapsed_time)
                break
            
            # 等待检查间隔或停止事件
            self.timeout_stop_event.wait(config.TIMEOUT_CHECK_INTERVAL)
    
    def _show_recording_warning(self, elapsed_time: int):
        """显示录音时长警告"""
        remaining_time = config.MAX_RECORDING_DURATION - elapsed_time
        elapsed_text = self._format_duration(int(elapsed_time))
        remaining_text = self._format_duration(int(remaining_time))
        
        warning_msg = f"⚠️  录音时长警告: 已录音 {elapsed_text}，剩余 {remaining_text} 后将自动停止"
        print(f"\n{warning_msg}")
        
        # 发送通知
        if config.ENABLE_NOTIFICATIONS:
            try:
                notification_manager.show_warning_notification(warning_msg)
            except:
                pass
    
    def _handle_recording_timeout(self, elapsed_time: int):
        """处理录音超时"""
        elapsed_text = self._format_duration(int(elapsed_time))
        timeout_msg = f"🚨 录音超时: 已录音 {elapsed_text}，自动停止录音"
        print(f"\n{timeout_msg}")
        
        # 发送超时通知
        if config.ENABLE_NOTIFICATIONS:
            try:
                notification_manager.show_error_notification(timeout_msg)
            except:
                pass
        
        # 自动停止录音
        with self.state_lock:
            if self.state == AppState.RECORDING:
                self._stop_recording(auto_stopped=True)
    
    # ==================== 重试管理器回调函数 ====================
    
    def _transcription_callback(self, audio_data) -> Optional[str]:
        """重试管理器的转录回调函数"""
        try:
            # 开始转录计时
            self.timer.start("gemini_transcription")
            
            # 调用 Gemini 转录
            transcript = self.transcriber.transcribe_complete_audio(audio_data)
            
            # 停止转录计时
            gemini_time = self.timer.stop("gemini_transcription")
            if gemini_time:
                print(f"⏱️  Gemini转录耗时: {self.timer.format_duration(gemini_time.duration_ms)}")
            
            return transcript
            
        except Exception as e:
            self.timer.stop("gemini_transcription")
            print(f"❌ 转录回调异常: {e}")
            return None
    
    def _on_transcription_success(self, task_id: str, transcript: str):
        """转录成功回调"""
        print(f"✅ 任务 {task_id} 转录成功")
        
        # 如果当前状态是处理中，说明是当前会话的结果
        if self.state == AppState.PROCESSING:
            # 处理转录结果
            self._process_transcript_result(transcript)
        else:
            # 这是重试任务的成功结果，直接处理并通知
            print(f"🔄 重试任务成功: {transcript}")
            
            # 直接复制到剪贴板并通知
            if config.ENABLE_CLIPBOARD:
                try:
                    pyperclip.copy(transcript)
                    if config.ENABLE_NOTIFICATIONS:
                        notification_manager.show_clipboard_notification(transcript, "重试转录成功")
                    else:
                        print(f"📋 重试结果已复制到剪贴板: {transcript}")
                except Exception as e:
                    print(f"⚠️  复制重试结果失败: {e}")
    
    def _on_transcription_failure(self, task_id: str, error_message: str):
        """转录失败回调"""
        print(f"❌ 任务 {task_id} 最终失败: {error_message}")
        
        # 如果当前状态是处理中，说明是当前会话的失败
        if self.state == AppState.PROCESSING:
            print("❌ 当前录音转录失败，将在后台重试")
            # 完成当前会话，但重试会在后台继续
            self._finish_session()
        else:
            # 这是重试任务的最终失败
            if config.ENABLE_NOTIFICATIONS:
                notification_manager.show_error_notification(f"音频转录最终失败: {error_message}")
    
    # ==================== 原有方法 ====================
    
    def start(self):
        """启动应用"""
        if not self.transcriber.is_ready:
            print("❌ Gemini 转录器未准备就绪，请检查 API 配置")
            return False
        
        self.running = True
        
        # 根据模式启动相应服务
        if self.use_new_session_mode:
            # 新会话模式不需要额外启动服务，会话管理器会按需启动
            pass
        else:
            # 传统模式启动重试管理器
            self.retry_manager.start()
        
        # 启动快捷键监听
        if not self.hotkey_listener.start():
            print("❌ 快捷键监听启动失败")
            return False
        
        # 显示启动信息
        print("🚀 Gemini 语音转录系统已启动，按住 Command 键开始录音")
        print("按 Ctrl+C 退出程序")
        print("💡 提示: 录音结束后系统会自动复制并粘贴结果")
        
        # 显示重试管理器状态
        if not self.use_new_session_mode and config.DEBUG_MODE:
            self.retry_manager.print_status()
        
        # 显示设备信息
        if config.DEBUG_MODE:
            self.audio_recorder.get_device_info()
            
            # 显示 Gemini 转录器信息
            transcriber_info = self.transcriber.get_model_info()
            print(f"\n🤖 Gemini 转录器信息:")
            for key, value in transcriber_info.items():
                print(f"  {key}: {value}")
        
        try:
            # 主循环
            while self.running:
                time.sleep(1)
                
                # 显示状态
                if config.DEBUG_MODE:
                    print(f"\r状态: {self.state.value}", end='', flush=True)
        
        except KeyboardInterrupt:
            print(f"\n\n收到退出信号...")
        
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """停止应用"""
        print("正在关闭应用...")
        
        self.running = False
        
        # 停止超时监控
        self._stop_timeout_monitoring()
        
        # 如果正在录音，先停止
        if self.state == AppState.RECORDING:
            print("停止当前录音...")
            self._stop_recording()
        
        # 停止各个组件
        self.hotkey_listener.stop()
        
        if self.use_new_session_mode:
            # 如果使用新模式且正在录音，先停止会话
            if self.state == AppState.RECORDING:
                self.session_manager.stop_session()
        else:
            # 传统模式组件停止
            self.audio_recorder.stop_recording()
            self.transcriber.stop_processing()
            
            # 停止重试管理器
            self.retry_manager.stop()
        
        print("✅ 应用已关闭")


def signal_handler(sig, frame):
    """信号处理器"""
    print(f"\n收到信号 {sig}，正在退出...")
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("📱 使用传统一口气模式")

    # 创建并启动应用
    app = GeminiVoiceTranscriptionApp()
    
    try:
        success = app.start()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"❌ 应用运行错误: {e}")
        if config.DEBUG_MODE:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
