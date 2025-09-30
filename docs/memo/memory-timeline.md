# 记忆时间线

## 会话：主流程稳定化（2025-02-25）

- 2025-02-25：引入 `_session_report`，终端输出改为结构化报告。
- 2025-02-25：增加 Gemini 启动自检，拦截鉴权异常提示用户。
- 2025-02-25：关闭录音时长警告输出，保留超时自动停止。
- 2025-02-25：修复录音超时线程访问缺失属性的问题，并将短录音取消改为静默流程。
- 2025-02-25：自动粘贴使用清洗后的文本去重，仅在词典完成后输出最终版本。

## 会话：提示词混合语气调整（2025-09-27）

- 2025-09-27：更新 `GEMINI_TRANSCRIPTION_PROMPT`，默认输出调整为简体中文夹自然 English 的混合语气，并强调指令遵从与缺失反馈。

## 会话：热键配置增强（2025-09-27）

- 2025-09-27：允许在 `HOTKEY_LONG_PRESS_KEYS` 中配置 Command、Left Option 等长按触发键（按键之间为“或”关系），默认改为 Left Option。
- 2025-09-28：重新将默认热键设回 Command，并备注可通过配置切换，保持启动脚本与 README 指引一致。
- 2025-09-29：默认热键再次调整为 Left Option，并在 `config.py` 暴露 `HOTKEY_DISPLAY_LABELS` / `HOTKEY_PRIMARY_LABEL`，供终端与脚本统一引用。
- 2025-09-29：`main.py`、`session_mode_manager.py`、`usage_guide.py`、`start.sh` 等输出全部改用热键变量映射，提示文案会随配置同步更新。
- 2025-09-29：`hotkey_listener.py` 限制为单一修饰键长按触发，组合键（如 `⌘+C`、`⌥+Space`、`⌃⌥`）均被拦截，确保只有独按目标键才会开始并在松开后停止录音。
- 2025-09-29：为避免 macOS `CGEvent` 超时禁用监听，`main.py` 新增热键动作队列，按键事件入队后由后台线程执行 `_start/_stop_recording`，热键线程立刻返回。
- 2025-09-29：`hotkey_listener.py` 补充 `ensure_running()` 与自动重启日志，`main.py` 主循环定期巡检监听状态并在异常时重启，Option 长按后监控失效会自动恢复。

## 会话：录音与粘贴提速（2025-09-27）

- 2025-09-27：缩短录音分段为 1 秒并将静音收尾阈值调到 2 秒，同时精简剪贴板粘贴延迟，加快整体响应时间。
- 2025-09-28：`TextInputManager` 粘贴前只裁剪空白，保留句末标点，避免输出缺少“。”。

## 会话：无Realtime低延迟方案研究（2025-09-27）

- 2025-09-27 10:40：确认现状为 REST 批处理，VAD 只在静音收尾时产出分段，导致 2s 端点延迟 + 模型耗时形成 2~3s 体感。
- 2025-09-27 10:46：给出“REST 伪流式”路线：微提交（每 300~400ms）+ 1.0~1.5s 滚动窗口 + 差分上屏，静音后再做纠错复核。
- 2025-09-27 10:52：建议将 `VAD_SILENCE_DURATION` 降至 0.6~0.8s，`VAD_ANALYSIS_WINDOW` 降至 0.05s；临时关闭微提交阶段纠错，仅启用词典替换。
- 2025-09-27 10:58：规划模块改动：VAD 增加 `on_interim_segment`；SegmentProcessor 识别 `interim` 分支做轻量处理与 LCS 差分；Transcriber 支持 `prev_text` 以减少重复。
- 2025-09-27 11:05：预期首字延迟压至 0.6~0.9s，静音落地复核 0.7~1.2s；保持 HTTP/2 连接与 16k 单声道，避免网络端开销。

## 会话：调用链降载与稳态优化（2025-09-27）

- 2025-09-27 11:22：新增 `service_registry.py`，将转录、纠错、词典改为单例复用，SegmentProcessor 转译线程只负责调用模型。
- 2025-09-27 11:28：SegmentProcessor 建立后台后处理队列与 `Condition` 唤醒机制，日志默认截断 80 字符，`wait_for_completion` 不再轮询。
- 2025-09-27 11:34：AudioRecorder 使用临时 WAV 落盘与有限队列供 VAD 消费，结束时按需清理文件，长录音内存占用收敛。
- 2025-09-27 11:40：AudioRetryManager 把音频序列化为 `.npy`、记录 SHA1 指纹并在成功/失败时清理文件，状态恢复可重排队。
- 2025-09-27 11:45：Gemini 客户端调试输出改为指纹，不再泄露 API Key 片段。
- 2025-09-27 11:52：修复启动时 `AudioRecorder.get_device_info` 缺失导致的异常，补全设备信息打印以兼容旧主流程。
- 2025-09-27 12:05：新增交接手册 `docs/memo/handoff.md`，整理上手步骤、配置要点、日志规范与近期改造摘要，便于新会话快速接管。

