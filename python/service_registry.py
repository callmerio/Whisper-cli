"""共享服务注册中心，用于管理全局复用的模型与处理器实例。"""

from __future__ import annotations

import sys
import threading
from typing import Optional

from gemini_transcriber import GeminiTranscriber
from gemini_corrector import GeminiCorrector
from dictionary_manager import DictionaryManager
import config


class _ServiceRegistry:
    """简单的线程安全单例容器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._transcriber: Optional[GeminiTranscriber] = None
        self._corrector: Optional[GeminiCorrector] = None
        self._dictionary: Optional[DictionaryManager] = None
        self._init_errors: list[str] = []

    def get_transcriber(self) -> GeminiTranscriber:
        """获取或创建 Gemini 转录器单例。
        
        Returns:
            GeminiTranscriber: 转录器实例
            
        Raises:
            RuntimeError: 如果转录器初始化失败
        """
        with self._lock:
            if self._transcriber is None:
                try:
                    self._transcriber = GeminiTranscriber()
                    if not self._transcriber.is_ready:
                        error_msg = "Gemini 转录器初始化失败：未就绪状态，请检查 GEMINI_API_KEY 配置"
                        self._init_errors.append(error_msg)
                        if config.DEBUG_MODE:
                            print(f"❌ {error_msg}")
                        raise RuntimeError(error_msg)
                except Exception as exc:
                    error_msg = f"Gemini 转录器初始化异常: {exc}"
                    self._init_errors.append(error_msg)
                    if config.DEBUG_MODE:
                        print(f"❌ {error_msg}")
                    raise RuntimeError(error_msg) from exc
            return self._transcriber

    def get_corrector(self) -> GeminiCorrector:
        """获取或创建 Gemini 纠错器单例。
        
        Returns:
            GeminiCorrector: 纠错器实例
            
        Raises:
            RuntimeError: 如果纠错器初始化失败
        """
        with self._lock:
            if self._corrector is None:
                try:
                    self._corrector = GeminiCorrector()
                    if not self._corrector.is_ready:
                        error_msg = "Gemini 纠错器初始化失败：未就绪状态，请检查 GEMINI_API_KEY 配置"
                        self._init_errors.append(error_msg)
                        if config.DEBUG_MODE:
                            print(f"❌ {error_msg}")
                        raise RuntimeError(error_msg)
                except Exception as exc:
                    error_msg = f"Gemini 纠错器初始化异常: {exc}"
                    self._init_errors.append(error_msg)
                    if config.DEBUG_MODE:
                        print(f"❌ {error_msg}")
                    raise RuntimeError(error_msg) from exc
            return self._corrector

    def get_dictionary(self) -> DictionaryManager:
        """获取或创建词典管理器单例。
        
        Returns:
            DictionaryManager: 词典管理器实例
            
        Raises:
            RuntimeError: 如果词典管理器初始化失败
        """
        with self._lock:
            if self._dictionary is None:
                try:
                    self._dictionary = DictionaryManager()
                except Exception as exc:
                    error_msg = f"词典管理器初始化异常: {exc}"
                    self._init_errors.append(error_msg)
                    if config.DEBUG_MODE:
                        print(f"❌ {error_msg}")
                    raise RuntimeError(error_msg) from exc
            return self._dictionary

    def get_init_errors(self) -> list[str]:
        """获取所有初始化错误列表。
        
        Returns:
            list[str]: 初始化错误信息列表
        """
        with self._lock:
            return self._init_errors.copy()

    def reset(self) -> None:
        """重置所有服务实例（主要用于测试）。"""
        with self._lock:
            self._transcriber = None
            self._corrector = None
            self._dictionary = None
            self._init_errors.clear()


_registry = _ServiceRegistry()


def get_transcriber() -> GeminiTranscriber:
    """获取 Gemini 转录器实例（线程安全）。
    
    Returns:
        GeminiTranscriber: 转录器单例
        
    Raises:
        RuntimeError: 初始化失败时抛出
    """
    return _registry.get_transcriber()


def get_corrector() -> GeminiCorrector:
    """获取 Gemini 纠错器实例（线程安全）。
    
    Returns:
        GeminiCorrector: 纠错器单例
        
    Raises:
        RuntimeError: 初始化失败时抛出
    """
    return _registry.get_corrector()


def get_dictionary() -> DictionaryManager:
    """获取词典管理器实例（线程安全）。
    
    Returns:
        DictionaryManager: 词典管理器单例
        
    Raises:
        RuntimeError: 初始化失败时抛出
    """
    return _registry.get_dictionary()


def get_init_errors() -> list[str]:
    """获取所有服务初始化错误。
    
    Returns:
        list[str]: 错误信息列表
    """
    return _registry.get_init_errors()


def reset_registry() -> None:
    """重置服务注册中心（测试用）。"""
    _registry.reset()