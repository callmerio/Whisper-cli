#!/usr/bin/env python3
"""
系统级文本输入管理器
支持在 macOS 任意应用中的光标位置直接输入文本
"""

import time
import subprocess
import os
from typing import Optional, List, Callable
from enum import Enum
from dataclasses import dataclass
import threading

try:
    from pynput.keyboard import Controller, Key
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("⚠️  pynput 未安装，文本输入功能将受限")
    print("   请运行: uv add pynput")

import pyperclip
import config


class InputMethod(Enum):
    """输入方法"""
    DIRECT_TYPE = "direct_type"      # 直接键盘输入
    CLIPBOARD_PASTE = "clipboard"    # 剪贴板粘贴
    DISABLED = "disabled"            # 禁用输入


class InputResult(Enum):
    """输入结果"""
    SUCCESS = "success"
    PERMISSION_DENIED = "permission_denied"
    METHOD_UNAVAILABLE = "method_unavailable"
    INPUT_CONFLICT = "input_conflict"
    ERROR = "error"


@dataclass
class InputRequest:
    """输入请求"""
    text: str                    # 要输入的文本
    method: InputMethod         # 输入方法
    delay_before: float = 0.1   # 输入前延迟
    delay_after: float = 0.1    # 输入后延迟
    backup_to_clipboard: bool = True  # 是否备份到剪贴板
    request_id: Optional[str] = None  # 请求ID


