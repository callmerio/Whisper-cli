"""轻量纠错记忆功能。

提供对原始转录与用户优化文本的对比、筛选与持久化，
帮助后续提示词/词典迭代与人工复核。
"""

from __future__ import annotations

import difflib
import json
import threading
from pathlib import Path
from typing import Optional, Tuple

from pynput import keyboard

try:
    import pyperclip  # type: ignore
except ImportError:  # pragma: no cover - 环境缺失时提示
    pyperclip = None  # type: ignore

import config


# 文件路径配置
CORRECTION_FILE = Path(config.PROJECT_ROOT) / "logs" / "corrections.txt"
HISTORY_FILE = Path(config.PROJECT_ROOT) / "logs" / "history.json"

# 从配置文件读取阈值
MIN_CHARS_IGNORE = getattr(config, "CORRECTION_MIN_CHARS_IGNORE", 3)
AUTO_ACCEPT_THRESHOLD = getattr(config, "CORRECTION_AUTO_ACCEPT_THRESHOLD", 7)
MAX_LENGTH_GROWTH_RATIO = getattr(config, "CORRECTION_MAX_LENGTH_GROWTH_RATIO", 1.6)
MAX_DIFF_RATIO = getattr(config, "CORRECTION_MAX_DIFF_RATIO", 0.5)

# 线程安全的全局状态管理
_hotkey_lock = threading.Lock()
_hotkey_listener: Optional[keyboard.GlobalHotKeys] = None


def _load_latest_history() -> Optional[str]:
    """读取 history.json 中最新一条的文本。
    
    Returns:
        Optional[str]: 最新历史记录的文本内容，如果不存在或出错则返回 None
    """
    if not HISTORY_FILE.exists():
        return None
    
    try:
        raw_text = HISTORY_FILE.read_text(encoding="utf-8")
        if not raw_text.strip():
            return None
            
        data = json.loads(raw_text)
        
        if not isinstance(data, list) or not data:
            return None
            
        latest = data[-1]
        if not isinstance(latest, dict):
            return None
            
        text = latest.get("text") or latest.get("final_text") or ""
        return text.strip()
        
    except (OSError, PermissionError) as exc:
        if config.DEBUG_MODE:
            print(f"⚠️ 无法访问 history.json: {exc}")
        return None
    except json.JSONDecodeError as exc:
        if config.DEBUG_MODE:
            print(f"⚠️ history.json 格式错误: {exc}")
        return None
    except Exception as exc:
        # 未预期的错误，保留日志但不中断
        if config.DEBUG_MODE:
            print(f"⚠️ 读取 history.json 时发生未预期错误: {exc}")
        return None


def _get_clipboard_text() -> Optional[str]:
    """安全地读取剪贴板内容。
    
    Returns:
        Optional[str]: 剪贴板文本内容，失败则返回 None
    """
    if pyperclip is None:
        print("⚠️ 当前环境未安装 pyperclip，无法读取剪贴板")
        return None
        
    try:
        text = pyperclip.paste()
        if not isinstance(text, str):
            return None
        return text.strip()
    except (OSError, RuntimeError) as exc:
        if config.DEBUG_MODE:
            print(f"⚠️ 读取剪贴板失败: {exc}")
        return None
    except Exception as exc:
        if config.DEBUG_MODE:
            print(f"⚠️ 读取剪贴板时发生未预期错误: {exc}")
        return None


def _should_accept(original: str, corrected: str) -> Tuple[bool, str]:
    """根据长度和差异比判断是否记录。
    
    Args:
        original: 原始文本
        corrected: 修订后的文本
        
    Returns:
        Tuple[bool, str]: (是否接受, 说明)
    """
    if not original or not corrected:
        return False, "文本为空"

    if original == corrected:
        return False, "两者完全一致"

    if len(corrected) <= MIN_CHARS_IGNORE:
        return False, f"修订文本长度 <= {MIN_CHARS_IGNORE}"

    if len(corrected) <= AUTO_ACCEPT_THRESHOLD:
        return True, "短文本直接接受"

    # 长度差异判定
    if len(corrected) > len(original) * MAX_LENGTH_GROWTH_RATIO:
        return False, f"修订文本长度增长过大 (>{MAX_LENGTH_GROWTH_RATIO:.0%})"

    # 计算差异比例
    try:
        ratio = difflib.SequenceMatcher(None, original, corrected).ratio()
        diff_ratio = 1.0 - ratio
    except Exception as exc:
        if config.DEBUG_MODE:
            print(f"⚠️ 计算文本相似度失败: {exc}")
        return False, "相似度计算失败"
        
    if diff_ratio > MAX_DIFF_RATIO:
        return False, f"改动比例过大 ({diff_ratio:.2%})"

    return True, f"改动比例 {diff_ratio:.2%}"


