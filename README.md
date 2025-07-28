# 🎤 Whisper-CLI 实时语音转录系统

基于 whisper.cpp 的高性能中文语音转录系统，支持实时录音、AI纠错和剪贴板集成。

## ✨ 核心功能

- 🎙️ **实时录音** - 双击 Option 键控制录音开始/停止
- 🧠 **Whisper转录** - 使用 whisper.cpp 高精度语音识别
- 🤖 **AI智能纠错** - Gemini 2.5 Flash 自动纠错和标点优化
- 📋 **剪贴板集成** - 转录结果自动复制到剪贴板
- 🔔 **智能通知** - 多种通知方式：系统通知、声音提示、视觉反馈
- 📚 **用户词典** - 自定义词汇权重提升识别准确率
- ⏱️ **性能监控** - 详细的处理时间统计
- 🌐 **代理支持** - 支持系统代理访问AI服务

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- macOS (支持全局快捷键)
- whisper.cpp 或 whisper-cli
- 音频输入设备

### 2. 安装依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 3. 安装 Whisper

```bash
# 使用 Homebrew 安装
brew install whisper-cpp

# 或下载预训练模型到指定路径
# 默认路径: ~/Library/Application Support/MacWhisper/models/
```

### 4. 配置环境

```bash
# 复制环境配置文件
cp .env.sample .env

# 编辑 .env 文件，设置 Gemini API 密钥
# GEMINI_API_KEY=your_gemini_api_key_here

# 或使用配置脚本
./setup_env.sh your_gemini_api_key
```

### 5. 启动应用

#### 方式一：智能启动 (推荐)
```bash
./start.sh
```
- 🔍 自动检查系统环境和依赖
- 📋 显示详细的配置状态  
- 📖 提供完整的使用指南
- ⚙️ 检测权限和配置问题

#### 方式二：快速启动
```bash
./quick-start.sh
# 或直接运行
uv run python main.py
```

## 🎯 使用方法

1. **启动应用** - 运行启动脚本
2. **开始录音** - 双击 Option 键
3. **停止录音** - 再次双击 Option 键
4. **获取结果** - 转录完成后自动复制到剪贴板
5. **粘贴使用** - 在任意应用中 Cmd+V 粘贴结果

## ⚙️ 配置选项

### 基础配置 (`config.py`)

```python
# 音频设置
SAMPLE_RATE = 16000  # 采样率
CHANNELS = 1         # 声道数

# Whisper 设置
WHISPER_MODEL = "turbo"          # 模型类型
WHISPER_LANGUAGE = "zh"          # 识别语言

# 功能开关
ENABLE_GEMINI_CORRECTION = True  # AI纠错
ENABLE_CLIPBOARD = True          # 剪贴板
USE_PROXY = True                 # 代理支持

# 通知设置
ENABLE_NOTIFICATIONS = True       # 通知系统
ENABLE_SYSTEM_NOTIFICATIONS = True  # 系统通知
ENABLE_SOUND_NOTIFICATIONS = True   # 声音提示
ENABLE_VISUAL_NOTIFICATIONS = True  # 视觉反馈

# 调试模式
DEBUG_MODE = False               # 调试信息
```

### 用户词典 (`dic.txt`)

```
测试 40%
语音 35%
转录 40%
效果 30%
# 格式: 词汇 权重%
```

### 环境变量 (`.env`)

```bash
# Gemini API 密钥
GEMINI_API_KEY=your_api_key_here

# 代理设置 (可选)
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

## 📊 性能特点

- **录音无时长限制** - 支持长时间连续录音
- **毫秒级计时** - 精确的性能分析
- **内存优化** - 动态音频缓冲
- **多线程处理** - 并发音频处理

### 典型处理时间

- 录音: 实时
- Whisper转录: ~0.3x 音频时长
- Gemini纠错: ~1-3秒
- 剪贴板操作: <10ms

## 🛠️ 工具脚本

- `proxy_test.py` - 代理连接测试
- `setup_env.sh` - 环境配置助手
- `timer_utils.py` - 计时工具模块

## 🔧 故障排除

### 常见问题

1. **快捷键无响应**
   - 检查辅助功能权限 (系统偏好设置 > 安全性与隐私 > 辅助功能)

2. **Whisper转录失败**
   - 确认 whisper-cli 安装: `which whisper-cli`
   - 检查模型文件路径

3. **Gemini纠错失败**
   - 验证API密钥设置
   - 测试代理连接: `python proxy_test.py`

4. **音频录制问题**
   - 检查麦克风权限
   - 确认音频设备可用

### 调试模式

启用详细日志:
```python
DEBUG_MODE = True  # 在 config.py 中设置
```

## 📝 更新日志

### v1.0.0
- ✅ 实时语音转录
- ✅ Gemini AI纠错
- ✅ 剪贴板集成
- ✅ 用户词典支持
- ✅ 性能计时统计
- ✅ 代理支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**🎯 享受高效的语音转录体验！**