class TextInputManager:
    """系统级文本输入管理器"""
    
    def __init__(self):
        """初始化文本输入管理器"""
        # 配置参数
        default_method_str = getattr(config, 'TEXT_INPUT_METHOD', 'direct_type')
        if default_method_str == 'direct_type':
            self.default_method = InputMethod.DIRECT_TYPE
        elif default_method_str == 'clipboard':
            self.default_method = InputMethod.CLIPBOARD_PASTE
        else:
            self.default_method = InputMethod.DISABLED
            
        self.input_delay = getattr(config, 'TEXT_INPUT_DELAY', 0.1)
        self.enable_clipboard_backup = getattr(config, 'TEXT_INPUT_CLIPBOARD_BACKUP', True)
        self.check_permissions_on_init = getattr(config, 'TEXT_INPUT_CHECK_PERMISSIONS', True)
        
        # 组件初始化
        self.keyboard_controller = None
        self.permission_checked = False
        self.permission_granted = False
        self.input_lock = threading.Lock()
        
        # 回调函数
        self.on_input_success: Optional[Callable[[str], None]] = None
        self.on_input_error: Optional[Callable[[str, str], None]] = None
        self.on_permission_required: Optional[Callable[[], None]] = None
        
        # 初始化
        self._initialize()
    
    def _initialize(self):
        """初始化组件"""
        if not PYNPUT_AVAILABLE:
            print("❌ pynput 不可用，文本输入功能受限")
            return
        
        try:
            self.keyboard_controller = Controller()
            print("✅ 键盘控制器初始化成功")
        except Exception as e:
            print(f"❌ 键盘控制器初始化失败: {e}")
        
        # 检查权限
        if self.check_permissions_on_init:
            self._check_permissions()
        
        print(f"🖊️ 文本输入管理器初始化完成")
        if isinstance(self.default_method, InputMethod):
            print(f"   默认输入方法: {self.default_method.value}")
        else:
            print(f"   默认输入方法: {self.default_method}")
        print(f"   输入延迟: {self.input_delay}s")
    
    def _check_permissions(self) -> bool:
        """检查 macOS 辅助功能权限"""
        if self.permission_checked:
            return self.permission_granted
        
        self.permission_checked = True
        
        try:
            # 在 macOS 上检查辅助功能权限
            if os.uname().sysname == 'Darwin':
                # 尝试执行一个需要权限的操作
                test_controller = Controller()
                test_controller.type('')  # 空字符串测试
                
                self.permission_granted = True
                print("✅ macOS 辅助功能权限已授予")
                return True
                
        except Exception as e:
            self.permission_granted = False
            print(f"❌ macOS 辅助功能权限检查失败: {e}")
            print("   请前往: 系统偏好设置 > 隐私与安全性 > 辅助功能")
            print("   添加你的终端应用到允许列表")
            
            if self.on_permission_required:
                try:
                    self.on_permission_required()
                except Exception as callback_error:
                    if config.DEBUG_MODE:
                        print(f"⚠️ 权限回调异常: {callback_error}")
            
            return False
        
        return self.permission_granted
    
    def set_callbacks(self,
                     on_input_success: Optional[Callable[[str], None]] = None,
                     on_input_error: Optional[Callable[[str, str], None]] = None,
                     on_permission_required: Optional[Callable[[], None]] = None):
        """设置回调函数"""
        self.on_input_success = on_input_success
        self.on_input_error = on_input_error
        self.on_permission_required = on_permission_required
    
    def input_text(self, request: InputRequest) -> InputResult:
        """输入文本到当前光标位置"""
        if not request.text.strip():
            return InputResult.SUCCESS
        
        with self.input_lock:
            try:
                # 输入前延迟
                if request.delay_before > 0:
                    time.sleep(request.delay_before)
                
                # 选择输入方法（显式请求优先，其次回退到默认）
                method = request.method or self.default_method

                result = InputResult.ERROR
                text_to_input = request.text
                skip_input = False

                if method == InputMethod.CLIPBOARD_PASTE:
                    sanitized_text = self._sanitize_clipboard_text(request.text)
                    request.text = sanitized_text
                    text_to_input = sanitized_text
                    if not sanitized_text:
                        skip_input = True
                        result = InputResult.SUCCESS

                if not skip_input:
                    if method == InputMethod.DIRECT_TYPE:
                        result = self._direct_type_input(text_to_input)
                    elif method == InputMethod.CLIPBOARD_PASTE:
                        result = self._clipboard_paste_input(text_to_input)
                    elif method == InputMethod.DISABLED:
                        result = InputResult.SUCCESS  # 不执行输入
                
                # 备份到剪贴板
                if result == InputResult.SUCCESS and request.backup_to_clipboard and request.text:
                    try:
                        pyperclip.copy(request.text)
                        if config.DEBUG_MODE:
                            print(f"📋 文本已备份到剪贴板")
                    except Exception as e:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 剪贴板备份失败: {e}")
                
                # 输入后延迟
                if request.delay_after > 0:
                    time.sleep(request.delay_after)
                
                # 调用回调
                if result == InputResult.SUCCESS:
                    if self.on_input_success:
                        try:
                            self.on_input_success(request.text)
                        except Exception as e:
                            if config.DEBUG_MODE:
                                print(f"⚠️ 输入成功回调异常: {e}")
                else:
                    if self.on_input_error:
                        try:
                            self.on_input_error(request.text, result.value)
                        except Exception as e:
                            if config.DEBUG_MODE:
                                print(f"⚠️ 输入错误回调异常: {e}")
                
                return result
                
            except Exception as e:
                error_msg = f"文本输入异常: {e}"
                print(f"❌ {error_msg}")
                
                if self.on_input_error:
                    try:
                        self.on_input_error(request.text, error_msg)
                    except Exception as callback_error:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 错误回调异常: {callback_error}")
                
                return InputResult.ERROR
    
    def _direct_type_input(self, text: str) -> InputResult:
        """直接键盘输入方法"""
        if not PYNPUT_AVAILABLE:
            return InputResult.METHOD_UNAVAILABLE
        
        if not self.keyboard_controller:
            return InputResult.METHOD_UNAVAILABLE
        
        if not self._check_permissions():
            return InputResult.PERMISSION_DENIED
        
        try:
            # 等待更长时间确保目标应用准备好
            time.sleep(0.8)
            
            # 逐字符输入，支持中文，使用更慢的速度确保稳定性
            for i, char in enumerate(text):
                self.keyboard_controller.type(char)
                
                # 根据字符类型调整延迟
                if ord(char) > 127:  # 非ASCII字符（中文、emoji等）
                    time.sleep(0.08)  # 增加延迟确保中文输入稳定
                else:
                    time.sleep(0.03)  # 英文字符也增加延迟
                
                # 每输入5个字符暂停一下，防止输入过快
                if (i + 1) % 5 == 0:
                    time.sleep(0.1)
            
            print(f"⌨️ 直接输入完成: {len(text)} 字符")
            return InputResult.SUCCESS
            
        except Exception as e:
            print(f"❌ 直接输入失败: {e}")
            return InputResult.ERROR
    
    def _clipboard_paste_input(self, text: str) -> InputResult:
        """剪贴板粘贴输入方法"""
        try:
            original_clipboard = ""
            try:
                original_clipboard = pyperclip.paste()
            except Exception:
                pass

            pyperclip.copy(text)
            time.sleep(0.15)

            clipboard_content = pyperclip.paste()
            if clipboard_content != text:
                print(f"⚠️ 剪贴板验证失败，期望: '{text}', 实际: '{clipboard_content}'")
                return InputResult.ERROR

            if not self._perform_paste_shortcut():
                print("⚠️ 粘贴快捷键触发失败，文本仍保留在剪贴板，需手动 Cmd+V")
                return InputResult.INPUT_CONFLICT

            # 给予目标应用足够时间完成粘贴
            time.sleep(0.35)

            if original_clipboard:
                try:
                    pyperclip.copy(original_clipboard)
                except Exception:
                    if config.DEBUG_MODE:
                        print("⚠️ 恢复原剪贴板内容失败，保持当前文本")

            print(f"📋 剪贴板粘贴完成: {len(text)} 字符")
            return InputResult.SUCCESS

        except Exception as e:
            print(f"❌ 剪贴板粘贴失败: {e}")
            return InputResult.ERROR

    def _perform_paste_shortcut(self) -> bool:
        """尝试触发系统级 Cmd+V 粘贴"""

        # 首选 pynput 模拟按键
        if PYNPUT_AVAILABLE and self.keyboard_controller:
            try:
                if not self._check_permissions():
                    return False

                time.sleep(0.1)
                self.keyboard_controller.press(Key.cmd)
                time.sleep(0.07)
                self.keyboard_controller.press('v')
                time.sleep(0.07)
                self.keyboard_controller.release('v')
                time.sleep(0.07)
                self.keyboard_controller.release(Key.cmd)
                return True
            except Exception as exc:
                if config.DEBUG_MODE:
                    print(f"⚠️ pynput 粘贴按键触发失败: {exc}")

        # 回退到 AppleScript 触发
        if os.uname().sysname == 'Darwin':
            script = 'tell application "System Events" to keystroke "v" using {command down}'
            try:
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                stderr_text = (proc.stderr or "").strip()
                if proc.returncode != 0:
                    if config.DEBUG_MODE:
                        print(
                            f"⚠️ AppleScript 粘贴触发返回码 {proc.returncode}: {stderr_text}"
                        )
                    return False

                if stderr_text:
                    lowered = stderr_text.lower()
                    if "not trusted" in lowered or "accessibility" in lowered:
                        print(
                            "⚠️ 系统未授予辅助功能权限，无法自动粘贴。请在 系统设置 → 隐私与安全性 → 辅助功能 中勾选终端应用后重试。"
                        )
                        return False
                    if config.DEBUG_MODE:
                        print(f"ℹ️ AppleScript 输出: {stderr_text}")

                time.sleep(0.15)
                return True
            except Exception as exc:
                if config.DEBUG_MODE:
                    print(f"⚠️ AppleScript 粘贴触发失败: {exc}")

        return False

    def _sanitize_clipboard_text(self, text: str) -> str:
        """粘贴前轻量清理文本，保留标点仅去除首尾空白。"""
        if not text:
            return ""

        sanitized = text.strip()

        if sanitized != text and config.DEBUG_MODE:
            print(f"🧹 已清理粘贴文本首尾空白 -> '{sanitized}'")

        return sanitized
    
    def input_text_simple(self, text: str, method: Optional[InputMethod] = None) -> bool:
        """简化的文本输入接口"""
        request = InputRequest(
            text=text,
            method=method or self.default_method,
            delay_before=self.input_delay,
            delay_after=self.input_delay / 2,
            backup_to_clipboard=self.enable_clipboard_backup
        )
        
        result = self.input_text(request)
        return result == InputResult.SUCCESS
    
    def test_input_method(self, method: InputMethod) -> InputResult:
        """测试输入方法是否可用"""
        test_request = InputRequest(
            text="",  # 空文本测试
            method=method,
            delay_before=0,
            delay_after=0,
            backup_to_clipboard=False
        )
        
        return self.input_text(test_request)
    
    def get_available_methods(self) -> List[InputMethod]:
        """获取可用的输入方法"""
        available = []
        
        # 测试直接输入
        if self.test_input_method(InputMethod.DIRECT_TYPE) in [InputResult.SUCCESS, InputResult.INPUT_CONFLICT]:
            available.append(InputMethod.DIRECT_TYPE)
        
        # 测试剪贴板输入
        if self.test_input_method(InputMethod.CLIPBOARD_PASTE) in [InputResult.SUCCESS, InputResult.INPUT_CONFLICT]:
            available.append(InputMethod.CLIPBOARD_PASTE)
        
        # 禁用输入总是可用
        available.append(InputMethod.DISABLED)
        
        return available
    
    def set_default_method(self, method: InputMethod):
        """设置默认输入方法"""
        self.default_method = method
        print(f"🔧 默认输入方法更新为: {method.value}")
    
    def get_status(self) -> dict:
        """获取状态信息"""
        return {
            "pynput_available": PYNPUT_AVAILABLE,
            "keyboard_controller_ready": self.keyboard_controller is not None,
            "permission_checked": self.permission_checked,
            "permission_granted": self.permission_granted,
            "default_method": self.default_method.value,
            "available_methods": [m.value for m in self.get_available_methods()]
        }
    
    def open_accessibility_settings(self):
        """打开 macOS 辅助功能设置（仅 macOS）"""
        try:
            if os.uname().sysname == 'Darwin':
                subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])
                print("🔧 已打开辅助功能设置")
                return True
        except Exception as e:
            print(f"❌ 无法打开设置: {e}")
        
        return False


