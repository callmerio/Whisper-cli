#!/usr/bin/env python3
"""
配置文件 - Gemini 语音转录系统
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
SAMPLE_RATE = 16000  # 音频采样率
CHANNELS = 1  # 单声道
CHUNK_DURATION = 2.0  # 分段时长（秒）
BUFFER_DURATION = 30.0  # 缓冲区时长（秒）

# 快捷键配置
HOTKEY_LONG_PRESS_KEY = "command"       # 长按 Command 键启动录音
HOTKEY_LONG_PRESS_THRESHOLD = 0.03        # 长按阈值（秒）

# 录音有效性配置
MIN_TRANSCRIPTION_DURATION = 2.0         # 录音时长不超过该值（秒）将跳过转录

# 用户词典配置
DICTIONARY_WEIGHT_THRESHOLD = 0.6  # 相似度阈值
DICTIONARY_MAX_WEIGHT = 0.5  # 最大权重影响（避免过度替换）

# ==================== Gemini 配置 ====================

# Gemini 纠错配置
ENABLE_GEMINI_CORRECTION = False  # 默认直接在转录阶段完成润色，可按需开启二次纠错
GEMINI_MODEL = "gemini-2.5-flash-lite"  # Gemini 纠错模型
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')  # 从环境变量读取API密钥

# Gemini 转录模型配置
GEMINI_TRANSCRIPTION_MODEL = os.getenv('GEMINI_TRANSCRIPTION_MODEL', 'gemini-2.5-flash')  # 支持环境变量覆盖
GEMINI_TRANSCRIPTION_API_KEY = os.getenv('GEMINI_API_KEY', '')  # 使用相同的API密钥

# Gemini 可选模型列表
GEMINI_AVAILABLE_MODELS = [
    {
        "name": "gemini-2.5-pro",
        "description": "Pro模式 - 最高精度，功能最全面",
        "recommended": False,
        "supports_thinking": True
    },
    {
        "name": "gemini-2.5-flash", 
        "description": "Flash模式 - 平衡性能和精度",
        "recommended": True,
        "supports_thinking": True
    },
    {
        "name": "gemini-2.5-flash-lite",
        "description": "Flash Lite模式 - 最快速度",
        "recommended": False,
        "supports_thinking": False
    }
]

# Thinking 模式配置
GEMINI_THINKING_BUDGET = int(os.getenv('GEMINI_THINKING_BUDGET', '0'))  # 支持环境变量覆盖
GEMINI_THINKING_OPTIONS = [
    {"budget": 0, "name": "快速模式", "description": "无思考，响应快速"},
    {"budget": 5000, "name": "平衡模式", "description": "适度思考，平衡速度和精度"},
    {"budget": 10000, "name": "精确模式", "description": "深度思考，最高精度"}
]

# Gemini 音频转录参数
GEMINI_AUDIO_LANGUAGE = "zh"  # 音频语言设置
GEMINI_AUDIO_MAX_SIZE = 20 * 1024 * 1024  # 最大音频文件大小 20MB
GEMINI_AUDIO_FORMATS = ["wav", "mp3", "m4a", "flac"]  # 支持的音频格式

# Gemini 转录提示词
GEMINI_TRANSCRIPTION_PROMPT = """请转录这段中文音频，并直接完成以下处理：
1. 精准还原语音内容，保留原有语气和口语化表达
2. 自动添加恰当的标点符号（句号、逗号、问号、感叹号、破折号、省略号等）
3. 修正明显的听写错误（同音、近音、错别字）以及基础语法问题
4. 不要改变说话者的语气、态度或风格，不要增删额外信息
5. 使用简体中文输出纯文本结果，不要包含任何说明、前缀或后缀"""

# Gemini API 配置
GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', '')  # 从环境变量读取Base URL
GEMINI_REQUEST_TIMEOUT = 30  # 请求超时时间（秒）- 缩短超时时间
GEMINI_MAX_RETRIES = 2  # 最大重试次数 - 减少重试次数
GEMINI_RETRY_DELAY = 1  # 重试延迟（秒）- 减少重试延迟

# 性能优化配置
GEMINI_AUDIO_COMPRESSION_ENABLED = True  # 启用音频压缩
GEMINI_PARALLEL_PROCESSING_ENABLED = True  # 启用并行处理
GEMINI_CHUNK_SIZE_SECONDS = 60  # 分片大小（秒）
GEMINI_MAX_PARALLEL_CHUNKS = 3  # 最大并行处理的分片数

# ==================== 语音活动检测 (VAD) 配置 ====================

# VAD 基础配置
VAD_VOLUME_THRESHOLD = 0.01  # 音量阈值（0.001-0.1，越小越敏感）
VAD_SILENCE_DURATION = 4.0   # 静音检测时长（秒，用户可配置）
VAD_MIN_SEGMENT_DURATION = 1.0  # 最小分段时长（秒）
VAD_ANALYSIS_WINDOW = 0.1    # 分析窗口大小（秒）

# ==================== 分段处理器配置 ====================

# 分段处理基础配置
SEGMENT_ENABLE_CORRECTION = False  # 默认关闭分段纠错，依赖转录提示词直接产出润色结果
SEGMENT_ENABLE_DICTIONARY = True   # 启用分段词典处理
SEGMENT_ENABLE_AUTO_OUTPUT = True  # 启用自动输出到光标位置
SEGMENT_MAX_CONCURRENT = 3         # 最大并发分段处理数

# 分段输出配置
SEGMENT_OUTPUT_METHOD = "clipboard"  # 输出方法: "direct_type" | "clipboard" | "disabled"

# ==================== 文本输入管理器配置 ====================

# 文本输入基础配置
TEXT_INPUT_METHOD = "clipboard"        # 默认输入方法: "direct_type" | "clipboard" | "disabled"
TEXT_INPUT_DELAY = 0.1                   # 输入延迟（秒）
TEXT_INPUT_CLIPBOARD_BACKUP = True       # 是否备份到剪贴板
TEXT_INPUT_CHECK_PERMISSIONS = True      # 启动时检查权限
AUTO_PASTE_ENABLED = True                # 处理完成后自动粘贴到光标位置

# ==================== 会话模式配置 ====================

# 默认会话模式配置
DEFAULT_SESSION_MODE = "batch"          # 固定为一口气模式
DEFAULT_SILENCE_DURATION = 4.0          # 默认静音检测时长（秒）
DEFAULT_AUTO_OUTPUT_ENABLED = True      # 默认启用自动输出
DEFAULT_CLIPBOARD_BACKUP = True         # 默认启用剪贴板备份

# Gemini纠错润色提示词配置
GEMINI_CORRECTION_PROMPT = """请对以下中文语音转录文本进行纠错和基础润色：

