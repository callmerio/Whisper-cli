# 交接手册（Whisper-cli）

本手册面向新加入会话/开发者，聚焦快速上手、健康运行与近期改造要点。

## 一、项目速览

- 启动入口：`main.py`（热键、录音、转录、上屏、传统/会话模式）
- 关键模块：
  - 录音：`audio_recorder.py`（临时 WAV 落盘 + 实时块队列）
  - 转录：`gemini_transcriber.py`（Gemini 2.5 Flash 系列）
  - 纠错：`gemini_corrector.py`（可选二次润色）
  - 词典：`dictionary_manager.py`（相似度 + 权重替换）
  - 会话：`session_mode_manager.py`（一口气/逐步上屏）
  - 分段：`segment_processor.py`（前台转录线程 + 后台后处理队列）
  - 重试：`audio_retry_manager.py`（指数退避，.npy 轻量存储）
  - 文本输出：`text_input_manager.py`（剪贴板/直打，macOS 辅助权限）
  - 单例注册：`service_registry.py`（复用转录/纠错/词典实例）

## 二、环境与运行

- 依赖安装（推荐）：`uv sync`
- 或虚拟环境：
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
- 启动：`./start.sh` 或 `python main.py`
- 快捷键：默认按住 Left Option 开始录音（`config.py:29` 可改）

## 三、配置要点

- 必需环境变量：`.env` 中设置 `GEMINI_API_KEY`
- 主要开关在 `config.py`：
  - 音频：`SAMPLE_RATE=16000`, `CHANNELS=1`, `CHUNK_DURATION`
  - 模型：`GEMINI_TRANSCRIPTION_MODEL`, `ENABLE_GEMINI_CORRECTION`
  - 分段：`SEGMENT_ENABLE_*`, `SEGMENT_MAX_CONCURRENT`
  - VAD：`VAD_*`
  - 输入：`TEXT_INPUT_METHOD`（`clipboard`/`direct_type`）
  - 代理：`USE_PROXY`, `HTTP[S]_PROXY`
  - 调试：`DEBUG_MODE`

## 四、健康检查与权限

- macOS 需授权“辅助功能”（键盘输入/粘贴）与“麦克风”。
- 启动自检：`GeminiTranscriber.check_health()`；设备信息打印：`audio_recorder.py:get_device_info()`。
- 若遇 PEP 668 安装限制，优先使用 `uv sync` 或 `.venv` 再 `pip install`。

## 五、日志与数据

- 历史文本：`logs/history.json`
- 重试状态：`logs/retry_queue.json`（仅元数据 + 指纹）
- 重试音频：`logs/retry_audio/*.npy`（成功/最终失败后自动清理）
- 临时录音：`logs/recordings/*.wav`（默认结束清理；`LOG_AUDIO_FILES=True` 保留）
- 安全输出：密钥仅打印指纹，不输出明文。

## 六、近期改造（性能/稳定/体验）

- 单例共享：`service_registry.py` 统一提供模型/词典实例，避免重复初始化。
- 异步后处理：`segment_processor.py` 新增 `postprocess_queue` 与后台线程，`Condition` 精准唤醒，替代轮询等待。
- 录音内存收敛：`audio_recorder.py` 落盘累计整段 + 限长队列供 VAD。
- 重试瘦身：`audio_retry_manager.py` 存 `.npy` + SHA1 指纹，任务收尾清理文件，支持状态恢复重排队。
- 安全日志：`gemini_transcriber.py`/`gemini_corrector.py` 打印 API Key 指纹。
- 兼容修复：补齐 `AudioRecorder.get_device_info()`，避免启动异常。

## 七、已知注意点

- 词典替换在长文本/大词典时开销较高，建议仅保留核心术语。
- 剪贴板粘贴留有 `delay_before` 缓冲，避免切前台时丢字。
- Realtime 未启用，`docs/memo/2-CODEBASE.md` 附“REST 伪流式”设计草案可按需推进。

## 八、快速验证

- 启动：`python main.py`，按住 Left Option 录音，松开自动粘贴。
- 重试回归：`python test_retry_system.py`（需 `numpy` 就绪）。

## 九、习惯与约定

- 每次功能变更需同步：
  - `docs/memo/2-CODEBASE.md`（技术变更点）
  - `docs/memo/memory-timeline.md`（时间线）
- 提交信息：命令式，<=72 字，可用 emoji 前缀。

## 十、下一步建议

- 最小可用“伪流式”实现（微提交 + 差分上屏）。
- 词典侧增量缓存/索引以降低替换成本。
- 端到端耗时基线对比，固化性能阈值。

