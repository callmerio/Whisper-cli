#!/usr/bin/env python3
"""
配置文件 - Gemini 语音转录系统
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 调试开关
PRINT_PROMPT_ON_TRANSCRIBE = True       # 每次转录前是否打印最终 Prompt（仅调试用）

# 项目路径
PROJECT_ROOT = Path(__file__).parent
DICTIONARY_FILE = PROJECT_ROOT / "dic.txt"

# 音频配置
SAMPLE_RATE = 16000  # 音频采样率
CHANNELS = 1  # 单声道0
CHUNK_DURATION = 1.0  # 分段时长（秒）
BUFFER_DURATION = 30.0  # 缓冲区时长（秒）

# 回归测试默认录音路径（可通过环境变量覆盖）
REGRESSION_AUDIO_PATH = Path(
    os.getenv('REGRESSION_AUDIO_PATH', str(PROJECT_ROOT / 'docs' / 'samples' / 'recent_recording.wav'))
)

# 快捷键配置
HOTKEY_LONG_PRESS_KEYS = [
    "left_option",
]  # 支持多项按键的“或”关系: "command", "left_command", "right_command", "option", "left_option", "right_option"
HOTKEY_LONG_PRESS_KEY = HOTKEY_LONG_PRESS_KEYS[0]  # 兼容旧逻辑
HOTKEY_LONG_PRESS_THRESHOLD = 0.03        # 长按阈值（秒）


def _normalize_hotkey_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


_HOTKEY_LABEL_MAP = {
    "option": "Option",
    "opt": "Option",
    "alt": "Option",
    "left_option": "Left Option",
    "option_left": "Left Option",
    "opt_l": "Left Option",
    "alt_l": "Left Option",
    "left_alt": "Left Option",
    "right_option": "Right Option",
    "option_right": "Right Option",
    "opt_r": "Right Option",
    "alt_r": "Right Option",
    "right_alt": "Right Option",
    "command": "Command",
    "cmd": "Command",
    "meta": "Command",
    "left_command": "Left Command",
    "command_left": "Left Command",
    "cmd_l": "Left Command",
    "right_command": "Right Command",
    "command_right": "Right Command",
    "cmd_r": "Right Command",
}


def _resolve_hotkey_label(name: str) -> str:
    normalized = _normalize_hotkey_name(name)
    return _HOTKEY_LABEL_MAP.get(normalized, name.replace("_", " ").title())


HOTKEY_DISPLAY_LABELS = [_resolve_hotkey_label(name) for name in HOTKEY_LONG_PRESS_KEYS]
HOTKEY_PRIMARY_LABEL = HOTKEY_DISPLAY_LABELS[0] if HOTKEY_DISPLAY_LABELS else "Command"

# 录音有效性配置
MIN_TRANSCRIPTION_DURATION = 1.0         # 录音时长不超过该值（秒）将跳过转录

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

GEMINI_TRANSCRIPTION_PROMPT = """请转录这段中文或英文音频，并严格按以下优先级输出简体中文文本（可含必要英文单词）：

高频词汇务必正确拼写, 同音词识别逻辑后输出 比如 (`其实我是疑问句，我再问这里有没`) 这里应该是`在问`

【必删】
1. 删除所有以“注意”开头的说明（包括“注意,”“注意：”“注意-”等），自“注意”及后续解释直到该句或分句结束全部移除，不保留解释文字。- 若“注意”后紧跟的是对前文实体（人名、品牌、术语、地点等）的解释、定义、补充说明，即便没有明显的句号或问号，也将整段说明删除。示例：“注意，柠檬喜喜就是柠檬的柠…” → 请删除从“注意”到说明结束的全部内容。
2. 若同一句或段落出现多个“注意”，请逐个删除，并整理多余空格或连续标点。

示例：
- 原文：“我要开吐吐车来南岸，注意，吐是呕吐的吐。” → “我要开吐吐车来南岸。”
- 原文：“嗯，这个流程完成了，注意：以后改成自动执行。” → “嗯，这个流程完成了。”

【保留】
3. 其余内容需处理原始语气和口语化表达（如“嗯”“哦”“啊”等），为保证通顺 可以清理一些。比如 `提供给嗯，Gemini。` -> `提供给Gemini。`
4. 自动补全恰当标点（句号、逗号、问号、感叹号、破折号、省略号等），并修正明显错别字或语法错误，不增删事实信息。