## 会话：启动设备信息修复（2025-09-28）

- 2025-09-28 08:32：恢复 `AudioRecorder.get_device_info()` 输出默认输入设备、Host API、默认采样率与通道配置，启动链路重新打印麦克风概览，方便校验权限与设备状态。

## 会话：提示词逻辑精炼（2025-09-28）

- 2025-09-28 09:10：重写 `GEMINI_TRANSCRIPTION_PROMPT`，将“注意”说明的整句删除设为最高优先级，提供简洁示例并保持语气保留规则，避免模型误把补充解释、注意段落保留下来。
- 2025-09-28 09:45：新增剪贴板纠错记忆流程（`correction_memory.py`），判定合格后写入 `logs/corrections.txt`，并在 `main.py` 注册 `<cmd>+shift+m` 热键，一键把“原文→修订”对记入知识库。
- 2025-09-28 10:30：提示词注入扩展，`gemini_transcriber.py` 将 `dic.txt` 与 `logs/corrections.txt` 全量拼接进请求 Prompt，保留百分比权重说明，并按配置可开关词典/示例注入。
- 2025-09-29：`gemini_transcriber.py` 读取 `history.json` 最新两条 `text` 注入提示词上下文，`config.py` 增加 `PROMPT_HISTORY_LIMIT` / `PROMPT_HISTORY_MAX_CHARS` 控制数量与截断规则。

## 会话：录音统计与日志清理（2025-09-28）

- 2025-09-28：`AudioRecorder` 将分块计数、帧数在会话结束时一次性写入 `_last_*` 指标，`get_recording_stats()` 不再泄漏上一次录音的数据。
- 2025-09-28：`main.py` 在停止录音后再汇总统计，最终报告显示“热键时长 / 音频时长 / 分块 / 帧数 / 原始体积”并用 `|` 分隔，去掉重复数字。
- 2025-09-28：`Timer.print_summary` 输出阶段合计与总耗时两行，避免把 `total_session` 再次计入导致总耗时翻倍。

## 会话：启动脚本兼容性修复（2025-09-29）

- 2025-09-29 18:29：`start.sh` 换用 `read` 解析 Python 输出，去掉 `mapfile` 依赖，兼容 macOS 默认 Bash 3.2，避免启动时出现 “mapfile: command not found”。
- 2025-09-29：启动脚本新增虚拟环境激活流程，默认执行 `uv sync` 并 source `.venv`（支持 `UV_PROJECT_ENVIRONMENT` 自定义路径），无 uv 时自动创建虚拟环境后再安装依赖。
- 2025-09-29：脚本开头若检测到 `.venv/bin/activate` 会立即 `source`，保证后续检查与安装都在本地虚拟环境内进行。

## 会话：分段输出一致性修复（2025-09-29）

- 2025-09-29：`session_mode_manager` 不再在 `_on_segment_output` 中调用 `TextInputManager`，避免自动粘贴执行两次，由 `SegmentProcessor` 统一输出。
- 2025-09-29：`TextInputManager.input_text` 优先使用显式 `InputMethod`，`direct_type` 保留模拟键入能力，不再被默认剪贴板覆盖。
- 2025-09-29：一口气模式完成后补充调用 `_auto_paste_text`，整段结果会自动上屏，无需手动粘贴。
- 2025-09-29：`TextInputManager._clipboard_paste_input` 失败时自动退回 AppleScript 触发 Cmd+V，并延长等待与剪贴板恢复节奏，减少"成功但未粘贴"的假阳性。
- 2025-09-29：AppleScript 回退若出现"not trusted / accessibility"警告即视为失败并输出权限指引，避免日志提示成功但实际未上屏。

## 会话：代码质量与安全性加固（2025-09-30）

Note: 本次会话执行全面代码审查，修复安全隐患和代码质量问题，提升系统稳定性和可维护性。

