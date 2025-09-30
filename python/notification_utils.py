#!/usr/bin/env python3
"""
通知工具模块
提供多种通知方式：系统通知、声音提示、视觉提示
"""

import os
import subprocess
import threading
import time
from typing import Optional, Callable
from pathlib import Path
import config

class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        """初始化通知管理器"""
        self.platform = self._detect_platform()
        self.notification_enabled = True
        self.sound_enabled = True
        self.visual_enabled = True
        
        # 检测系统通知支持
        self.system_notification_available = self._check_system_notification()
        
        if config.DEBUG_MODE:
            print(f"🔔 通知系统初始化:")
            print(f"   平台: {self.platform}")
            print(f"   系统通知: {'✅' if self.system_notification_available else '❌'}")
    
    def _detect_platform(self) -> str:
        """检测操作系统平台"""
        import platform
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'windows':
            return 'windows' 
        elif system == 'linux':
            return 'linux'
        else:
            return 'unknown'
    
    def _check_system_notification(self) -> bool:
        """检查系统通知支持"""
        if self.platform == 'macos':
            # macOS 使用 osascript 显示通知
            try:
                subprocess.run(['osascript', '-e', 'display notification "test" with title "test"'], 
                             capture_output=True, timeout=2, check=True)
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                return False
        elif self.platform == 'linux':
            # Linux 使用 notify-send
            try:
                subprocess.run(['notify-send', '--version'], 
                             capture_output=True, timeout=2, check=True)
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                return False
        elif self.platform == 'windows':
            # Windows 使用 PowerShell
            return True
        
        return False
    
    def show_clipboard_notification(self, text: str, correction_type: str = "原始") -> None:
        """
        显示剪贴板复制完成通知
        
        Args:
            text: 复制的文本内容
            correction_type: 纠错类型 ("原始" 或 "纠错")
        """
        # 截断过长的文本用于显示
        display_text = text[:50] + "..." if len(text) > 50 else text
        
        # 根据类型设置不同的标题和图标
        if correction_type == "纠错":
            title = "🤖 AI纠错完成"
            message = f"已更新剪贴板内容:\n{display_text}"
            self._play_success_sound()
        else:
            title = "📋 转录完成"
            message = f"已复制到剪贴板:\n{display_text}"
            self._play_copy_sound()
        
        # 显示控制台提示（增强版）
        self._show_console_notification(title, message, text)
        
        # 显示系统通知
        if self.system_notification_available:
            threading.Thread(
                target=self._show_system_notification,
                args=(title, message),
                daemon=True
            ).start()
    
    def _show_console_notification(self, title: str, message: str, full_text: str) -> None:
        """显示增强的控制台通知"""
        # 计算边框长度
        max_len = max(len(title), max(len(line) for line in message.split('\n')))
        border_len = min(max_len + 4, 60)
        border = "═" * border_len
        
        print(f"\n┌{border}┐")
        print(f"│ {title:^{border_len-2}} │")
        print(f"├{border}┤")
        
        # 分行显示消息
        for line in message.split('\n'):
            if line.strip():
                print(f"│ {line:<{border_len-2}} │")
        
        # 显示字符数统计
        char_count = len(full_text)
        word_count = len(full_text.split())
        stats = f"字符数: {char_count} | 词数: {word_count}"
        print(f"├{border}┤")
        print(f"│ {stats:<{border_len-2}} │")
        
        # 操作提示
        print(f"│ {'按 Cmd+V 粘贴使用':<{border_len-2}} │")
        print(f"└{border}┘")
        
        # 闪烁效果（可选）
        if config.DEBUG_MODE:
            self._create_visual_flash()
    
    def _show_system_notification(self, title: str, message: str) -> None:
        """显示系统通知"""
        try:
            if self.platform == 'macos':
                # macOS 通知
                script = f'''
                display notification "{message}" with title "{title}" sound name "Glass"
                '''
                subprocess.run(['osascript', '-e', script], 
                             capture_output=True, timeout=5)
                             
            elif self.platform == 'linux':
                # Linux 通知
                subprocess.run(['notify-send', title, message, '--icon=info', '--expire-time=3000'],
                             capture_output=True, timeout=5)
                             
            elif self.platform == 'windows':
                # Windows 通知
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $xml = New-Object System.Xml.XmlDocument
                $xml.LoadXml($template.GetXml())
                $xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null  
                $xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Whisper-CLI").Show($toast)
                '''
                subprocess.run(['powershell', '-Command', ps_script],
                             capture_output=True, timeout=5)
                             
        except Exception as e:
            if config.DEBUG_MODE:
                print(f"系统通知发送失败: {e}")
    
    def _play_copy_sound(self) -> None:
        """播放复制完成音效"""
        if not self.sound_enabled:
            return
            
        threading.Thread(target=self._play_sound_async, args=("copy",), daemon=True).start()
    
    def _play_success_sound(self) -> None:
        """播放纠错成功音效"""
        if not self.sound_enabled:
            return
            
        threading.Thread(target=self._play_sound_async, args=("success",), daemon=True).start()
    
    def _play_warning_sound(self) -> None:
        """播放警告音效"""
        if not self.sound_enabled:
            return
            
        threading.Thread(target=self._play_sound_async, args=("warning",), daemon=True).start()
    
    def _play_start_recording_sound(self) -> None:
        """播放录音开始音效"""
        if not self.sound_enabled:
            return
            
        threading.Thread(target=self._play_sound_async, args=("start_recording",), daemon=True).start()
    
    def _play_sound_async(self, sound_type: str) -> None:
        """异步播放声音"""
        try:
            if self.platform == 'macos':
                if sound_type == "copy":
                    # 播放系统复制音效
                    subprocess.run(['afplay', '/System/Library/Sounds/Tink.aiff'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "success":
                    # 播放系统成功音效
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "warning":
                    # 播放系统警告音效
                    subprocess.run(['afplay', '/System/Library/Sounds/Sosumi.aiff'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "start_recording":
                    # 播放录音开始音效 - 使用较短的提示音
                    subprocess.run(['afplay', '/System/Library/Sounds/Ping.aiff'], 
                                 capture_output=True, timeout=3)
            elif self.platform == 'linux':
                # Linux 播放音效
                if sound_type == "copy":
                    subprocess.run(['paplay', '/usr/share/sounds/alsa/Front_Left.wav'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "success":
                    subprocess.run(['paplay', '/usr/share/sounds/alsa/Front_Right.wav'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "warning":
                    subprocess.run(['paplay', '/usr/share/sounds/alsa/Rear_Left.wav'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "start_recording":
                    subprocess.run(['paplay', '/usr/share/sounds/alsa/Side_Left.wav'], 
                                 capture_output=True, timeout=3)
            elif self.platform == 'windows':
                # Windows 播放音效
                if sound_type == "copy":
                    subprocess.run(['powershell', '-c', '(New-Object Media.SoundPlayer "C:\\Windows\\Media\\Windows Ding.wav").PlaySync()'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "success":
                    subprocess.run(['powershell', '-c', '(New-Object Media.SoundPlayer "C:\\Windows\\Media\\Windows Notify.wav").PlaySync()'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "warning":
                    subprocess.run(['powershell', '-c', '(New-Object Media.SoundPlayer "C:\\Windows\\Media\\Windows Critical Stop.wav").PlaySync()'], 
                                 capture_output=True, timeout=3)
                elif sound_type == "start_recording":
                    subprocess.run(['powershell', '-c', '(New-Object Media.SoundPlayer "C:\\Windows\\Media\\Windows Information Bar.wav").PlaySync()'], 
                                 capture_output=True, timeout=3)
        except Exception as e:
            if config.DEBUG_MODE:
                print(f"音效播放失败: {e}")
    
    def _create_visual_flash(self) -> None:
        """创建视觉闪烁提示"""
        if not self.visual_enabled:
            return
        
        # 简单的控制台闪烁效果
        for _ in range(3):
            time.sleep(0.1)
            print("\r" + " " * 80, end="", flush=True)  # 清空当前行
            time.sleep(0.1)
            print("\r🎉 剪贴板更新完成！", end="", flush=True)
        print()  # 换行
    
    def show_error_notification(self, error_message: str) -> None:
        """显示错误通知"""
        title = "❌ 操作失败"
        message = f"错误信息:\n{error_message}"
        
        self._show_console_notification(title, message, error_message)
        
        if self.system_notification_available:
            threading.Thread(
                target=self._show_system_notification,
                args=(title, message),
                daemon=True
            ).start()
    
    def show_warning_notification(self, warning_message: str) -> None:
        """显示警告通知"""
        title = "⚠️ 录音时长警告"
        message = warning_message
        
        # 播放警告音效
        self._play_warning_sound()
        
        # 显示控制台通知
        self._show_console_notification(title, message, warning_message)
        
        # 显示系统通知
        if self.system_notification_available:
            threading.Thread(
                target=self._show_system_notification,
                args=(title, message),
                daemon=True
            ).start()
    
    def disable_notifications(self) -> None:
        """禁用所有通知"""
        self.notification_enabled = False
        self.sound_enabled = False
        self.visual_enabled = False
    
    def enable_notifications(self) -> None:
        """启用所有通知"""
        self.notification_enabled = True
        self.sound_enabled = True
        self.visual_enabled = True
    
    def show_start_recording_notification(self) -> None:
        """显示录音开始通知"""
        # 播放录音开始音效
        self._play_start_recording_sound()
        
        if config.DEBUG_MODE:
            print("🎤 录音开始提示音已播放")

# 全局通知管理器实例
notification_manager = NotificationManager()

def notify_clipboard_success(text: str, correction_type: str = "原始") -> None:
    """便捷函数：显示剪贴板成功通知"""
    notification_manager.show_clipboard_notification(text, correction_type)

def notify_error(error_message: str) -> None:
    """便捷函数：显示错误通知"""
    notification_manager.show_error_notification(error_message)

def notify_start_recording() -> None:
    """便捷函数：播放录音开始提示音"""
    notification_manager.show_start_recording_notification()

# 测试代码
if __name__ == "__main__":
    # 启用调试模式
    import sys
    sys.path.append(str(Path(__file__).parent))
    
    manager = NotificationManager()
    
    print("测试通知系统...")
    
    # 测试复制通知
    test_text = "这是一段测试的转录文本，用来验证通知系统是否正常工作。"
    manager.show_clipboard_notification(test_text, "原始")
    
    time.sleep(2)
    
    # 测试纠错通知
    corrected_text = "这是一段测试的转录文本，用来验证通知系统是否正常工作。（已纠错）"
    manager.show_clipboard_notification(corrected_text, "纠错")
    
    time.sleep(2)
    
    # 测试错误通知
    manager.show_error_notification("这是一个测试错误消息")
    
    print("通知测试完成")