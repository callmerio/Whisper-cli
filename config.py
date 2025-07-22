#!/usr/bin/env python3
"""
配置文件 - 实时语音转录系统
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 项目路径
PROJECT_ROOT = Path(__file__).parent
DICTIONARY_FILE = PROJECT_ROOT / "dic.txt"

# 音频配置
SAMPLE_RATE = 16000  # whisper 推荐采样率
CHANNELS = 1  # 单声道
CHUNK_DURATION = 2.0  # 分段时长（秒）
BUFFER_DURATION = 30.0  # 缓冲区时长（秒）

# Whisper 配置  
WHISPER_MODEL = "turbo"  # 使用 turbo 模型
WHISPER_MODEL_PATH = "/Users/bigdan/Library/Application Support/MacWhisper/models/ggml-model-whisper-turbo.bin"  # turbo 模型路径
WHISPER_LANGUAGE = "zh"  # 中文
WHISPER_OUTPUT_FORMAT = "txt"  # 输出格式
WHISPER_ENABLE_PUNCTUATION = True  # 启用标点符号
WHISPER_THREADS = 4  # 处理线程数

# 快捷键配置
HOTKEY_COMBINATION = ["option", "r"]  # Option+R

# 用户词典配置
DICTIONARY_WEIGHT_THRESHOLD = 0.6  # 相似度阈值
DICTIONARY_MAX_WEIGHT = 0.5  # 最大权重影响（避免过度替换）

# 显示配置 - 简化
SHOW_PARTIAL_RESULTS = False  # 关闭实时显示，只在最后显示结果

# 后处理配置
ENABLE_GEMINI_CORRECTION = True  # 启用Gemini纠错
GEMINI_MODEL = "gemini-2.0-flash-exp"  # Gemini模型
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')  # 从环境变量读取API密钥

# 代理配置
USE_PROXY = True  # 启用代理
HTTP_PROXY = os.getenv('HTTP_PROXY', os.getenv('http_proxy', ''))  # HTTP代理
HTTPS_PROXY = os.getenv('HTTPS_PROXY', os.getenv('https_proxy', ''))  # HTTPS代理

# 剪贴板配置
ENABLE_CLIPBOARD = True  # 启用剪贴板功能
CLIPBOARD_RAW_FIRST = True  # 先复制原始转录，后覆盖纠错结果

# Gemini纠错提示词配置
GEMINI_CORRECTION_PROMPT = """请对以下中文语音转录文本进行纠错和优化：

原始转录文本：
{text}

要求：
1. 纠正语音识别错误（同音字、近音字错误）
2. 添加合适的标点符号（句号、逗号、问号、感叹号等）
3. 修正语法错误和语序问题
4. 保持原意不变，不要添加原文中没有的内容
5. 输出标准简体中文
6. 保持自然的口语化表达

只输出纠错后的文本，不要添加任何说明或解释："""

# 调试配置
DEBUG_MODE = True  # 开启调试模式
LOG_AUDIO_FILES = False  # 是否保存音频文件用于调试