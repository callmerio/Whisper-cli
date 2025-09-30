#!/usr/bin/env python3
"""
基于 Gemini-2.5-Flash 的语音转录系统主程序
使用 Gemini 进行音频转录，支持可配置的长按热键控制录音
"""

import time
import signal
import sys
import json
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import threading
import queue
import pyperclip

# 导入各个模块
from hotkey_listener import HotkeyListener
from audio_recorder import AudioRecorder
from service_registry import get_transcriber, get_dictionary, get_corrector
from timer_utils import Timer
from notification_utils import notification_manager
from audio_retry_manager import audio_retry_manager  # 导入重试管理器

# 导入新的会话模式组件
from session_mode_manager import SessionModeManager, SessionMode, SessionState
from text_input_manager import TextInputManager, InputMethod, InputRequest, InputResult
from correction_memory import start_hotkey_listener, stop_hotkey_listener
import config

class AppState(Enum):
    """应用状态枚举"""
    IDLE = "待机"
    RECORDING = "录音中"
    PROCESSING = "处理中"
    COMPLETE = "完成"


@dataclass
class SessionContext:
    """多会话处理上下文"""
    session_id: str
    task_id: Optional[str]
    timer: Timer
    report: Dict[str, Any] = field(default_factory=dict)
    status: str = "recording"
    final_transcript: Optional[List[Dict[str, Any]]] = None
    last_autopaste_text: Optional[str] = None
    stop_reason: str = ""
    created_at: float = field(default_factory=time.time)
    recording_started_at: Optional[float] = None
    transcript_text: str = ""
    failure_reason: Optional[str] = None
    history_written: bool = False

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
            self.transcriber = get_transcriber()
            self.dictionary_manager = get_dictionary()
            self.gemini_corrector = get_corrector()
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
        self.hotkey_labels = list(dict.fromkeys(config.HOTKEY_DISPLAY_LABELS)) or [config.HOTKEY_PRIMARY_LABEL]
        self.primary_hotkey_label = config.HOTKEY_PRIMARY_LABEL
        self.hotkey_hint = " / ".join(self.hotkey_labels)
        self.timer = Timer()

        # 会话上下文管理
        self.active_session: Optional[SessionContext] = None
        self.session_contexts: Dict[str, SessionContext] = {}
        self.processing_order: List[str] = []
        self.latest_task_id: Optional[str] = None
        self.session_counter = 0
        self.history_file = Path(config.PROJECT_ROOT) / "logs" / "history.json"
        self.history_lock = threading.Lock()
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.write_text("[]", encoding="utf-8")
        self._global_last_autopaste_text: Optional[str] = None
        self.correction_hotkey_active = False

        # 运行标志
        self.running = False
        
        # 超时管理
        self.timeout_thread = None
        self.timeout_stop_event = threading.Event()
        self.warning_shown = False
        self.recording_start_time: Optional[float] = None

        # 热键动作异步执行队列，避免阻塞系统事件线程
        self._action_queue: "queue.Queue[Optional[Callable[[], None]]]" = queue.Queue()
        self._action_dispatcher_stop = threading.Event()
        self._action_worker = threading.Thread(
            target=self._process_action_queue,
            name="HotkeyActionWorker",
            daemon=True,
        )
        self._action_worker.start()

        # 热键健康检查节流
        self._last_hotkey_health_check = 0.0

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
快捷键: 按住 {self.hotkey_hint} 键（松开即停止）
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
        """录音热键长按触发回调"""
        self._schedule_action(self._handle_hotkey_press_action)

    def _on_hotkey_release(self):
        """录音热键松开回调"""
        self._schedule_action(self._handle_hotkey_release_action)

    def _handle_hotkey_press_action(self):
        should_start = False
        with self.state_lock:
            if self.state != AppState.RECORDING:
                should_start = True
            elif config.DEBUG_MODE:
                pending = len(self.processing_order)
                print(f"当前状态 {self.state.value}，忽略开始录音请求（后台处理中 {pending} 个任务）")
        if should_start:
            self._start_recording()

    def _handle_hotkey_release_action(self):
        should_stop = False
        with self.state_lock:
            if self.state == AppState.RECORDING:
                should_stop = True
            elif config.DEBUG_MODE:
                print(f"当前状态 {self.state.value}，忽略停止录音请求")
        if should_stop:
            self._stop_recording()

    def _schedule_action(self, action: Callable[[], None]) -> None:
        if self._action_dispatcher_stop.is_set():
            return
        self._action_queue.put(action)

    def _process_action_queue(self) -> None:
        while True:
            action = self._action_queue.get()
            try:
                if action is None:
                    return
                action()
            except Exception as exc:
                print(f"⚠️ 热键动作执行错误: {exc}")
            finally:
                self._action_queue.task_done()
    
    # ==================== 新会话模式回调函数 ====================
    
    def _on_session_start(self, mode: SessionMode):
        """会话开始回调"""
        print(f"🚀 {mode.value}会话已开始")
        
        if mode == SessionMode.REALTIME:
            print("💡 提示: 系统将在您停顿后自动处理语音并输出到光标位置")
            print(f"   松开 {self.primary_hotkey_label} 键可提前结束录音")
    
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

    def _create_session_context(self) -> SessionContext:
        """创建新的会话上下文"""
        self.session_counter += 1
        session_id = f"session_{int(time.time() * 1000)}_{self.session_counter}"
        timer = Timer()
        report = {
            "session_id": session_id,
            "task_id": None,
            "stop_reason": "",
            "recording": {},
            "transcription": {},
            "dictionary": {},
            "clipboard": {},
            "text": "",
            "original_text": "",
            "total_duration_ms": None,
            "created_at": time.time()
        }
        context = SessionContext(
            session_id=session_id,
            task_id=None,
            timer=timer,
            report=report,
            status="recording",
            recording_started_at=time.time()
        )
        return context

    def _is_latest_context(self, context: SessionContext) -> bool:
        """判断上下文是否为最新任务"""
        return bool(context.task_id and context.task_id == self.latest_task_id)

    def _append_history_entry(self, entry: Dict[str, Any]) -> None:
        """写入历史记录"""
        with self.history_lock:
            try:
                raw = self.history_file.read_text(encoding="utf-8")
                history = json.loads(raw) if raw.strip() else []
            except Exception:
                history = []

            history.append(entry)

            # 可选：限制历史条目数量，避免文件无限增长
            max_entries = getattr(config, "HISTORY_MAX_ENTRIES", 200)
            if len(history) > max_entries:
                history = history[-max_entries:]

            self.history_file.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _record_history_entry(self, context: SessionContext, text: str, reason: str) -> None:
        """将会话结果写入历史记录"""
        entry = {
            "session_id": context.session_id,
            "task_id": context.task_id,
            "text": text,
            "reason": reason,
            "created_at": context.created_at,
            "completed_at": time.time(),
            "stop_reason": context.stop_reason,
            "metadata": context.report.get("recording", {}),
        }
        self._append_history_entry(entry)
    
    def _start_recording(self):
        """开始录音"""
        if self.state == AppState.RECORDING:
            return
        
        if self.use_new_session_mode:
            # 使用新的会话模式管理器
            success = self.session_manager.start_session(self.session_mode)
            if success:
                self.state = AppState.RECORDING
                self._global_last_autopaste_text = None
                print(f"\n{'='*50}")
                print(f"🎤 开始{self.session_mode.value}...")
                if self.session_mode == SessionMode.REALTIME:
                    silence_duration = getattr(config, 'VAD_SILENCE_DURATION', 4.0)
                    print(f"🔇 静音检测: {silence_duration}秒后自动分段")
                    print(f"📝 自动输出: 转录完成后直接输入到光标位置")
                print(f"⏹️ 松开 {self.primary_hotkey_label} 键停止")
                print(f"{'='*50}")
            else:
                print("❌ 录音启动失败")
            return
        
        # 传统模式逻辑
        context = self._create_session_context()
        self.active_session = context
        self.timer = context.timer
        self._global_last_autopaste_text = None

        max_duration_text = self._format_duration(config.MAX_RECORDING_DURATION)
        print(f"\n{'='*50}")
        print(f"🎤 开始录音... (松开 {self.primary_hotkey_label} 键停止)")
        print(f"⏰ 最大录音时长: {max_duration_text}")
        print(f"🌐 转录引擎: Gemini-{config.GEMINI_TRANSCRIPTION_MODEL}")
        print(f"{'='*50}")
        
        # 重置超时相关状态
        self.warning_shown = False
        self.timeout_stop_event.clear()
        context.recording_started_at = time.time()
        self.recording_start_time = context.recording_started_at

        # 重置计时器并开始录音计时
        context.timer.reset()
        context.report.update({
            "task_id": None,
            "stop_reason": "",
            "recording": {},
            "transcription": {},
            "dictionary": {},
            "clipboard": {},
            "text": "",
            "original_text": "",
            "total_duration_ms": None
        })
        context.timer.start("total_session")
        context.timer.start("recording")

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
            context.timer.reset()
            self._stop_timeout_monitoring()
            self.active_session = None
            self.recording_start_time = None
    
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
            self.recording_start_time = None
            return

        # 传统模式逻辑
        context = self.active_session
        if not context:
            if config.DEBUG_MODE:
                print("⚠️ 未找到活跃会话上下文，忽略停止请求")
            return

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
        recording_time = context.timer.stop("recording")
        recording_duration_ms = recording_time.duration_ms if recording_time else None
        if recording_duration_ms is not None:
            print(f"⏱️  录音时长: {context.timer.format_duration(recording_duration_ms)}")

        # 停止录音并获取完整音频
        final_audio = self.audio_recorder.stop_recording()

        stats = self.audio_recorder.get_recording_stats()
        sample_rate = getattr(self.audio_recorder, "sample_rate", getattr(config, "SAMPLE_RATE", 16000))
        frame_count = stats.get("total_frames", 0)
        chunk_count = stats.get("chunk_count", 0)
        audio_seconds = stats.get("duration_seconds", 0.0)

        if final_audio is not None and len(final_audio) > 0:
            frame_count = len(final_audio)
            if sample_rate:
                audio_seconds = frame_count / float(sample_rate)

        context.stop_reason = stop_reason
        context.report["stop_reason"] = stop_reason
        context.report["recording"] = {
            "timer_duration_ms": recording_duration_ms,
            "audio_seconds": audio_seconds,
            "chunk_count": chunk_count,
            "frame_count": frame_count,
        }

        if final_audio is not None and len(final_audio) > 0:
            context.report["recording"]["raw_kb"] = final_audio.nbytes / 1024

        # 计算录音时长，判断是否需要跳过转录
        min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)
        recorded_seconds = 0.0
        if recording_time:
            recorded_seconds = max(recorded_seconds, recording_time.duration_ms / 1000.0)
        if audio_seconds:
            recorded_seconds = max(recorded_seconds, audio_seconds)

        if recorded_seconds <= min_duration:
            self._handle_short_recording_cancel(context, recorded_seconds, stop_reason)
            self.recording_start_time = None
            return

        # 使用重试管理器处理音频
        if final_audio is not None and len(final_audio) > 0:
            print("🎯 提交音频到重试管理器...")
            
            # 生成任务ID（复用会话ID确保唯一性）
            task_id = context.session_id
            context.task_id = task_id
            context.report["task_id"] = task_id
            
            # 提交到重试管理器，标记为强制立即处理（新录音覆盖机制）
            self.retry_manager.submit_audio(
                audio_data=final_audio,
                task_id=task_id,
                force_immediate=True,  # 新录音强制立即处理
                metadata={
                    "session_start": context.recording_started_at,
                    "recording_duration": recording_time.duration_ms if recording_time else 0,
                    "stop_reason": stop_reason
                }
            )
            
            # 状态保持处理中，等待回调
            print("⏳ 等待转录完成...")
            context.status = "processing"
            self.session_contexts[task_id] = context
            if task_id in self.processing_order:
                self.processing_order.remove(task_id)
            self.processing_order.append(task_id)
            self.latest_task_id = task_id
            self.active_session = None
            
            # 允许下一次录音
            self.state = AppState.IDLE
        else:
            print("❌ 未录制到有效音频")
            self._finalize_session_with_failure(context, "未录制到有效音频")
            self.recording_start_time = None

    def _handle_short_recording_cancel(self, context: SessionContext, recorded_seconds: float, stop_reason: str):
        """处理录音时长不足的情况"""
        min_duration = getattr(config, "MIN_TRANSCRIPTION_DURATION", 2.0)

        context.report["stop_reason"] = stop_reason
        context.report.setdefault("recording", {})["audio_seconds"] = recorded_seconds
        context.report["cancelled"] = True
        context.status = "cancelled"
        self.state = AppState.IDLE
        self.active_session = None
        self.recording_start_time = None

        self._finalize_context(context, "", None)

    def _process_transcript_result(self, context: SessionContext, raw_transcript: str) -> str:
        """处理转录结果，返回最终文本"""
        original_transcript = (raw_transcript or "").strip()
        context.report["original_text"] = original_transcript

        # 词典处理
        context.timer.start("dictionary_processing")
        transcript_data = [{'text': raw_transcript, 'start': 0.0, 'duration': 0.0}]
        optimized_transcript = self.dictionary_manager.process_transcript(transcript_data)
        dict_time = context.timer.stop("dictionary_processing")

        dictionary_report = context.report.setdefault("dictionary", {})
        if dict_time:
            duration_ms = dict_time.duration_ms
            print(f"⏱️  词典处理耗时: {self._format_duration_ms_value(duration_ms)}")
            dictionary_report["duration_ms"] = duration_ms
        dictionary_report["replacements"] = sum(len(entry.get('replacements', [])) for entry in optimized_transcript)
        dictionary_report["enabled"] = getattr(config, "SEGMENT_ENABLE_DICTIONARY", True)

        combined_text = ""
        for entry in optimized_transcript:
            text = entry.get('text', '').strip()
            if text:
                combined_text += text + " "
        processed_text = combined_text.strip()
        context.report["text"] = processed_text

        # 剪贴板处理（仅限最新任务）
        if processed_text and config.ENABLE_CLIPBOARD and self._is_latest_context(context):
            context.timer.start("clipboard_copy")
            try:
                pyperclip.copy(processed_text)
                clipboard_time = context.timer.stop("clipboard_copy")
                clipboard_duration_ms = clipboard_time.duration_ms if clipboard_time else None
                clipboard_report = context.report.setdefault("clipboard", {})
                clipboard_report.update({
                    "copied": True,
                    "char_count": len(processed_text),
                    "word_count": len(processed_text.split()),
                    "duration_ms": clipboard_duration_ms,
                    "mode": getattr(config, 'TEXT_INPUT_METHOD', 'clipboard')
                })
                if config.ENABLE_NOTIFICATIONS:
                    notification_manager.show_clipboard_notification(processed_text, "Gemini转录")
                elif clipboard_time:
                    print(f"📋 转录结果已复制到剪贴板 ({self._format_duration_ms_value(clipboard_time.duration_ms)})")
                else:
                    print("📋 转录结果已复制到剪贴板")
            except Exception as e:
                context.timer.stop("clipboard_copy")
                clipboard_report = context.report.setdefault("clipboard", {})
                clipboard_report.update({
                    "copied": False,
                    "error": str(e)
                })
                if config.ENABLE_NOTIFICATIONS:
                    notification_manager.show_error_notification(f"复制到剪贴板失败: {e}")
                else:
                    print(f"⚠️  复制到剪贴板失败: {e}")

        # Gemini 纠错
        correction_applied = False
        if (config.ENABLE_GEMINI_CORRECTION and
                config.GEMINI_MODEL != config.GEMINI_TRANSCRIPTION_MODEL and
                processed_text):
            print(f"🤖 使用 {config.GEMINI_MODEL} 进行纠错...")
            context.timer.start("gemini_correction")
            corrected_text = self.gemini_corrector.correct_transcript(processed_text)
            correction_time = context.timer.stop("gemini_correction")

            if corrected_text and corrected_text.strip() != processed_text:
                optimized_transcript = [{
                    'start': 0.0,
                    'duration': 0.0,
                    'text': corrected_text,
                    'gemini_transcribed': True,
                    'gemini_corrected': True
                }]
                correction_applied = True
                if config.ENABLE_CLIPBOARD and self._is_latest_context(context):
                    context.timer.start("clipboard_update")
                    try:
                        corrected_clean = corrected_text.strip()
                        pyperclip.copy(corrected_clean)
                        clipboard_update_time = context.timer.stop("clipboard_update")
                        clipboard_update_duration = clipboard_update_time.duration_ms if clipboard_update_time else None
                        clipboard_report = context.report.setdefault("clipboard", {})
                        clipboard_report.update({
                            "copied": True,
                            "char_count": len(corrected_clean),
                            "word_count": len(corrected_clean.split()),
                            "duration_ms": clipboard_update_duration if clipboard_update_duration is not None else clipboard_report.get("duration_ms"),
                            "mode": getattr(config, 'TEXT_INPUT_METHOD', 'clipboard'),
                            "correction": True
                        })
                        if config.ENABLE_NOTIFICATIONS:
                            notification_manager.show_clipboard_notification(corrected_clean, "纠错完成")
                        elif correction_time and clipboard_update_time:
                            print(
                                f"✅ Gemini纠错完成 ({self._format_duration_ms_value(correction_time.duration_ms)})，"
                                f"已更新剪贴板 ({self._format_duration_ms_value(clipboard_update_time.duration_ms)})"
                            )
                        else:
                            print("✅ Gemini纠错完成，已更新剪贴板")
                    except Exception as e:
                        context.timer.stop("clipboard_update")
                        clipboard_report = context.report.setdefault("clipboard", {})
                        clipboard_report.update({
                            "copied": False,
                            "error": str(e)
                        })
                        if config.ENABLE_NOTIFICATIONS:
                            notification_manager.show_error_notification(f"更新剪贴板失败: {e}")
                        else:
                            print(f"⚠️  更新剪贴板失败: {e}")
                else:
                    if correction_time:
                        print(f"✅ Gemini纠错完成 ({self._format_duration_ms_value(correction_time.duration_ms)})")
                    else:
                        print("✅ Gemini纠错完成")
            else:
                if correction_time:
                    print(f"ℹ️  无需纠错 ({self._format_duration_ms_value(correction_time.duration_ms)})，剪贴板保持原始内容")
                else:
                    print("ℹ️  无需纠错，剪贴板保持原始内容")

        context.report["correction_applied"] = correction_applied
        context.final_transcript = optimized_transcript

        final_output_text = ""
        for entry in optimized_transcript:
            text = entry.get('text', '').strip()
            if text:
                if final_output_text:
                    final_output_text += " "
                final_output_text += text

        final_clean = final_output_text.strip()
        if not final_clean:
            final_clean = processed_text or ""

        if final_clean and self._is_latest_context(context):
            self._auto_paste_text(context, final_clean)

        if final_clean:
            context.report["text"] = final_output_text.strip()
            context.transcript_text = final_clean
        else:
            fallback_text = original_transcript
            context.transcript_text = fallback_text
            if fallback_text and self._is_latest_context(context):
                self._auto_paste_text(context, fallback_text)

        return context.transcript_text
    
    def _finalize_context(self, context: SessionContext, final_text: Optional[str], failure_reason: Optional[str] = None):
        """完成会话处理并输出总结"""
        if failure_reason:
            context.failure_reason = failure_reason
            context.report["failure"] = failure_reason
            context.status = "failed"
        elif context.status != "cancelled":
            context.status = "complete"

        total_time = context.timer.stop("total_session")
        if total_time:
            context.report["total_duration_ms"] = total_time.duration_ms

        timings_raw = context.timer.get_all_timings()
        context.report["timings"] = {
            name: timing.duration_ms for name, timing in timings_raw.items()
        }

        if self._is_latest_context(context):
            self.final_transcript = context.final_transcript

        self._display_final_results(context)

        if config.DEBUG_MODE:
            self._display_timing_summary(context)

        reason = failure_reason or context.status
        history_text = final_text or context.transcript_text or ""
        self._record_history_entry(context, history_text, reason)
        context.history_written = True

        if context.task_id and context.task_id in self.session_contexts:
            del self.session_contexts[context.task_id]
        if context.task_id and context.task_id in self.processing_order:
            self.processing_order.remove(context.task_id)

        if self.active_session and self.active_session.session_id == context.session_id:
            self.active_session = None

        self.state = AppState.IDLE
        self.recording_start_time = None
        summary_duration = context.report.get("total_duration_ms")
        print(f"\n{'='*50}")
        duration_text = self._format_duration_ms_value(summary_duration)
        if failure_reason:
            print(f"❌ 任务 {context.session_id} 处理完成（失败: {failure_reason}，耗时 {duration_text}）")
        elif context.status == "cancelled":
            print(f"⚠️  任务 {context.session_id} 已取消，耗时 {duration_text}")
        else:
            print(f"✅ 任务 {context.session_id} 处理完成，耗时 {duration_text}")
        print("等待下次录音...")
        print(f"{'='*50}\n")

    def _finalize_session_with_failure(self, context: SessionContext, reason: str):
        """快捷处理失败会话"""
        context.failure_reason = reason
        context.report["failure"] = reason
        context.status = "failed"
        self._finalize_context(context, context.transcript_text, reason)

    def _finish_session(self):
        """兼容新会话模式的收尾逻辑"""
        self.state = AppState.IDLE
        if not self.use_new_session_mode or not hasattr(self, 'session_manager'):
            return

        segments = self.session_manager.get_session_segments()
        if not segments:
            print("🔚 会话结束，未获取到分段结果")
            return

        full_text = ""
        for segment in segments:
            if hasattr(segment, 'final_text') and segment.final_text:
                full_text += segment.final_text + " "

        full_text = full_text.strip()
        print(f"✅ 会话处理完成，共 {len(segments)} 个分段")
        if full_text:
            print("-" * 60)
            print(full_text)
            print("-" * 60)
        if config.ENABLE_CLIPBOARD:
            try:
                pyperclip.copy(full_text)
                if config.ENABLE_NOTIFICATIONS:
                    notification_manager.show_clipboard_notification(full_text, "会话完成")
            except Exception as exc:
                print(f"⚠️ 会话结果复制剪贴板失败: {exc}")

        # 一口气模式下也尝试自动粘贴最终文本
        if full_text and getattr(config, 'AUTO_PASTE_ENABLED', True):
            context = None
            if self.latest_task_id:
                context = self.session_contexts.get(self.latest_task_id)

            if not context and self.processing_order:
                for task_id in reversed(self.processing_order):
                    possible = self.session_contexts.get(task_id)
                    if possible:
                        context = possible
                        break

            if not context and self.session_contexts:
                context = next(iter(self.session_contexts.values()))

            if not context:
                context = SessionContext(
                    session_id=f"session_autopaste_{int(time.time() * 1000)}",
                    task_id=self.latest_task_id or None,
                    timer=Timer(),
                )

            pasted = self._auto_paste_text(context, full_text, force=True)
            if pasted:
                context.last_autopaste_text = full_text
                self._global_last_autopaste_text = full_text

    def _auto_paste_text(self, context: SessionContext, text: str, force: bool = False) -> bool:
        """尝试自动粘贴文本到当前光标位置，返回是否成功"""
        if not force and not self._is_latest_context(context):
            return False

        cleaned = (text or "").strip()
        if not cleaned or not getattr(config, 'AUTO_PASTE_ENABLED', True):
            return False

        manager = getattr(self, 'text_input_manager', None)
        if not manager:
            try:
                manager = TextInputManager()
                self.text_input_manager = manager
            except Exception as exc:
                print(f"⚠️ 自动粘贴初始化失败: {exc}")
                return False

        method_str = getattr(config, 'TEXT_INPUT_METHOD', 'clipboard')
        if method_str == 'direct_type':
            method = InputMethod.DIRECT_TYPE
        elif method_str == 'clipboard':
            method = InputMethod.CLIPBOARD_PASTE
        else:
            return False

        sanitized = cleaned
        if method == InputMethod.CLIPBOARD_PASTE and hasattr(manager, '_sanitize_clipboard_text'):
            try:
                sanitized_candidate = manager._sanitize_clipboard_text(cleaned)
                if sanitized_candidate:
                    sanitized = sanitized_candidate
            except Exception:
                sanitized = cleaned

        if context.last_autopaste_text and context.last_autopaste_text == sanitized:
            return True
        if self._global_last_autopaste_text and self._global_last_autopaste_text == sanitized:
            return True

        request = InputRequest(
            text=sanitized,
            method=method,
            delay_before=max(getattr(config, 'TEXT_INPUT_DELAY', 0.1), 0.1),
            delay_after=0.1,
            backup_to_clipboard=True,
            request_id=f"auto_paste_{int(time.time() * 1000)}"
        )

        result = manager.input_text(request)
        autopaste_report = context.report.setdefault("autopaste", {})
        if result != InputResult.SUCCESS:
            print(f"⚠️ 自动粘贴失败: {result.value}")
            autopaste_report.update({
                "performed": False,
                "error": result.value,
                "method": method.name.lower()
            })
            return False

        context.last_autopaste_text = sanitized
        self._global_last_autopaste_text = sanitized
        autopaste_report.update({
            "performed": True,
            "method": method.name.lower()
        })
        return True

    def _display_final_results(self, context: SessionContext):
        """显示最终转录结果"""
        report = context.report or {}
        border = "═" * 60
        print(f"\n{border}")
        print(f"🎯 会话报告".center(60))
        print(border)

        if report.get("cancelled"):
            print(f"⚠️  会话已取消: 录音时长不足 ({report.get('stop_reason', '未知原因')})")
            print(border)
            return

        failure = report.get("failure") or context.failure_reason
        if failure:
            print(f"❌ 转录失败: {failure}")

        task_id = report.get("task_id") or context.task_id or "-"
        stop_reason = report.get("stop_reason") or "-"
        total_duration = self._format_duration_ms_value(report.get("total_duration_ms"))
        print(f"🆔 任务: {task_id} · 结束方式: {stop_reason}")
        print(f"⏱️ 总耗时: {total_duration}")

        recording_info = report.get("recording", {})
        rec_duration = self._format_duration_ms_value(recording_info.get("timer_duration_ms"))
        rec_audio_seconds = self._format_seconds_float(recording_info.get("audio_seconds"))
        rec_chunks = recording_info.get("chunk_count")
        rec_frames = recording_info.get("frame_count")
        rec_raw = recording_info.get("raw_kb")
        rec_parts = [
            f"热键 {rec_duration}" if rec_duration != "-" else None,
            f"音频 {rec_audio_seconds}" if rec_audio_seconds != "-" else None,
            f"分块 {rec_chunks}" if rec_chunks else None,
            f"帧 {rec_frames}" if rec_frames else None,
            f"原始 {rec_raw:.1f}KB" if rec_raw is not None else None,
        ]
        rec_line = self._join_summary_parts(rec_parts)
        if rec_line:
            print(f"🎙️ {rec_line}")

        trans_info = report.get("transcription", {})
        trans_duration = self._format_duration_ms_value(trans_info.get("duration_ms"))
        compressed = trans_info.get("compressed_kb")
        attempts = trans_info.get("api_attempts") or 0
        strategy = self._format_strategy(trans_info.get("strategy"), trans_info.get("payload_type"))
        trans_parts = [
            f"Gemini-{config.GEMINI_TRANSCRIPTION_MODEL}",
            f"耗时 {trans_duration}" if trans_duration != "-" else None,
            strategy,
            f"压缩 {compressed:.1f}KB" if compressed is not None else None,
            f"尝试 {attempts} 次" if attempts else None,
            f"分片 {trans_info.get('chunks_success', 0)}/{trans_info.get('chunks_total')}" if trans_info.get("chunks_total") else None,
            f"文本 {trans_info.get('transcript_chars')} 字" if trans_info.get("transcript_chars") else None,
        ]
        trans_line = self._join_summary_parts(trans_parts)
        if trans_line:
            print(f"🤖 {trans_line}")

        dictionary_info = report.get("dictionary", {})
        dict_duration = self._format_duration_ms_value(dictionary_info.get("duration_ms"))
        replacements = dictionary_info.get("replacements") or 0
        if dictionary_info:
            dict_parts = [
                f"耗时 {dict_duration}" if dict_duration != "-" else None,
                f"替换 {replacements} 处",
            ]
            dict_line = self._join_summary_parts(dict_parts)
            if dict_line:
                print(f"📚 词典优化 | {dict_line}")

        clipboard_info = report.get("clipboard", {})
        if clipboard_info:
            clip_status = "已复制" if clipboard_info.get("copied") else "失败"
            clip_duration = self._format_duration_ms_value(clipboard_info.get("duration_ms"))
            char_count = clipboard_info.get("char_count") or 0
            word_count = clipboard_info.get("word_count") or 0
            clip_parts = [
                clip_status,
                f"耗时 {clip_duration}" if clip_duration != "-" else None,
                f"字符 {char_count}" if char_count else None,
                f"词数 {word_count}" if word_count else None,
                "来源 纠错" if clipboard_info.get("correction") else None,
            ]
            clip_line = self._join_summary_parts(clip_parts)
            if clip_line:
                print(f"📋 剪贴板 | {clip_line}")

        autopaste_info = report.get("autopaste", {})
        if autopaste_info.get("performed"):
            method = autopaste_info.get('method') or 'unknown'
            print(f"✍️ 自动粘贴 | 成功 · 方法 {method}")
        elif autopaste_info:
            print(f"✍️ 自动粘贴 | 失败 · {autopaste_info.get('error')}")

        final_text = report.get("text") or self._collect_final_text_fallback(context)

        if final_text:
            print("-" * 60)
            print(final_text)
            print("-" * 60)
            if config.DEBUG_MODE:
                self._show_replacement_stats(context)
        else:
            print("❌ 未获取到转录结果")
            print("可能原因: 录音过短 / 音频质量不足 / 网络异常")

        print(border)

    def _show_replacement_stats(self, context: SessionContext):
        """显示词典替换统计"""
        if not context.final_transcript:
            return
        
        total_replacements = 0
        replacement_details = []
        
        for entry in context.final_transcript:
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
    
    def _display_timing_summary(self, context: SessionContext):
        """显示计时统计摘要"""
        if config.DEBUG_MODE:
            context.timer.print_summary("⏱️  处理时间分析")
        else:
            timings = context.timer.get_all_timings()
            if timings:
                print(f"\n⏱️  处理时间:")
                for name, timing in timings.items():
                    if name in ["recording", "gemini_transcription", "gemini_correction"]:
                        print(f"  {self._format_timing_name(name)}: {self._format_duration_ms_value(timing.duration_ms)}")
    
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
    
    @staticmethod
    def _format_duration_ms_value(duration_ms: Optional[float]) -> str:
        """将毫秒格式化为易读文本"""
        if duration_ms is None:
            return "-"
        if duration_ms < 1000:
            return f"{duration_ms:.1f}ms"
        return f"{duration_ms/1000:.2f}s ({duration_ms:.1f}ms)"

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

    def _format_seconds_float(self, seconds: Optional[float]) -> str:
        """格式化浮点秒"""
        if seconds is None or seconds <= 0:
            return "-"
        if seconds < 60:
            return f"{seconds:.2f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        if minutes < 60:
            return f"{minutes}分{secs:.1f}秒"
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}小时{minutes}分{secs:.0f}秒"

    def _format_strategy(self, strategy: Optional[str], payload: Optional[str]) -> Optional[str]:
        """格式化转录策略"""
        mapping = {
            "single": "短音频",
            "compressed": "压缩",
            "chunked": "分片"
        }
        selected = strategy or payload
        if not selected:
            return None
        return mapping.get(selected, selected)

    @staticmethod
    def _join_summary_parts(parts: List[Optional[str]]) -> str:
        """将部分指标拼接为易读行"""
        filtered = [part for part in parts if part]
        return " | ".join(filtered)

    def _collect_final_text_fallback(self, context: SessionContext) -> str:
        """从最终转录结构提取文本"""
        if not context.final_transcript:
            return ""
        full_text = ""
        for entry in context.final_transcript:
            text = entry.get('text', '').strip()
            if text:
                if full_text:
                    full_text += " "
                full_text += text
        return full_text
    
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
        # 现在保持静默，避免打扰用户
        # 仍旧保留方法以兼容调用链
        return
    
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
        should_stop = False
        with self.state_lock:
            if self.state == AppState.RECORDING:
                should_stop = True
        if should_stop:
            self._schedule_action(lambda: self._stop_recording(auto_stopped=True))
    
    # ==================== 重试管理器回调函数 ====================
    
    def _transcription_callback(self, audio_data) -> Optional[str]:
        """重试管理器的转录回调函数"""
        try:
            active_task = getattr(self.retry_manager, "active_task", None)
            context = None
            if active_task:
                context = self.session_contexts.get(active_task.task_id)

            timer = context.timer if context else self.timer
            report = context.report.setdefault("transcription", {}) if context else {}

            # 开始转录计时
            timer.start("gemini_transcription")
            audio_seconds = 0.0
            if audio_data is not None and hasattr(audio_data, "__len__"):
                audio_seconds = len(audio_data) / float(getattr(config, "SAMPLE_RATE", 16000))
            if context:
                report["audio_seconds"] = audio_seconds
            
            # 调用 Gemini 转录
            transcript = self.transcriber.transcribe_complete_audio(audio_data)
            
            # 停止转录计时
            gemini_time = timer.stop("gemini_transcription")
            if gemini_time:
                duration_ms = gemini_time.duration_ms
                if context:
                    report["duration_ms"] = duration_ms
                print(f"⏱️  Gemini转录耗时: {self._format_duration_ms_value(duration_ms)}")

            # 记录本次转录的其他信息
            run_info = getattr(self.transcriber, "last_run_info", {}) or {}
            if context:
                for key in ["strategy", "compressed_kb", "transcript_chars", "api_attempts", "payload_type", "chunks_total", "chunks_success", "model"]:
                    if key in run_info:
                        report[key] = run_info.get(key)
            
            return transcript
            
        except Exception as e:
            try:
                timer.stop("gemini_transcription")
            except Exception:
                pass
            print(f"❌ 转录回调异常: {e}")
            return None
    
    def _on_transcription_success(self, task_id: str, transcript: str):
        """转录成功回调"""
        print(f"✅ 任务 {task_id} 转录成功")

        context = self.session_contexts.get(task_id)
        if not context and self.active_session and self.active_session.session_id == task_id:
            context = self.active_session

        if not transcript:
            print("⚠️ 转录结果为空，跳过自动粘贴")

        if context:
            if not transcript:
                self._finalize_context(context, "", "empty_transcript")
                return

            final_text = self._process_transcript_result(context, transcript)

            if not self._is_latest_context(context):
                print("📦 历史队列任务完成：结果已写入 history.json，未触发自动粘贴")

            self._finalize_context(context, final_text)
            return

        # 无上下文的兼容处理（如旧版本遗留任务）
        if transcript and config.ENABLE_CLIPBOARD:
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

        context = self.session_contexts.get(task_id)
        if not context and self.active_session and self.active_session.session_id == task_id:
            context = self.active_session

        if context:
            context.failure_reason = error_message
            if not self._is_latest_context(context):
                print("📦 历史队列任务失败：错误信息已写入 history.json")
            self._finalize_context(context, context.transcript_text, error_message)
            return

        if config.ENABLE_NOTIFICATIONS:
            notification_manager.show_error_notification(f"音频转录最终失败: {error_message}")
    
    # ==================== 原有方法 ====================
    
    def start(self):
        """启动应用"""
        if not self.transcriber.is_ready:
            print("❌ Gemini 转录器未准备就绪，请检查 API 配置")
            return False

        healthy, health_error = self.transcriber.check_health()
        if not healthy:
            print(f"❌ Gemini 服务自检失败: {health_error}")
            if "401" in health_error or "UNAUTHORIZED" in health_error.upper():
                print("ℹ️ 提示: 请检查 GEMINI_API_KEY、代理配置或自建网关的鉴权设置。")
            if config.ENABLE_NOTIFICATIONS:
                try:
                    notification_manager.show_error_notification(f"Gemini 自检失败: {health_error}")
                except Exception as exc:
                    if config.DEBUG_MODE:
                        print(f"通知发送失败: {exc}")
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

        if getattr(config, "ENABLE_CORRECTION_MEMORY", False):
            memory_hotkey = getattr(config, "CORRECTION_MEMORY_HOTKEY", "<cmd>+<shift>+m")
            self.correction_hotkey_active = start_hotkey_listener(memory_hotkey)
            if not self.correction_hotkey_active:
                print(f"⚠️ 纠错记忆热键未启用，请确认依赖和快捷键格式（当前: {memory_hotkey}）")

        # 显示启动信息
        print(f"🚀 Gemini 语音转录系统已启动，按住 {self.hotkey_hint} 键开始录音")
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

                now = time.time()
                if now - self._last_hotkey_health_check >= 3.0:
                    self._last_hotkey_health_check = now
                    self.hotkey_listener.ensure_running()
                
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

        if self.correction_hotkey_active:
            stop_hotkey_listener()
            self.correction_hotkey_active = False

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
        
        if not self._action_dispatcher_stop.is_set():
            self._action_dispatcher_stop.set()
            self._action_queue.put(None)
            try:
                self._action_worker.join(timeout=1.0)
            except RuntimeError:
                pass

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
