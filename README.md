# 🎤 Gemini 语音转录系统

基于 Google Gemini-2.5-Flash 的高性能中文语音转录系统，支持实时录音、提示词内联润色和剪贴板集成。

> 📢 **项目重构中**: 正在开发 TypeScript 版本，提供更好的类型安全和跨平台支持！
>
> - 🐍 **Python 版本**: `python/` 目录（当前稳定版本）
> - 🚀 **TypeScript 版本**: `typescript/` 目录（开发中）

## ✨ 核心功能

- 🎙️ **实时录音** - 按住 Left Option 键录音，松开自动结束（可在 `config.HOTKEY_LONG_PRESS_KEYS` 调整）
- 🧠 **Gemini转录** - 使用 Gemini-2.5-Flash 云端高精度语音识别
- 🤖 **提示词内联润色** - Gemini 转录阶段直接完成纠错和标点优化
- 📋 **剪贴板集成** - 转录结果自动复制到剪贴板
- 🔔 **智能通知** - 多种通知方式：系统通知、声音提示、视觉反馈
- 📚 **用户词典** - 自定义词汇权重提升识别准确率
- ⏱️ **性能监控** - 详细的处理时间统计和自动重试机制
- 🌐 **代理支持** - 支持系统代理访问AI服务
- ⚙️ **智能选择** - 启动时可选择模型和思考模式

## 🚀 快速开始

### Python 版本（当前稳定版）

#### 1. 环境要求

- Python 3.8+
- macOS (支持全局快捷键)
- Google Gemini API 密钥
- 音频输入设备

#### 2. 安装依赖

```bash
cd python

# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install google-genai python-dotenv pynput sounddevice numpy pyperclip
```

#### 3. 配置 API 密钥

在 `python/` 目录创建 `.env` 文件：

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

获取 API 密钥：<https://aistudio.google.com/app/apikey>

#### 4. 启动程序

```bash
cd python
./start.sh
```

### TypeScript 版本（开发中）

```bash
cd typescript

# 安装依赖
pnpm install  # 或 npm install

# 开发模式
pnpm dev

# 查看详细文档
cat README.md
```

详细重构计划：[`docs/memo/TS_REFACTOR_PLAN.md`](docs/memo/TS_REFACTOR_PLAN.md)

## 🎯 使用方法

### 基础操作

1. 运行 `./start.sh` 启动系统
2. 在启动时选择转录模型和思考模式
3. 按住 **Left Option 键** 开始录音
4. 松开 **Left Option 键** 停止录音
5. 系统自动转录并粘贴到光标位置，同时备份剪贴板

### 模型选择

启动时可选择三种模式：

**📋 转录模型选择:**

- **Gemini 2.5 Pro** - 最高精度，功能最全面
- **Gemini 2.5 Flash (推荐)** - 平衡性能和精度  
- **Gemini 2.5 Flash Lite** - 最快速度，无思考模式

**🧠 思考模式选择:**

- **快速模式 (推荐)** - 无思考，响应快速
- **平衡模式** - 适度思考，平衡速度和精度
- **精确模式** - 深度思考，最高精度

*注：Flash Lite 模式自动使用快速模式*

## 📁 项目结构

```
Whisper-cli/
├── python/                    # Python 版本（稳定）
│   ├── main.py               # 主程序
│   ├── start.sh              # 启动脚本
│   ├── config.py             # 配置文件
│   ├── gemini_transcriber.py # Gemini 转录器
│   ├── gemini_corrector.py   # Gemini 纠错器
│   ├── hotkey_listener.py    # 快捷键监听
│   ├── audio_recorder.py     # 音频录制
│   ├── dictionary_manager.py # 词典管理
│   ├── notification_utils.py # 通知工具
│   ├── dic.txt               # 用户词典
│   └── pyproject.toml        # 项目依赖
├── typescript/                # TypeScript 版本（开发中）
│   ├── src/                  # 源代码
│   │   ├── core/            # 核心业务逻辑
│   │   ├── services/        # 外部服务
│   │   ├── managers/        # 状态管理器
│   │   ├── utils/           # 工具函数
│   │   └── types/           # 类型定义
│   ├── tests/               # 测试文件
│   └── package.json         # 项目配置
├── docs/                      # 文档
│   └── memo/                 # 开发记录
│       ├── memory-timeline.md
│       ├── cards.md
│       └── TS_REFACTOR_PLAN.md  # TypeScript 重构计划
└── README.md                  # 本文件
```

## ⚙️ 配置说明

### 主要配置项

在 `config.py` 中可以调整：

- **模型配置**: 转录和纠错模型选择
- **音频设置**: 采样率、缓冲区大小等
- **快捷键**: 默认为按住 Left Option 键说话，松开即停止，可在 `config.HOTKEY_LONG_PRESS_KEYS` 配置多个别名（自动同步终端提示）
- **通知方式**: 系统通知、声音、视觉提示
- **词典设置**: 相似度阈值、权重影响
- **代理设置**: HTTP/HTTPS 代理配置

### 用户词典

编辑 `dic.txt` 添加专业词汇：

```
# 格式：词汇:权重
React:30.0%
JavaScript:35.0%
API:25.0%
数据库:30.0%
```

## 🔧 高级功能

### 错误处理与重试

- 自动检测网络错误并重试
- 智能识别 API 超时和服务故障
- 最大重试 3 次，间隔 2 秒

### 性能监控

- 详细的处理时间统计
- 分步计时：录音、转录、纠错、词典处理
- 调试模式显示完整性能分析

### 通知系统

- **系统通知**: macOS 通知中心弹窗
- **声音反馈**: 不同操作播放对应音效  
- **视觉提示**: 控制台状态显示

## 🤝 相比 Whisper 版本的优势

| 特性 | Gemini 版本 | Whisper 版本 |
|------|-------------|--------------|
| **依赖** | 无需本地模型 | 需要安装 whisper.cpp |
| **速度** | 云端并行处理 | 本地处理较慢 |
| **准确度** | 针对中文优化 | 通用模型 |
| **维护** | Google 持续更新 | 需要手动更新模型 |
| **配置** | 简单的 API 密钥 | 复杂的模型管理 |

## 📝 开发说明

### 核心模块

- **主程序** (`main.py`): 应用主循环和状态管理
- **转录器** (`gemini_transcriber.py`): Gemini 音频转录实现
- **纠错器** (`gemini_corrector.py`): Gemini 文本纠错实现
- **录音器** (`audio_recorder.py`): 音频采集和处理
- **快捷键** (`hotkey_listener.py`): 全局快捷键监听

### 自定义开发

可以通过修改配置文件和提示词来定制：

1. **转录提示词** (`GEMINI_TRANSCRIPTION_PROMPT`): 调整转录要求
2. **纠错提示词** (`GEMINI_CORRECTION_PROMPT`): 自定义纠错规则  
3. **模型选择**: 根据需要选择不同的 Gemini 模型
4. **思考模式**: 调整 thinking budget 平衡速度和质量

## 🐛 故障排除

### 常见问题

1. **权限问题**: 首次运行需要授权麦克风和辅助功能权限
2. **API 密钥**: 确保 Gemini API 密钥正确且有效
3. **网络问题**: 检查代理设置和网络连接
4. **音频设备**: 确保麦克风设备正常工作

### 调试模式

设置 `DEBUG_MODE = True` 查看详细日志：

- API 调用详情
- 音频文件信息  
- 性能统计数据
- 错误堆栈信息

## 📄 许可证

本项目仅供学习和研究使用。

---

🎉 **享受智能语音转录体验！** 如有问题请提交 Issue。
