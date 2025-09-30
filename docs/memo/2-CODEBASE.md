# 代码库笔记

## 模型共享与异步后处理（2025-09-27）
- `service_registry.py` 新增统一的模型注册中心，`GeminiTranscriber` / `GeminiCorrector` / `DictionaryManager` 以单例形式复用，避免传统模式与会话模式重复初始化。
- `segment_processor.py` 将词典和纠错搬入后台线程队列，主处理线程只负责转录并把分段投入 `postprocess_queue`，并通过 `Condition` 精准唤醒等待，替代原来的轮询等待。
- 分段日志默认截断到 80 字符，减少终端泄露；`wait_for_completion` 改用条件变量后，终止阶段再无 100ms 轮询。
- `main.py` 在旧模式下走共享实例，初始化阶段输出信息保持一致。

## 录音与音频缓存（2025-09-27）
- `audio_recorder.py` 采用临时 WAV 文件落盘积累整段录音，并把实时块塞入有限长度 `queue`，长时间录音不再占用巨额内存。
- 录音停止后从临时文件读回浮点音频，调试模式可保留文件，否则自动清理；CLI 回调继续收到 `chunk_callback`。
- `SessionModeManager` 复用新的 `get_latest_audio_chunk()` 流程，无需处理 `_last_processed_chunk_index`。

## 快捷键配置（2025-09-29）
- `config.py` 默认的 `HOTKEY_LONG_PRESS_KEYS` 改为 `"left_option"`，新增 `HOTKEY_DISPLAY_LABELS` / `HOTKEY_PRIMARY_LABEL` 统一输出热键提示文案。
- `main.py`、`session_mode_manager.py`、`usage_guide.py`、`start.sh` 全量改用上述变量生成提示，脚本与终端 UI 不再手动维护“Command/Option”文案。
- `hotkey_listener.py` 仅接受单一修饰键配置（首个条目），检测到组合键（如 `⌘+C`、`⌥+Space`、`⌃⌥`）会直接阻止触发，确保只有独按该键时才会启动录音并在松开后停止。
- 2025-09-29：`main.py` 为 `_start_recording()` / `_stop_recording()` 引入后台动作队列，热键线程仅入队处理，避免阻塞 macOS 辅助功能事件导致监听器被系统关闭。
- 2025-09-29：`hotkey_listener.py` 新增 `ensure_running()`，`main.py` 主循环每 3 秒检测一次并在必要时自动重启监听器，降低 Option 长按后热键失效的频率。

## 分段输出与文本输入（2025-09-29）
- `session_mode_manager.py` 取消在 `_on_segment_output` 中再次调用 `TextInputManager`，由 `SegmentProcessor` 统一负责自动粘贴，仅保留完成事件通知，避免重复上屏。
- `text_input_manager.py` 调整 `input_text()` 的方法选择顺序，显式请求的 `InputMethod` 优先，`direct_type` 不再退回默认剪贴板，确保需要模拟敲击时可以生效。
- 2025-09-29：`TextInputManager._clipboard_paste_input` 触发 Cmd+V 时先经由 pynput，失败后自动回退 AppleScript，并延长等待与延迟恢复剪贴板，提升“剪贴板粘贴成功”日志的真实度。
- 2025-09-29：AppleScript 回退若捕获 “not trusted / accessibility” 输出即判定失败并提示到系统设置授予权限，杜绝日志误判自动粘贴成功。

## 启动脚本兼容性（2025-09-29）
- `start.sh` 改用 Python 子进程输出配合 `read` 解析热键提示，移除 Bash 4 专属的 `mapfile` 依赖，兼容 macOS 默认 Bash 3.2，避免 `mapfile: command not found`。
- 若热键信息解析失败，脚本会回退到 `Command`，保持原有的默认提示行为。
- 2025-09-29：启动脚本在执行前自动 `uv sync` 并加载 `.venv`（可通过 `UV_PROJECT_ENVIRONMENT` 覆盖），缺少 `uv` 时创建/启用本地虚拟环境后用 pip 补齐依赖，确保主程序始终在隔离环境中运行。脚本启动即会 `source .venv/bin/activate`（若存在），提前完成环境切换。