# 全局实例
text_input_manager = TextInputManager()


def test_text_input():
    """测试文本输入功能"""
    print("🧪 测试文本输入管理器...")
    
    def on_success(text):
        print(f"✅ 输入成功: {text}")
    
    def on_error(text, error):
        print(f"❌ 输入失败: {text} - {error}")
    
    def on_permission():
        print("🔐 需要权限，请检查系统设置")
    
    manager = TextInputManager()
    manager.set_callbacks(
        on_input_success=on_success,
        on_input_error=on_error,
        on_permission_required=on_permission
    )
    
    # 显示状态
    status = manager.get_status()
    print(f"📊 状态: {status}")
    
    # 测试可用方法
    available = manager.get_available_methods()
    print(f"📋 可用方法: {[m.value for m in available]}")
    
    # 测试输入（等待用户确认）
    print("\n⚠️  准备测试文本输入...")
    print("   请确保光标在一个可输入的位置（如文本编辑器）")
    print("   按 Enter 继续测试，或 Ctrl+C 取消...")
    
    try:
        input()
        
        # 测试简单输入
        test_text = "Hello, 这是一个测试文本! 🎉"
        success = manager.input_text_simple(test_text)
        
        if success:
            print("✅ 文本输入测试成功")
        else:
            print("❌ 文本输入测试失败")
    
    except KeyboardInterrupt:
        print("\n⏹️ 测试已取消")
    
    print("✅ 文本输入测试完成")


if __name__ == "__main__":
    test_text_input()