原始转录文本：
{text}

要求：
1. 【语音识别纠错】纠正同音字、近音字、多音字等识别错误
2. 【标点符号优化】
   - 添加必要的句号、逗号、问号、感叹号
   - 使用破折号（——）表示明显的语音停顿或转折
   - 使用省略号（……）表示未说完的话
3. 【基础语法纠错】修正明显的语法错误和语序问题
4. 【保持原貌】严格保持说话者的语气、态度、用词习惯和表达风格

重要约束：
- 绝对不要改变说话者的语气和态度
- 不要替换俚语、网络用语、口语化表达（如"GG"保持为"GG"）
- 不要进行风格转换（口语转书面语等）
- 不要添加原文中没有的信息
- 只做最基础的错误纠正和标点添加

只输出纠错后的文本，不要添加任何说明："""

# ==================== 系统配置 ====================

# 代理配置
USE_PROXY = True  # 启用代理
HTTP_PROXY = os.getenv('HTTP_PROXY', os.getenv('http_proxy', ''))  # HTTP代理
HTTPS_PROXY = os.getenv('HTTPS_PROXY', os.getenv('https_proxy', ''))  # HTTPS代理

# 剪贴板配置
ENABLE_CLIPBOARD = True  # 启用剪贴板功能
CLIPBOARD_RAW_FIRST = True  # 先复制原始转录，后覆盖纠错结果

# 通知配置
ENABLE_NOTIFICATIONS = True  # 启用通知系统
ENABLE_SYSTEM_NOTIFICATIONS = True  # 启用系统通知（macOS/Linux/Windows）
ENABLE_SOUND_NOTIFICATIONS = True  # 启用声音提示
ENABLE_VISUAL_NOTIFICATIONS = True  # 启用视觉提示（控制台闪烁）

# 录音超时配置
MAX_RECORDING_DURATION = 7200  # 最大录音时长（秒），默认2小时
WARNING_RECORDING_DURATION = 6000  # 警告时长（秒），默认100分钟（录音1小时40分钟时提醒）
TIMEOUT_CHECK_INTERVAL = 60  # 超时检查间隔（秒），每分钟检查一次

# 调试配置
DEBUG_MODE = True  # 开启调试模式
LOG_AUDIO_FILES = False  # 是否保存音频文件用于调试