## 启动设备信息补齐（2025-09-28）
- `audio_recorder.py` 恢复 `get_device_info()`，启动阶段打印默认输入设备名称、Host API、设备默认采样率与最大通道数，方便校验麦克风权限和采样配置。
- 返回结构化字典，主流程可在日志或调试报告中复用这些字段。

## 重试队列瘦身（2025-09-27）
- `audio_retry_manager.py` 重试任务将音频保存为 `.npy` 文件，记录 SHA1 指纹，日志与状态文件不再包含原始波形。
- 任务成功或最终失败时自动清理临时文件；失败原因与重试日志带上指纹，方便排查但避免敏感文本。
- 状态恢复读取存档后自动重新排队，避免重量级音频遗失导致的死循环。

## 纠错记忆（2025-09-28）
- 新增 `correction_memory.py`：读取 `history.json` 最新文本与剪贴板修订，按“原文/→ 修订”格式写入 `logs/corrections.txt`。
- 过滤策略：长度 ≤3 的直接忽略；≤7 字自动接受；>7 字时校验长度增幅 ≤60%、差异比例 ≤50%，避免误复制长文本。
- `config.py` 增加 `ENABLE_CORRECTION_MEMORY` 与 `CORRECTION_MEMORY_HOTKEY`，`main.py` 启动时注册 `<cmd>+shift+m` 热键触发记忆。


## 会话报告输出
- `main.py` 新增 `_session_report` 汇总字典，将录音、转录、词典、剪贴板等阶段的结构化数据集中存储。
- `_display_final_results` 现在使用统一的边框排版输出行内摘要，默认展示耗时、块数、压缩体积以及字符统计；调试模式下仍可查看详细计时与替换统计。
- 2025-09-28：录音统计改为在 `stop_recording()` 完成后写入报告，新增分块计数与帧数实时刷新，避免跨会话复用旧数据。
- 2025-09-28：终端摘要行改为 `|` 分隔的精简形态，区分“热键时长 / 音频时长 / 分块 / 帧数 / 压缩体积”等关键指标，并在剪贴板、自动粘贴等分支统一格式。
- `GeminiTranscriber` 暴露 `last_run_info`，记录音频长度、压缩大小、API尝试次数等信息，供主流程生成报告。
- `AudioRecorder` 提供 `get_recording_stats()` 以便主流程获取块数和帧数，减少零散的即时打印。

## Gemini 健康检查
- `GeminiTranscriber.check_health()` 使用轻量 `generate_content` 调用验证鉴权与代理可达性，避免正式转录时报 401。
- `GeminiVoiceTranscriptionApp.start()` 在真正启动前执行健康检查，失败会给出 401/UNAUTHORIZED 的针对性提示并停止启动。

## 录音时长策略
- `_show_recording_warning` 现在保持静默，仅保留接口占位；避免长录音过程中出现警告提醒，仍保留自动超时终止。
- 短录音判定失败时不再弹出警告，仅静默回到待机，避免打断用户思路。
- `config.py` 将 `CHUNK_DURATION` 调整为 `1.0s`，录音缓冲刷新更频繁；同时把 `VAD_SILENCE_DURATION` 降为 `2.0s`，静音两秒即可触发收尾。

## 计时汇总格式
- 2025-09-28：`Timer.print_summary` 在汇总阶段时长的同时单独展示 `total_session`，杜绝重复累加导致的“总耗时翻倍”误导。

## Gemini 提示词策略
- `config.py` 中 `GEMINI_TRANSCRIPTION_PROMPT` 更新为简体中文夹杂自然 English 的混合语气，确保基础输出就是 Chinese+English 融合，同时继续强调指令遵从与缺失反馈。
- 2025-09-28：提示词重写为“必删/保留/格式”三段结构，明确“注意”说明整句删除的优先级，并附简明示例，避免模型误保留补充解释。
- 2025-09-29：`gemini_transcriber.py` 追加 `history.json` 最新两条文本作为上下文，可在 `config.py` 通过 `PROMPT_HISTORY_LIMIT` / `PROMPT_HISTORY_MAX_CHARS` 调整注入数量与长度。

