#!/usr/bin/env python3
"""
全局快捷键监听模块
仅允许配置单个修饰键长按触发录音，组合键会被拦截
"""

import threading
from typing import Callable, Dict, List, Optional, Sequence, Set

from pynput import keyboard

import config


def _normalize_key_name(name: str) -> str:
    """统一键名格式，便于匹配配置与 pynput 键值"""

    return name.strip().lower().replace(" ", "_")


def _register_key(
    registry: Dict[str, Dict[str, object]],
    aliases: Sequence[str],
    label: str,
    key_objects: Sequence[keyboard.Key],
) -> None:
    """将按键别名注册到共享定义里"""

    entry = {"label": label, "keys": set(key_objects)}
    for alias in aliases:
        registry[_normalize_key_name(alias)] = entry


# 支持的长按按键集合（Command / Option 等）
SUPPORTED_LONG_PRESS_KEYS: Dict[str, Dict[str, object]] = {}
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("option", "opt", "alt"),
    label="Option",
    key_objects=(keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r),
)
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("left_option", "option_left", "opt_l", "alt_l", "left_alt"),
    label="Left Option",
    key_objects=(keyboard.Key.alt_l,),
)
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("right_option", "option_right", "opt_r", "alt_r", "right_alt"),
    label="Right Option",
    key_objects=(keyboard.Key.alt_r,),
)
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("command", "cmd", "meta"),
    label="Command",
    key_objects=(keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r),
)
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("left_command", "command_left", "cmd_l"),
    label="Left Command",
    key_objects=(keyboard.Key.cmd_l,),
)
_register_key(
    SUPPORTED_LONG_PRESS_KEYS,
    aliases=("right_command", "command_right", "cmd_r"),
    label="Right Command",
    key_objects=(keyboard.Key.cmd_r,),
)

DEFAULT_LONG_PRESS_NAME = _normalize_key_name("left_option")


