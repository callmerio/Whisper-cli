#!/usr/bin/env python3
"""
实时语音转录系统主程序
支持 Option+R 快捷键控制，实时转录和用户词典优化
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
from transcriber import WhisperTranscriber
from dictionary_manager import DictionaryManager
from gemini_corrector import GeminiCorrector
from timer_utils import Timer
import config

class AppState(Enum):
    """应用状态枚举"""
    IDLE = "待机"
    RECORDING = "录音中"
    PROCESSING = "处理中"
    COMPLETE = "完成"

class VoiceTranscriptionApp:
    def __init__(self):
        """初始化语音转录应用"""
        self.state = AppState.IDLE
        self.state_lock = threading.Lock()
        
        # 组件初始化
        self.hotkey_listener = HotkeyListener(self._on_hotkey_pressed)
        self.audio_recorder = AudioRecorder()
        self.transcriber = WhisperTranscriber()
        self.dictionary_manager = DictionaryManager()
        self.gemini_corrector = GeminiCorrector()
        self.timer = Timer()  # 计时器
        
        # 转录数据
        self.current_session_audio = None
        self.partial_transcripts = []  # 存储所有部分转录文本
        self.final_transcript = None
        self.all_transcript_segments = []  # 存储所有转录片段
        
        # 运行标志
        self.running = False
        
        clipboard_status = "✅" if config.ENABLE_CLIPBOARD else "❌"
        gemini_status = "✅" if config.ENABLE_GEMINI_CORRECTION and self.gemini_corrector.is_ready else "❌"
        
        print(f"""