## 自动粘贴策略
- `_auto_paste_text` 统一对文本执行 `TextInputManager._sanitize_clipboard_text` 后再去重，避免因标点差异触发重复粘贴。
- 原始转录不再立即粘贴，只在词典/纠错完成后输出最终清洗版本，必要时才回退到原始文本。
- `text_input_manager.py` 缩短剪贴板粘贴阶段的等待（复制、按键、恢复剪贴板）至 0.05~0.2 秒量级，整体粘贴耗时下降。
- 2025-09-28：`_sanitize_clipboard_text` 仅裁剪首尾空白，保留句末标点，修复终端结果缺少“。”的问题。
- 2025-09-29：一口气模式在会话收尾时也调用 `_auto_paste_text`，确保最终整段文本自动粘贴到光标位置。

## REST 伪流式设计（无 Realtime）
- 目标：在不启用 WebSocket/WebRTC/gRPC Realtime 的前提下，将端到端可见延迟压到 0.6~1.2s。
- 思路：小粒度分段 + 并行请求 + 差分上屏，模拟“增量吐字”的体验。

实现要点（拟实现）：
- VAD 端点提前：`VAD_SILENCE_DURATION` 降到 0.6~0.8s，`VAD_ANALYSIS_WINDOW` 降到 0.05s，尽快收尾；必要时将 `VAD_MIN_SEGMENT_DURATION` 降到 0.6s。
- 微提交窗口：说话进行中每 300~400ms 做一次“滚动窗口”微提交（lookback 1.0~1.5s，overlap 0.3~0.5s），发起一次短音频 REST 调用；静音落地后再做终结提交。
- 差分上屏：维护一个“已提交文本长度”的游标，后续结果仅对最后 N 字符做修订并追加新文本；上屏前做 LCS/LCP 对齐，限制回滚范围，减少闪烁。
- 轻量后处理：微提交阶段默认不跑纠错（或只跑词典替换），终结提交再做纠错/重写，UI 灰显→转正。
- 顺序保障：微提交阶段 `SEGMENT_MAX_CONCURRENT` 设为 1，保持输出有序；后台复核另起并发。
- 请求复用：保持 HTTP/2 长连接（`google-genai` 默认支持），控制 payload ≤ 200~400ms 的 WAV/FLAC；必要时在客户端先做 16k 单声道、幅值归一化。

配置建议（对应文件与键）：
- `config.py:116` 将 `VAD_SILENCE_DURATION` 调整至 `0.6~0.8`；`config.py:118` 将 `VAD_ANALYSIS_WINDOW` 调整至 `0.05`；视情况将 `config.py:117` `VAD_MIN_SEGMENT_DURATION` 调整至 `0.6`。
- 新增开关（建议）：`REST_PSEUDO_STREAMING_ENABLED`、`MICRO_COMMIT_INTERVAL_MS`、`LOOKBACK_WINDOW_S`、`COMMIT_REPAIR_CHARS`、`ENABLE_INTERIM_CORRECTION`、`ENABLE_INTERIM_DICTIONARY`。

模块改动草案：
- `voice_activity_detector.py`：在说话态周期性触发“微提交”回调（新增 `on_interim_segment`），构造含 `interim=True` 的 `VoiceSegment` 元数据；静音后触发最终 `on_segment_complete`。
- `segment_processor.py`：识别 `interim=True` 的分段时只做轻量处理与差分上屏；最终分段再跑词典/纠错并替换末尾 N 字符。
- `gemini_transcriber.py`：新增 `transcribe_with_context(audio_bytes, prev_text)` 以提示模型“仅续写/少回滚”，减少重复文本；限制 `max_output_tokens`（如 256）。

度量与预期：
- 100ms 采集 + 70~120ms 传输 + 250~450ms 推理 + 100ms 上屏，典型首字延迟 0.6~0.9s；静音落地后复核在后台 0.7~1.2s 完成。