class HotkeyListener:
    def __init__(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
        long_press_threshold: Optional[float] = None,
    ):
        """初始化快捷键监听器（仅支持单个修饰键触发）"""

        self.on_press = on_press
        self.on_release = on_release
        self.long_press_threshold = (
            long_press_threshold
            if long_press_threshold is not None
            else getattr(config, "HOTKEY_LONG_PRESS_THRESHOLD", 0.3)
        )

        self.listener: Optional[keyboard.Listener] = None
        self.running = False

        configured_name = self._load_configured_hotkey()

        (
            self._monitored_keys,
            self._display_labels,
        ) = self._resolve_hotkey_config(configured_name)

        # 长按状态管理
        self._lock = threading.Lock()
        self._hotkey_pressed = False
        self._long_press_triggered = False
        self._long_press_timer: Optional[threading.Timer] = None
        self._active_non_hotkeys: Set[object] = set()
        self._combo_blocked = False

    def _load_configured_hotkey(self) -> str:
        """只允许单一热键名称，优先读取 HOTKEY_LONG_PRESS_KEY"""

        single_key = getattr(config, "HOTKEY_LONG_PRESS_KEY", None)
        if isinstance(single_key, str) and single_key.strip():
            return single_key.strip()

        configured_keys = getattr(config, "HOTKEY_LONG_PRESS_KEYS", None)
        if isinstance(configured_keys, str):
            return configured_keys.strip()

        if isinstance(configured_keys, Sequence):
            valid_names = [
                name for name in configured_keys if isinstance(name, str) and name.strip()
            ]
            if not valid_names:
                return DEFAULT_LONG_PRESS_NAME

            if len(valid_names) > 1:
                print(
                    "⚠️ 仅支持单个长按热键，已使用配置中的首个按键："
                    f"{valid_names[0]}"
                )
            return valid_names[0]

        return DEFAULT_LONG_PRESS_NAME

    def _cancel_long_press_timer_locked(self) -> None:
        if self._long_press_timer:
            self._long_press_timer.cancel()
            self._long_press_timer = None

    def _resolve_hotkey_config(
        self, configured_name: str
    ) -> tuple[Set[keyboard.Key], List[str]]:
        """根据配置解析可监听的键集合和展示标签"""

        normalized = _normalize_key_name(configured_name)
        definition = SUPPORTED_LONG_PRESS_KEYS.get(normalized)

        if not definition:
            print(
                f"⚠️ 未识别的长按热键配置: {configured_name}，已回退到 Left Option 键"
            )
            fallback = SUPPORTED_LONG_PRESS_KEYS[DEFAULT_LONG_PRESS_NAME]
            return set(fallback["keys"]), [fallback["label"]]  # type: ignore[arg-type]

        monitored_keys = set(definition["keys"])  # type: ignore[arg-type]
        return monitored_keys, [definition["label"]]

    def _is_configured_key(self, key: keyboard.Key) -> bool:
        """判断是否为配置允许的长按键"""

        return key in self._monitored_keys

    def _handle_long_press(self):
        with self._lock:
            if (
                not self._hotkey_pressed
                or self._long_press_triggered
                or self._combo_blocked
            ):
                return
            self._long_press_triggered = True

        self._safe_call(self.on_press)

    def _on_press(self, key):
        if not self._is_configured_key(key):
            with self._lock:
                self._active_non_hotkeys.add(key)
                if self._hotkey_pressed and not self._combo_blocked:
                    self._combo_blocked = True
                    self._cancel_long_press_timer_locked()
            return

        with self._lock:
            if self._hotkey_pressed:
                return

            self._hotkey_pressed = True
            self._long_press_triggered = False
            self._combo_blocked = bool(self._active_non_hotkeys)

            if self._combo_blocked:
                return

            self._long_press_timer = threading.Timer(
                max(self.long_press_threshold, 0.0),
                self._handle_long_press,
            )
            self._long_press_timer.daemon = True
            self._long_press_timer.start()

    def _on_release(self, key):
        if not self._is_configured_key(key):
            with self._lock:
                self._active_non_hotkeys.discard(key)
                self._combo_blocked = bool(self._active_non_hotkeys)
            return

        with self._lock:
            self._cancel_long_press_timer_locked()

            should_trigger_stop = self._long_press_triggered

            self._hotkey_pressed = False
            self._long_press_triggered = False
            self._combo_blocked = False

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
            # 若标记为运行中但底层监听器已经停止，则允许继续启动流程
            if not self._is_listener_active():
                self.running = False
            else:
                return

        hotkey_label = " / ".join(self._display_labels)
        print(f"启动全局快捷键监听 (按住 {hotkey_label} 键)...")
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
            self._cancel_long_press_timer_locked()
            self._hotkey_pressed = False
            self._long_press_triggered = False
            self._combo_blocked = False
            self._active_non_hotkeys.clear()

        if self.listener:
            self.listener.stop()
            self.listener = None

        print("快捷键监听已停止 ✓")

    def is_running(self) -> bool:
        """检查监听器是否在运行"""
        if not self.running or not self.listener:
            return False
        return self._is_listener_active()

    def ensure_running(self) -> bool:
        """确保监听器保持运行，必要时尝试自动重启。"""

        if self.is_running():
            return True

        if self.listener and not self.listener.running:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None

        self.running = False
        print("⚠️ 检测到热键监听已停止，尝试重新启动...")
        result = self.start()
        if result:
            print("✅ 热键监听已重新启动")
            return True

        print("❌ 热键监听重启失败，请检查辅助功能权限或重新启动应用")
        return False

    def _is_listener_active(self) -> bool:
        return bool(self.listener and getattr(self.listener, "running", False))


# 测试代码
if __name__ == "__main__":

    def handle_start():
        print("🎤 长按触发")

    def handle_stop():
        print("⏹️ 松开长按键，停止录音")

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
