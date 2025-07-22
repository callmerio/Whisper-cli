#!/usr/bin/env python3
"""
全局快捷键监听模块
监听 Option+R 快捷键来控制录音状态
"""

import threading
from pynput import keyboard
from typing import Callable, Set
import config

class HotkeyListener:
    def __init__(self, callback: Callable[[], None]):
        """
        初始化快捷键监听器
        
        Args:
            callback: 按键触发时的回调函数
        """
        self.callback = callback
        self.pressed_keys: Set[str] = set()
        self.listener = None
        self.running = False
        
        # 新的检测逻辑：记录按键序列
        self.last_keys_sequence = []
        self.sequence_timeout = 1.0  # 序列超时时间
        self.last_key_time = 0
        
        # 转换配置中的按键名称
        self.target_keys = set()
        for key_name in config.HOTKEY_COMBINATION:
            if key_name == "option":
                self.target_keys.add("alt_l")  # 左侧 Option 键
                self.target_keys.add("alt_r")  # 右侧 Option 键
            elif key_name == "r":
                self.target_keys.add("r")
            else:
                self.target_keys.add(key_name.lower())
    
    def _on_press(self, key):
        """按键按下事件处理"""
        import time
        current_time = time.time()
        
        try:
            # 处理字母和数字键
            key_name = key.char.lower() if key.char else None
        except AttributeError:
            # 处理特殊键
            key_name = str(key).replace('Key.', '')
            
            # 处理 Option 键的不同表示 (macOS)
            if key_name in ['alt_l', 'alt', 'option', 'option_l']:
                key_name = 'alt_l'
            elif key_name in ['alt_r', 'option_r']:
                key_name = 'alt_r'
            elif key_name in ['cmd', 'cmd_l']:
                key_name = 'cmd_l'
            elif key_name in ['cmd_r']:
                key_name = 'cmd_r'
        
        if key_name:
            self.pressed_keys.add(key_name)
            
            # 记录按键序列
            if current_time - self.last_key_time > self.sequence_timeout:
                self.last_keys_sequence.clear()
            
            self.last_keys_sequence.append(key_name)
            self.last_key_time = current_time
            
            # 仅检查按键序列（主要是双击 Option）
            self._check_sequence()
    
    def _on_release(self, key):
        """按键释放事件处理"""
        try:
            key_name = key.char.lower() if key.char else None
        except AttributeError:
            key_name = str(key).replace('Key.', '')
            
            if key_name in ['alt_l', 'alt', 'option', 'option_l']:
                key_name = 'alt_l'
            elif key_name in ['alt_r', 'option_r']:
                key_name = 'alt_r'
            elif key_name in ['cmd', 'cmd_l']:
                key_name = 'cmd_l'
            elif key_name in ['cmd_r']:
                key_name = 'cmd_r'
        
        if key_name and key_name in self.pressed_keys:
            self.pressed_keys.remove(key_name)
    
    def _check_combination(self):
        """检查是否匹配目标组合键（已弃用，使用序列检测）"""
        pass
    
    def _check_sequence(self):
        """检查按键序列模式 - 主要检测双击 Option 键"""
        if len(self.last_keys_sequence) >= 2:
            recent_keys = self.last_keys_sequence[-2:]
            
            # 双击 Option 键触发
            if recent_keys == ['alt_l', 'alt_l'] or recent_keys == ['alt_r', 'alt_r']:
                self._trigger_callback()
                return
    
    def _trigger_callback(self):
        """触发回调并清理状态"""
        try:
            self.callback()
        except Exception as e:
            print(f"❌ 快捷键回调执行错误: {e}")
        
        # 清除序列以避免重复触发
        self.last_keys_sequence.clear()
        self.pressed_keys.clear()
    
    def start(self):
        """启动快捷键监听"""
        if self.running:
            return
        
        print("启动全局快捷键监听 (Option+R)...")
        print("注意: 首次运行可能需要授权辅助功能权限")
        
        self.running = True
        
        try:
            # 创建键盘监听器
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            
            # 启动监听器（非阻塞）
            self.listener.start()
            
            print("快捷键监听已启动 ✓")
            return True
            
        except Exception as e:
            print(f"启动快捷键监听失败: {e}")
            print("可能需要在 系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能 中授权此应用")
            self.running = False
            return False
    
    def stop(self):
        """停止快捷键监听"""
        if not self.running:
            return
        
        print("停止快捷键监听...")
        self.running = False
        
        if self.listener:
            self.listener.stop()
            self.listener = None
        
        print("快捷键监听已停止 ✓")
    
    def is_running(self) -> bool:
        """检查监听器是否在运行"""
        return self.running and (self.listener is not None)

# 测试代码
if __name__ == "__main__":
    def test_callback():
        print("🎤 Option+R 被按下!")
    
    # 启用调试模式
    config.DEBUG_MODE = True
    
    listener = HotkeyListener(test_callback)
    
    try:
        if listener.start():
            print("按 Ctrl+C 退出测试...")
            # 保持程序运行
            import time
            while True:
                time.sleep(1)
        else:
            print("无法启动快捷键监听")
    except KeyboardInterrupt:
        print("\n退出测试...")
        listener.stop()