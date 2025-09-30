# 进度跟踪

## 2025-09-27
- 调整 Gemini 转录提示词为简体中文融合 English 的混合语气，确保基础输出就符合 Chinese+English 风格，并补充缺失反馈约束。
  - 涉及模块：`config.py`、`docs/memo/2-CODEBASE.md`
  - 验证：`python -m compileall config.py`
- 支持配置化长按热键，`HOTKEY_LONG_PRESS_KEYS` 以“或”关系列出可触发按键，默认改为 Left Option，监听逻辑自动映射（Codex 执行）。
  - 涉及模块：`config.py`、`hotkey_listener.py`、`docs/memo/2-CODEBASE.md`
  - 验证：`python -m compileall config.py hotkey_listener.py`
- 缩短录音分段与静音收尾阈值，`CHUNK_DURATION=1.0s`、`VAD_SILENCE_DURATION=2.0s`，提升响应速度（Codex 执行）。
  - 涉及模块：`config.py`、`docs/memo/2-CODEBASE.md`
  - 验证：`python -m compileall config.py`
- 调整自动粘贴延迟，优化剪贴板复制与按键间隔，加快结果输出（Codex 执行）。
  - 涉及模块：`text_input_manager.py`、`docs/memo/2-CODEBASE.md`
  - 验证：`python -m compileall text_input_manager.py`

## 2025-02-25
- 优化会话报告输出，提供压缩的终端概要视图。
  - 涉及模块：`main.py`、`gemini_transcriber.py`、`audio_recorder.py`
  - 验证：`python -m compileall main.py gemini_transcriber.py audio_recorder.py`
- 启动前增加 Gemini 接口健康检查，提前捕获鉴权异常。
  - 涉及模块：`main.py`、`gemini_transcriber.py`
  - 验证：`python -m compileall main.py gemini_transcriber.py`
- 关闭录音时长预警输出，保持超时保护但不打扰用户。
  - 涉及模块：`main.py`
  - 验证：`python -m compileall main.py`
- 修复录音超时监控线程缺失属性导致的异常，并静默短录音取消流程。
  - 涉及模块：`main.py`
  - 验证：`python -m compileall main.py`
- 使用剪贴板清洗后的文本做粘贴去重，避免同一次转录出现重复粘贴。
  - 涉及模块：`main.py`
  - 验证：`python -m compileall main.py`
- 仅在词典/纠错完成后粘贴最终清洗文本，取消原始转录的提前粘贴。
  - 涉及模块：`main.py`
  - 验证：`python -m compileall main.py`