🎤 实时语音转录系统 v1.0
================================
快捷键: 双击 Option 键 (切换录音)
状态: {self.state.value}
模型: {config.WHISPER_MODEL}
词典: {len(self.dictionary_manager.user_dict)} 个词汇
剪贴板: {clipboard_status}
Gemini纠错: {gemini_status}
================================
        """)
    
    def _on_hotkey_pressed(self):
        """快捷键按下回调"""
        with self.state_lock:
            if self.state == AppState.IDLE:
                self._start_recording()
            elif self.state == AppState.RECORDING:
                self._stop_recording()
            else:
                print(f"当前状态 {self.state.value}，无法切换")
    
    def _start_recording(self):
        """开始录音"""
        if self.state != AppState.IDLE:
            return
        
        print(f"\n{'='*50}")
        print(f"🎤 开始录音... (再次双击 Option 键停止)")
        print(f"{'='*50}")
        
        # 清空之前的数据
        self.partial_transcripts.clear()
        self.all_transcript_segments.clear()
        self.final_transcript = None
        self.current_session_audio = None
        
        # 重置计时器并开始录音计时
        self.timer.reset()
        self.timer.start("total_session")
        self.timer.start("recording")
        
        # 更新状态
        self.state = AppState.RECORDING
        
        # 开始录音（简化，不用实时处理）
        success = self.audio_recorder.start_recording()
        
        if not success:
            print("❌ 录音启动失败")
            self.state = AppState.IDLE
            self.timer.reset()
    
    def _stop_recording(self):
        """停止录音"""
        if self.state != AppState.RECORDING:
            return
        
        print(f"\n{'='*50}")
        print(f"⏹️  停止录音，正在处理...")
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
        
        # 直接转录完整音频（简化）
        if final_audio is not None and len(final_audio) > 0:
            print("🎯 开始转录...")
            
            # 开始Whisper转录计时
            self.timer.start("whisper_transcription")
            
            # 直接调用同步转录
            transcript = self.transcriber.transcribe_complete_audio(final_audio)
            
            # 停止Whisper转录计时
            whisper_time = self.timer.stop("whisper_transcription")
            if whisper_time:
                print(f"⏱️  Whisper转录耗时: {self.timer.format_duration(whisper_time.duration_ms)}")
            
            if transcript:
                # 开始词典优化计时
                self.timer.start("dictionary_processing")
                
                # 应用用户词典优化
                optimized_transcript = self.dictionary_manager.process_transcript(transcript)
                
                # 停止词典优化计时
                dict_time = self.timer.stop("dictionary_processing")
                if dict_time:
                    print(f"⏱️  词典处理耗时: {self.timer.format_duration(dict_time.duration_ms)}")
                
                # 提取原始转录文本
                combined_text = ""
                for entry in optimized_transcript:
                    text = entry.get('text', '').strip()
                    if text:
                        combined_text += text + " "
                
                raw_text = combined_text.strip()
                if raw_text and config.ENABLE_CLIPBOARD:
                    # 开始剪贴板操作计时
                    self.timer.start("clipboard_copy")
                    
                    # 立即复制原始转录结果到剪贴板
                    try:
                        pyperclip.copy(raw_text)
                        clipboard_time = self.timer.stop("clipboard_copy")
                        if clipboard_time:
                            print(f"📋 原始转录已复制到剪贴板 ({self.timer.format_duration(clipboard_time.duration_ms)})")
                        else:
                            print("📋 原始转录已复制到剪贴板")
                    except Exception as e:
                        self.timer.stop("clipboard_copy")
                        print(f"⚠️  复制到剪贴板失败: {e}")
                
                # Gemini纠错处理
                if config.ENABLE_GEMINI_CORRECTION and raw_text:
                    print("🤖 Gemini纠错中...")
                    
                    # 开始Gemini纠错计时
                    self.timer.start("gemini_correction")
                    
                    corrected_text = self.gemini_corrector.correct_transcript(raw_text)
                    
                    # 停止Gemini纠错计时
                    gemini_time = self.timer.stop("gemini_correction")
                    
                    if corrected_text and corrected_text.strip() != raw_text:
                        # 更新转录结果
                        optimized_transcript = [{
                            'start': 0.0,
                            'duration': len(optimized_transcript) * 2.0,
                            'text': corrected_text,
                            'gemini_corrected': True
                        }]
                        
                        # 用纠错后的文本覆盖剪贴板
                        if config.ENABLE_CLIPBOARD:
                            self.timer.start("clipboard_update")
                            try:
                                pyperclip.copy(corrected_text.strip())
                                clipboard_update_time = self.timer.stop("clipboard_update")
                                if gemini_time and clipboard_update_time:
                                    print(f"✅ Gemini纠错完成 ({self.timer.format_duration(gemini_time.duration_ms)})，已更新剪贴板 ({self.timer.format_duration(clipboard_update_time.duration_ms)})")
                                else:
                                    print("✅ Gemini纠错完成，已更新剪贴板")
                            except Exception as e:
                                self.timer.stop("clipboard_update")
                                print(f"⚠️  更新剪贴板失败: {e}")
                        else:
                            if gemini_time:
                                print(f"✅ Gemini纠错完成 ({self.timer.format_duration(gemini_time.duration_ms)})")
                            else:
                                print("✅ Gemini纠错完成")
                    else:
                        if gemini_time:
                            print(f"ℹ️  无需纠错 ({self.timer.format_duration(gemini_time.duration_ms)})，剪贴板保持原始内容")
                        else:
                            print("ℹ️  无需纠错，剪贴板保持原始内容")
                
                self.final_transcript = optimized_transcript
            
            self._finish_session()
        else:
            print("❌ 未录制到有效音频")
            self._finish_session()
    
    
    def _finish_session(self):
        """完成会话处理"""
        self.state = AppState.COMPLETE
        
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
    
    def _display_final_results(self):
        """显示最终转录结果"""
        print(f"\n\n{'='*60}")
        print(f"🎯 最终转录结果")
        print(f"{'='*60}")
        
        if self.final_transcript:
            # 显示优化后的结果（简化，不显示时间戳）
            full_text = ""
            gemini_used = False
            for entry in self.final_transcript:
                text = entry.get('text', '').strip()
                if text:
                    full_text += text + " "
                if entry.get('gemini_corrected', False):
                    gemini_used = True
            
            correction_info = " (Gemini纠错)" if gemini_used else " (原始转录)"
            print(f"📝 完整转录内容{correction_info}:")
            print(f"{'-'*50}")
            print(full_text.strip())
            print(f"{'-'*50}")
            
            # 显示替换统计
            if config.DEBUG_MODE:
                self._show_replacement_stats()
                
        elif self.partial_transcripts:
            # 如果没有最终转录，显示合并的部分结果
            combined_text = ' '.join(self.partial_transcripts)
            print(f"📝 转录内容 (基于部分结果):")
            print(f"{'-'*50}")
            print(combined_text)
            print(f"{'-'*50}")
        else:
            print(f"❌ 未获取到转录结果")
            print(f"可能原因:")
            print(f"  - 录音时间过短")
            print(f"  - 音频质量不佳")
            print(f"  - 背景噪音过大")
        
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
                    if name in ["recording", "whisper_transcription", "gemini_correction"]:
                        print(f"  {self._format_timing_name(name)}: {self.timer.format_duration(timing.duration_ms)}")
    
    def _format_timing_name(self, name: str) -> str:
        """格式化计时器名称显示"""
        name_map = {
            "recording": "录音时长",
            "whisper_transcription": "Whisper转录",
            "gemini_correction": "Gemini纠错",
            "dictionary_processing": "词典处理",
            "clipboard_copy": "剪贴板复制",
            "clipboard_update": "剪贴板更新",
            "total_session": "总计时间"
        }
        return name_map.get(name, name)
    
    def start(self):
        """启动应用"""
        if not self.transcriber.is_ready:
            print("❌ 转录器未准备就绪，请检查 whisper.cpp 安装和模型文件")
            return False
        
        self.running = True
        
        # 启动快捷键监听
        if not self.hotkey_listener.start():
            print("❌ 快捷键监听启动失败")
            return False
        
        print("🚀 应用已启动，双击 Option 键开始录音")
        print("按 Ctrl+C 退出程序")
        
        # 显示设备信息
        if config.DEBUG_MODE:
            self.audio_recorder.get_device_info()
        
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
        
        # 如果正在录音，先停止
        if self.state == AppState.RECORDING:
            print("停止当前录音...")
            self._stop_recording()
        
        # 停止各个组件
        self.hotkey_listener.stop()
        self.audio_recorder.stop_recording()
        self.transcriber.stop_processing()
        
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
    
    # 创建并启动应用
    app = VoiceTranscriptionApp()
    
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