【格式】
5. 输出纯文本，不添加前后缀或额外说明；中文与英文混排时保持单词或缩写之间的空格/连字符（如“Gemini 2.5 Flash”或“flash-without-thinking”）。
6. 仅输出简体中文字符，不出现繁体字。
7. 如果是陈述句 末尾不要带上句号
"""


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
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", 3))
VAD_FRAME_MS = int(os.getenv("VAD_FRAME_MS", 30))
VAD_PADDING_MS = int(os.getenv("VAD_PADDING_MS", 300))
VAD_RATIO = float(os.getenv("VAD_RATIO", 0.75))
VAD_VOLUME_THRESHOLD = 0.01  # 音量阈值（0.001-0.1，越小越敏感）
VAD_SILENCE_DURATION = 2.0   # 静音检测时长（秒，用户可配置）
VAD_MIN_SEGMENT_DURATION = 1.0  # 最小分段时长（秒）
VAD_ANALYSIS_WINDOW = 0.1    # 分析窗口大小（秒）

# ==================== 分段处理器配置 ====================

# 分段处理基础配置
ENABLE_CORRECTION = os.getenv("ENABLE_CORRECTION", "True").lower() in ('true', '1', 't')
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

# ==================== 纠错记忆配置 ====================

ENABLE_CORRECTION_MEMORY = True          # 启用剪贴板纠错记忆
CORRECTION_MEMORY_HOTKEY = "<cmd>+<shift>+m"  # 触发学习的全局热键

# 纠错记忆阈值配置
CORRECTION_MIN_CHARS_IGNORE = 3          # 修订文本长度 <= 此值时忽略（避免误记录单字修改）
CORRECTION_AUTO_ACCEPT_THRESHOLD = 7     # 修订文本长度 <= 此值时直接接受（短文本更可能是有意修改）
CORRECTION_MAX_LENGTH_GROWTH_RATIO = 1.6 # 修订文本长度不得超过原文的倍数（防止粘贴错误内容）
CORRECTION_MAX_DIFF_RATIO = 0.5          # 允许的最大差异比例（0.5 = 50%，防止完全不相关的文本）

# ==================== Prompt 注入配置 ====================

INJECT_DICTIONARY_IN_PROMPT = True       # 在提示词中附加词典
INJECT_CORRECTIONS_IN_PROMPT = True      # 在提示词中附加纠错示例
INJECT_HISTORY_IN_PROMPT = True          # 在提示词尾部附加近期会话上下文
PROMPT_DICTIONARY_HEADER = (
    "词汇偏好（百分比表示推荐权重，0-100%，仅作为非强制建议：数值越高越倾向使用目标写法，仍需保持语义与语气通顺）："
)
PROMPT_CORRECTIONS_HEADER = (
    "示例纠错（反映用户喜欢的句式与格式，用于参考，不需逐字复述，仅在保持语义前提下优化表达）："
)
PROMPT_HISTORY_HEADER = (
    "近期会话上下文（按时间逆序，辅助理解说话者持续主题，仅供参考，不要重复整段）："
)
PROMPT_HISTORY_LIMIT = 2                 # 附加历史条目数量
PROMPT_HISTORY_MAX_CHARS = 300           # 单条历史最大字符数，超出将截断并加省略号

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


# ==================== 配置验证 ====================

def validate_config() -> None:
    """验证配置的合法性，在应用启动时调用。
    
    Raises:
        ValueError: 如果配置不合法
    """
    errors = []
    warnings = []
    
    # 关键配置检查
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY 未配置，无法使用 Gemini 服务")
    elif len(GEMINI_API_KEY) < 10:
        warnings.append("GEMINI_API_KEY 长度异常，可能配置错误")
    
    if not GEMINI_TRANSCRIPTION_API_KEY:
        errors.append("GEMINI_TRANSCRIPTION_API_KEY 未配置")
    
    # 数值范围检查
    if MIN_TRANSCRIPTION_DURATION < 0:
        errors.append("MIN_TRANSCRIPTION_DURATION 不能为负数")
    
    if HOTKEY_LONG_PRESS_THRESHOLD < 0.01:
        warnings.append(f"HOTKEY_LONG_PRESS_THRESHOLD ({HOTKEY_LONG_PRESS_THRESHOLD}s) 过小，可能导致误触发")
    elif HOTKEY_LONG_PRESS_THRESHOLD > 2.0:
        warnings.append(f"HOTKEY_LONG_PRESS_THRESHOLD ({HOTKEY_LONG_PRESS_THRESHOLD}s) 过大，影响用户体验")
    
    if MAX_RECORDING_DURATION < 60:
        errors.append("MAX_RECORDING_DURATION 不应小于 60 秒")
    
    if WARNING_RECORDING_DURATION >= MAX_RECORDING_DURATION:
        errors.append("WARNING_RECORDING_DURATION 应小于 MAX_RECORDING_DURATION")
    
    # 纠错记忆阈值检查
    if CORRECTION_MIN_CHARS_IGNORE < 0:
        errors.append("CORRECTION_MIN_CHARS_IGNORE 不能为负数")
    
    if CORRECTION_MAX_LENGTH_GROWTH_RATIO < 1.0:
        warnings.append("CORRECTION_MAX_LENGTH_GROWTH_RATIO < 1.0 将拒绝所有变长的修订")
    
    if CORRECTION_MAX_DIFF_RATIO < 0 or CORRECTION_MAX_DIFF_RATIO > 1:
        errors.append("CORRECTION_MAX_DIFF_RATIO 必须在 [0, 1] 范围内")
    
    # 文件路径检查
    if not PROJECT_ROOT.exists():
        errors.append(f"PROJECT_ROOT 路径不存在: {PROJECT_ROOT}")
    
    if not DICTIONARY_FILE.parent.exists():
        warnings.append(f"词典文件目录不存在: {DICTIONARY_FILE.parent}")
    
    # Gemini 模型配置检查
    valid_models = {m["name"] for m in GEMINI_AVAILABLE_MODELS}
    if GEMINI_TRANSCRIPTION_MODEL not in valid_models:
        warnings.append(
            f"GEMINI_TRANSCRIPTION_MODEL ({GEMINI_TRANSCRIPTION_MODEL}) "
            f"不在可用模型列表中: {valid_models}"
        )
    
    # 输出验证结果
    if warnings and DEBUG_MODE:
        print("⚠️ 配置警告:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)


# 在模块导入时自动验证（非测试环境）
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as exc:
        print(f"❌ {exc}")
        # 不直接退出，让调用方决定如何处理
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