- 2025-09-30：**安全加固** - 将 API 密钥哈希算法从 SHA1 升级到 SHA256（12位指纹），提升密钥安全性（`gemini_corrector.py`、`gemini_transcriber.py`）。
- 2025-09-30：**线程安全** - 为 `correction_memory.py` 的全局热键监听器添加线程锁保护，避免多线程竞态条件。
- 2025-09-30：**错误处理** - 重构 `correction_memory.py` 错误处理逻辑，使用具体异常类型（`OSError`、`PermissionError`、`JSONDecodeError`）替代裸 `except Exception`，提升问题定位能力。
- 2025-09-30：**配置管理** - 将 `correction_memory.py` 的魔法数字（阈值常量）迁移到 `config.py`，新增 `CORRECTION_MIN_CHARS_IGNORE`、`CORRECTION_AUTO_ACCEPT_THRESHOLD`、`CORRECTION_MAX_LENGTH_GROWTH_RATIO`、`CORRECTION_MAX_DIFF_RATIO` 配置项，方便用户调整。
- 2025-09-30：**类型注解** - 为 `correction_memory.py` 和 `service_registry.py` 添加完整的类型注解和文档字符串，提升代码可读性和 IDE 支持。
- 2025-09-30：**服务注册中心** - 改进 `service_registry.py` 错误处理，单例初始化失败时抛出明确的 `RuntimeError` 并记录错误信息，避免返回未就绪的服务实例。
- 2025-09-30：**配置验证** - 在 `config.py` 新增 `validate_config()` 函数，自动检查关键配置（API 密钥、数值范围、文件路径）的合法性，模块导入时自动验证并输出警告或错误。
- 2025-09-30：**输入验证** - 为 `correction_memory.py` 的 `_append_correction()` 添加文本长度验证（上限 10000 字符），防止异常长文本写入。
- 2025-09-30：**代码规范** - 统一错误处理风格，在 DEBUG_MODE 下输出详细错误信息，生产环境保持简洁提示，符合 SOLID 原则和最佳实践。

## 会话：TypeScript 重构 Phase 1-2（2025-09-30）

Note: 开始 TypeScript 版本重构，创建 monorepo 结构，完成 Phase 1（基础设施）和 Phase 2（核心工具）的开发。目标是用现代化的 TypeScript 技术栈重写整个系统，提升类型安全性和可维护性。

### Phase 1: 基础设施与核心服务（2025-09-30 上午）

- 2025-09-30 09:00：**项目结构重组** - 将现有 Python 代码移动到 `python/` 目录，创建 `typescript/` 目录用于新版本开发，形成 monorepo 结构。
- 2025-09-30 09:15：**TypeScript 项目初始化** - 配置 `tsconfig.json`（strict mode）、`package.json`、`tsup.config.ts`（构建工具）、`.eslintrc.json`、`.prettierrc`，建立现代化开发工具链。
- 2025-09-30 09:30：**配置系统（Zod 验证）** - 实现 `src/core/config.ts`，使用 Zod Schema 进行运行时验证，支持 30+ 配置项，自动从 `.env` 加载并打印配置摘要。
- 2025-09-30 09:45：**增强日志系统** - 实现 `src/utils/logger.ts`，支持彩色输出（chalk）、日志级别控制（DEBUG/INFO/WARN/ERROR）、时间戳、子 Logger 功能。
- 2025-09-30 10:00：**Result 类型系统** - 实现 `src/utils/result.ts`，Rust 风格的错误处理（`Result<T, E>`），提供 `ok`/`err`/`isOk`/`isErr` 以及 `map`/`andThen`/`unwrap` 工具函数。
- 2025-09-30 10:15：**自定义错误体系** - 实现 `src/utils/errors.ts`，定义 `AppError` 基类和专用错误类型（`ConfigError`、`GeminiError`、`AudioError`、`FileSystemError` 等）。
- 2025-09-30 10:30：**Gemini 客户端封装** - 实现 `src/services/gemini-client.ts`，封装 Google Generative AI SDK，提供音频转录、文本纠错、健康检查功能，支持重试机制和 SHA256 密钥指纹。
- 2025-09-30 10:45：**主程序集成** - 创建 `src/index.ts`，集成配置加载、Gemini 客户端初始化、健康检查流程，成功启动并输出系统状态。

### 代理配置支持（2025-09-30 中午）

- 2025-09-30 11:00：**代理支持** - 发现 Google SDK 不支持自定义 baseUrl，添加 `SKIP_HEALTH_CHECK` 环境变量跳过健康检查，创建 `PROXY_GUIDE.md` 详细说明代理配置方法。
- 2025-09-30 11:15：**crypto 模块修复** - 修复 ESM 模式下的 crypto 导入（使用 `import { createHash } from 'crypto'` 替代 `require('crypto')`）。
- 2025-09-30 11:30：**测试验证** - 程序成功启动，配置验证通过，跳过健康检查模式正常工作，准备进入 Phase 2 开发。