def _append_correction(original: str, corrected: str) -> None:
    """将纠错对写入文件。
    
    Args:
        original: 原始文本
        corrected: 修订后的文本
        
    Raises:
        OSError: 文件写入失败
        PermissionError: 无写入权限
    """
    CORRECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 基本的内容验证
    if len(original) > 10000 or len(corrected) > 10000:
        raise ValueError("文本长度超过限制 (10000 字符)")
    
    entry = (
        f"原文：{original}\n"
        f"→ 修订：{corrected}\n\n"
    )
    
    with CORRECTION_FILE.open("a", encoding="utf-8") as f:
        f.write(entry)


def capture_correction(
    original_text: Optional[str] = None,
    corrected_text: Optional[str] = None,
    *,
    verbose: bool = True,
) -> bool:
    """捕获并写入一次纠错。
    
    Args:
        original_text: 可显式传入原文；若缺省则读取 history.json 最新记录
        corrected_text: 可显式传入修订文本；若缺省则读取剪贴板内容
        verbose: 是否打印反馈信息
        
    Returns:
        bool: 是否成功写入
    """
    original = (original_text or _load_latest_history() or "").strip()
    corrected = (corrected_text or _get_clipboard_text() or "").strip()

    if verbose:
        max_preview = 60
        orig_preview = original[:max_preview] + ('...' if len(original) > max_preview else '')
        corr_preview = corrected[:max_preview] + ('...' if len(corrected) > max_preview else '')
        print(f"📝 原文: {orig_preview}")
        print(f"🖍️ 修订: {corr_preview}")

    accept, reason = _should_accept(original, corrected)
    if not accept:
        if verbose:
            print(f"⚠️ 忽略本次记忆：{reason}")
        return False

    try:
        _append_correction(original, corrected)
        if verbose:
            print(f"✅ 已记忆：{reason}")
        return True
    except (OSError, PermissionError) as exc:
        if verbose:
            print(f"❌ 写入 corrections.txt 失败（权限/磁盘问题）: {exc}")
        return False
    except ValueError as exc:
        if verbose:
            print(f"❌ 验证失败: {exc}")
        return False
    except Exception as exc:
        if verbose:
            print(f"❌ 写入时发生未预期错误: {exc}")
        return False


def start_hotkey_listener(hotkey: str) -> bool:
    """启动全局快捷键监听，触发剪贴板纠错记忆。
    
    Args:
        hotkey: 快捷键字符串，如 "<cmd>+<shift>+m"
        
    Returns:
        bool: 是否成功启动
    """
    global _hotkey_listener

    if pyperclip is None:
        print("⚠️ 未安装 pyperclip，无法启用纠错记忆热键")
        return False

    with _hotkey_lock:
        if _hotkey_listener is not None:
            # 已经启动
            return True

        def _on_trigger() -> None:
            """热键触发回调"""
            try:
                capture_correction()
            except Exception as exc:
                print(f"⚠️ 纠错记忆触发时发生错误: {exc}")

        try:
            _hotkey_listener = keyboard.GlobalHotKeys({hotkey: _on_trigger})
            _hotkey_listener.start()
            print(f"🧠 纠错记忆热键已启用: {hotkey}")
            return True
        except ValueError as exc:
            _hotkey_listener = None
            print(f"⚠️ 热键格式无效: {hotkey}, 错误: {exc}")
            return False
        except Exception as exc:
            _hotkey_listener = None
            print(f"⚠️ 启动纠错记忆热键失败: {exc}")
            return False


def stop_hotkey_listener() -> None:
    """停止纠错记忆热键监听。"""
    global _hotkey_listener
    
    with _hotkey_lock:
        if _hotkey_listener is not None:
            try:
                _hotkey_listener.stop()
            except Exception as exc:
                if config.DEBUG_MODE:
                    print(f"⚠️ 停止热键监听时出错: {exc}")
            finally:
                _hotkey_listener = None


if __name__ == "__main__":
    # 命令行测试入口
    capture_correction()