#!/usr/bin/env python3
"""
全局快捷键监听模块
监听 Command 长按触发录音的按键事件
"""

import threading
from typing import Callable, Optional

from pynput import keyboard

import config


class HotkeyListener:
    def __init__(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
        long_press_threshold: Optional[float] = None,
    ):
        """初始化快捷键监听器"""

        self.on_press = on_press
        self.on_release = on_release
        self.long_press_threshold = (
            long_press_threshold
            if long_press_threshold is not None
            else getattr(config, "HOTKEY_LONG_PRESS_THRESHOLD", 0.3)
        )

        self.listener: Optional[keyboard.Listener] = None
        self.running = False

        # Command 长按状态管理
        self._lock = threading.Lock()
        self._command_pressed = False
        self._long_press_triggered = False
        self._long_press_timer: Optional[threading.Timer] = None

    def _is_command_key(self, key) -> bool:
        """判断是否为 Command 键"""
        command_keys = {
            keyboard.Key.cmd,
            keyboard.Key.cmd_l,
            keyboard.Key.cmd_r,
        }
        return key in command_keys or str(key).replace("Key.", "") in {"cmd", "cmd_l", "cmd_r"}

    def _handle_long_press(self):
        with self._lock:
            if not self._command_pressed or self._long_press_triggered:
                return
            self._long_press_triggered = True

        self._safe_call(self.on_press)

    def _on_press(self, key):
        if not self._is_command_key(key):
            return

        with self._lock:
            if self._command_pressed:
                return

            self._command_pressed = True
            self._long_press_triggered = False

            self._long_press_timer = threading.Timer(
                max(self.long_press_threshold, 0.0),
                self._handle_long_press,
            )
            self._long_press_timer.daemon = True
            self._long_press_timer.start()

    def _on_release(self, key):
        if not self._is_command_key(key):
            return

        with self._lock:
            if self._long_press_timer:
                self._long_press_timer.cancel()
                self._long_press_timer = None

            should_trigger_stop = self._long_press_triggered

            self._command_pressed = False
            self._long_press_triggered = False

        if should_trigger_stop:
            self._safe_call(self.on_release)

    def _safe_call(self, callback: Optional[Callable[[], None]]):
        if not callback:
            return
        try:
            callback()
        except Exception as exc:
            print(f"❌ 快捷键回调执行错误: {exc}")

    def start(self):
        """启动快捷键监听"""
        if self.running:
            return

        print("启动全局快捷键监听 (按住 Command 键)...")
        print("注意: 首次运行可能需要授权辅助功能权限")

        self.running = True

        try:
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self.listener.start()

            print("快捷键监听已启动 ✓")
            return True

        except Exception as exc:
            print(f"启动快捷键监听失败: {exc}")
            print("可能需要在 系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能 中授权此应用")
            self.running = False
            return False

    def stop(self):
        """停止快捷键监听"""
        if not self.running:
            return

        print("停止快捷键监听...")
        self.running = False

        with self._lock:
            if self._long_press_timer:
                self._long_press_timer.cancel()
                self._long_press_timer = None
            self._command_pressed = False
            self._long_press_triggered = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        print("快捷键监听已停止 ✓")

    def is_running(self) -> bool:
        """检查监听器是否在运行"""
        return self.running and (self.listener is not None)


# 测试代码
if __name__ == "__main__":

    def handle_start():
        print("🎤 Command 长按触发")

    def handle_stop():
        print("⏹️ Command 松开，停止录音")

    config.DEBUG_MODE = True

    listener = HotkeyListener(on_press=handle_start, on_release=handle_stop)

    try:
        if listener.start():
            print("按 Ctrl+C 退出测试...")
            import time

            while True:
                time.sleep(1)
        else:
            print("无法启动快捷键监听")
    except KeyboardInterrupt:
        print("\n退出测试...")
        listener.stop()