### Phase 2: 核心工具（2025-09-30 下午）

- 2025-09-30 14:00：**文本处理工具** - 实现 `src/utils/text-utils.ts`，提供 Levenshtein 距离计算（`calculateSimilarity`）、文本规范化、中文检测、字数统计等工具函数。
- 2025-09-30 14:15：**文件系统适配器** - 实现 `src/utils/file-adapter.ts`，封装 fs/promises，提供 `readTextFile`/`writeTextFile`/`readJsonFile`/`writeJsonFile`/`fileExists` 等函数，全部返回 Result 类型。
- 2025-09-30 14:30：**词典管理器** - 实现 `src/managers/dictionary-manager.ts`（350+ 行），支持词典加载、智能替换、权重系统（0-100%）、相似度匹配、大小写保持等功能。
  - 支持两种词典格式：`词汇:权重%` 和 `原词汇->目标词汇:权重%`
  - 加载 15 个词典条目，平均权重 80.7%
  - 成功测试替换：\"谷歌\" → \"GOOGLE\"，\"微软\" → \"MICROSOFT\"
- 2025-09-30 15:00：**剪贴板管理器** - 实现 `src/managers/clipboard-manager.ts`（200+ 行），基于 clipboardy 库，提供：
  - `read()`/`write()` - 基础读写，自动备份
  - `restore()` - 恢复备份
  - `append()` - 追加内容
  - `writeSanitized()` - 清理并写入
  - `getStats()` - 统计信息（字符/词/行数）
- 2025-09-30 15:30：**CLI 命令行工具** - 实现 `src/cli.ts`（300+ 行），提供交互式测试命令：
  - `pnpm cli dictionary` - 测试词典替换（4 个测试用例全部通过）
  - `pnpm cli clipboard` - 测试剪贴板功能（读写/备份/恢复/统计全部正常）
  - `pnpm cli correction` - 测试 Gemini 纠错
  - `pnpm cli config` - 显示当前配置
  - `pnpm cli transcribe` - 转录功能（待音频模块实现）
- 2025-09-30 16:00：**集成测试** - 在主程序中集成词典和剪贴板测试，所有功能正常运行，系统初始化成功。

### 技术成果总结

**代码统计**：
- TypeScript 文件：15 个
- 总代码行数：~2000+ 行
- 测试覆盖：CLI 工具提供交互式测试
- 类型覆盖率：100%（严格模式）

**核心模块**：
1. 配置系统（Zod 验证，30+ 配置项）
2. 日志系统（彩色输出，分级控制）
3. Result 类型（Rust 风格错误处理）
4. 自定义错误体系（7 种错误类型）
5. Gemini 客户端（转录/纠错/健康检查）
6. 词典管理器（智能替换，权重系统）
7. 剪贴板管理器（完整的备份/恢复机制）
8. 文件系统适配器（Result 模式封装）
9. 文本处理工具（Levenshtein 距离等）

**Git 提交记录**：
- `b54f321` 🔒 代码质量与安全性加固
- `8a2e398` 🚀 项目重构：引入 TypeScript 版本
- `a5343df` 📝 更新 Roadmap: 添加 TypeScript 重构计划
- `b9a7f9c` ✨ Phase 1 完成：TypeScript 基础设施与核心服务
- `701ca6a` ✨ 配置代理支持和优化
- `399fa2b` ✨ 完成词典管理系统
- `3aae194` ✨ Phase 2 完成：剪贴板管理和 CLI 工具

**下一步计划（Phase 3）**：
- 音频录制模块（需要 Node.js 原生模块或外部库）
- 热键监听（macOS 平台集成）
- 会话管理器（状态机，多模式支持）
- 完整转录流程（端到端集成）

**经验总结**：
1. **类型安全是王道**：Zod Schema + TypeScript strict mode 在编译时捕获了大量潜在错误
2. **Result 模式优雅**：比 try-catch 更清晰，强制错误处理，代码可读性高
3. **工具链重要**：ESLint + Prettier + tsx 提供了流畅的开发体验
4. **测试驱动开发**：CLI 工具让每个模块都能独立测试，极大提升开发效率
5. **渐进式重构**：保留 Python 版本，TypeScript 版本独立开发，降低风险
