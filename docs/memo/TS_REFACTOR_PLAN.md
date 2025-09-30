# TypeScript 重构方案设计

> 🎯 目标：将现有 Python 项目重构为 TypeScript，提升类型安全、跨平台兼容性和开发体验

---

## 📊 当前项目分析

### 核心模块

- **音频处理**：`audio_recorder.py`、`voice_activity_detector.py`
- **AI 服务**：`gemini_transcriber.py`、`gemini_corrector.py`
- **用户交互**：`hotkey_listener.py`、`text_input_manager.py`
- **数据管理**：`dictionary_manager.py`、`correction_memory.py`、`service_registry.py`
- **会话控制**：`session_mode_manager.py`、`segment_processor.py`
- **重试机制**：`audio_retry_manager.py`

### 主要依赖

- 音频：`sounddevice` + `numpy`
- 热键：`pynput`
- AI：`google-generativeai`
- 剪贴板：`pyperclip`
- macOS 交互：`pyobjc`

### 技术债务

- 缺少完整的单元测试覆盖
- 配置管理散落（虽已改善）
- 日志系统不够结构化
- 错误追踪依赖打印输出

---

## 🎨 三种重构方案

### 方案 A：同仓库独立目录（推荐✨）

**目录结构：**

```
Whisper-cli/
├── python/                    # 重命名现有代码
│   ├── main.py
│   ├── config.py
│   └── ...
├── typescript/                # 新的 TS 版本
│   ├── src/
│   │   ├── core/             # 核心业务逻辑
│   │   ├── services/         # 外部服务（Gemini、音频等）
│   │   ├── managers/         # 状态管理器
│   │   ├── utils/            # 工具函数
│   │   └── types/            # TypeScript 类型定义
│   ├── tests/                # 测试文件
│   ├── package.json
│   ├── tsconfig.json
│   └── README.md
├── docs/                      # 共享文档
├── .gitignore                 # 更新忽略规则
└── README.md                  # 主说明文档
```

**优点：**

- ✅ 保持 Git 历史连续性
- ✅ 方便对比两个版本
- ✅ 共享文档和配置
- ✅ 逐步迁移，风险可控

**缺点：**

- ⚠️ 仓库体积会增大
- ⚠️ 需要明确区分两个版本的维护状态

**适用场景：**

- 想保持代码历史和文档连贯性
- 需要频繁对比两个版本
- 团队协作，需要统一入口

---

### 方案 B：新建独立仓库

**结构：**

```
whisper-cli-ts/               # 全新仓库
├── src/
├── tests/
├── docs/
├── package.json
└── README.md
```

**优点：**

- ✅ 完全独立，架构自由
- ✅ 干净的 Git 历史
- ✅ 独立的版本管理
- ✅ 更清晰的项目定位

**缺点：**

- ⚠️ 失去原项目的提交历史
- ⚠️ 文档需要重新整理
- ⚠️ 需要维护两个仓库

**适用场景：**

- 重构幅度很大，几乎重写
- 想要全新开始，抛弃历史包袱
- 作为独立产品发布

---

### 方案 C：本地开发目录（快速验证）

**结构：**

```
Whisper-cli/
├── ts-prototype/             # 加入 .gitignore
│   └── ...                   # 本地开发，不提交
├── main.py
└── ...
```

**优点：**

- ✅ 快速启动，无需改动现有结构
- ✅ 验证可行性后再决定最终方案
- ✅ 不污染 Git 历史

**缺点：**

- ⚠️ 无版本控制（除非单独初始化）
- ⚠️ 团队协作困难
- ⚠️ 仅适合原型阶段

**适用场景：**

- 快速验证 TypeScript 可行性
- 个人探索，暂不确定是否完整迁移

---

## 🛠️ 技术栈选择（方案 A 详细设计）

### 运行时环境

```json
{
  "runtime": "Node.js 20+ LTS",
  "language": "TypeScript 5.0+",
  "package-manager": "pnpm (推荐) / npm / yarn"
}
```

### 核心依赖映射

| Python 库 | TypeScript 替代 | 说明 |
|-----------|----------------|------|
| `sounddevice` | `@discordjs/voice` + `node-record-lpcm16` | 音频录制 |
| `numpy` | `ndarray` / `mathjs` | 数值计算 |
| `pynput` | `node-global-key-listener` / `iohook` | 全局热键 |
| `pyperclip` | `clipboardy` | 剪贴板操作 |
| `google-generativeai` | `@google/generative-ai` (官方 TS SDK) | Gemini API |
| `pyobjc` | `@jitsi/robotjs` (跨平台) / `applescript` (macOS) | 系统交互 |

### 开发工具链

```json
{
  "bundler": "tsup / esbuild",
  "linter": "ESLint + Prettier",
  "formatter": "Prettier",
  "test": "Vitest / Jest",
  "docs": "TypeDoc",
  "ci": "GitHub Actions"
}
```

### 架构设计（改进）

#### 1. 分层架构

```
┌─────────────────────────────────────┐
│  CLI / GUI (Presentation Layer)    │
├─────────────────────────────────────┤
│  Application Layer                  │
│  - SessionManager                   │
│  - WorkflowOrchestrator             │
├─────────────────────────────────────┤
│  Domain Layer                       │
│  - AudioRecorder                    │
│  - TranscriptionService             │
│  - DictionaryManager                │
├─────────────────────────────────────┤
│  Infrastructure Layer               │
│  - GeminiClient                     │
│  - FileSystemAdapter                │
│  - ClipboardAdapter                 │
└─────────────────────────────────────┘
```

#### 2. 依赖注入（IoC）

使用 `inversify` 或 `tsyringe` 实现依赖注入，替代当前的 `service_registry.py`：

```typescript
// 示例
@injectable()
class TranscriptionService {
  constructor(
    @inject(TYPES.GeminiClient) private gemini: GeminiClient,
    @inject(TYPES.Logger) private logger: Logger
  ) {}
}
```

#### 3. 事件驱动架构

使用 `EventEmitter` 或 `RxJS` 实现事件总线：

```typescript
enum AppEvents {
  RECORDING_STARTED = 'recording:started',
  TRANSCRIPTION_COMPLETE = 'transcription:complete',
  ERROR_OCCURRED = 'error:occurred',
}

eventBus.on(AppEvents.TRANSCRIPTION_COMPLETE, (result) => {
  // 处理转录完成
});
```

#### 4. 配置管理

使用 `zod` 进行配置验证：

```typescript
import { z } from 'zod';

const ConfigSchema = z.object({
  gemini: z.object({
    apiKey: z.string().min(10),
    model: z.string(),
  }),
  hotkey: z.object({
    key: z.enum(['left_option', 'command']),
    threshold: z.number().min(0.01).max(2.0),
  }),
});

type Config = z.infer<typeof ConfigSchema>;
```

---

## 📋 迁移计划（12 周路线图）

### Phase 1: 基础设施（Week 1-2）

- [ ] 创建 TypeScript 项目结构
- [ ] 配置 TypeScript、ESLint、Prettier
- [ ] 设置测试框架（Vitest）
- [ ] 实现配置管理系统（Config + Validation）
- [ ] 实现日志系统（Winston / Pino）

### Phase 2: 核心服务（Week 3-5）

- [ ] 实现 GeminiClient（转录 + 纠错）
- [ ] 实现 AudioRecorder（录音 + VAD）
- [ ] 实现 DictionaryManager
- [ ] 实现 ClipboardManager
- [ ] 单元测试覆盖 > 80%

### Phase 3: 业务逻辑（Week 6-8）

- [ ] 实现 SessionManager（一口气模式）
- [ ] 实现 SegmentProcessor
- [ ] 实现 CorrectionMemory
- [ ] 实现 RetryManager
- [ ] 集成测试

### Phase 4: 用户交互（Week 9-10）

- [ ] 实现 HotkeyListener（全局热键）
- [ ] 实现 TextInputManager（自动粘贴）
- [ ] 实现通知系统
- [ ] CLI 界面优化

### Phase 5: 性能优化（Week 11）

- [ ] 音频处理优化
- [ ] 并发控制优化
- [ ] 内存管理优化
- [ ] 性能测试

### Phase 6: 文档与发布（Week 12）

- [ ] 完善 API 文档（TypeDoc）
- [ ] 编写用户指南
- [ ] 打包发布（pkg / nexe）
- [ ] GitHub Release

---

## 🧪 测试策略

### 单元测试（Vitest）

```typescript
describe('GeminiTranscriber', () => {
  it('should transcribe audio successfully', async () => {
    const transcriber = new GeminiTranscriber(mockConfig);
    const result = await transcriber.transcribe(mockAudioData);
    expect(result).toBeDefined();
    expect(result.text).toContain('测试文本');
  });
});
```

### 集成测试

```typescript
describe('Full Transcription Flow', () => {
  it('should complete end-to-end workflow', async () => {
    const session = await sessionManager.startRecording();
    await simulateAudioInput();
    await session.stop();
    expect(clipboard.read()).toContain('转录结果');
  });
});
```

### E2E 测试（Playwright）

- 模拟真实用户操作
- 热键触发测试
- 剪贴板验证

---

## 📦 项目初始化命令

### 方案 A：同仓库独立目录

```bash
# 1. 重组现有 Python 代码
mkdir python
git mv *.py python/
git mv pyproject.toml uv.lock python/

# 2. 创建 TypeScript 目录
mkdir -p typescript/src/{core,services,managers,utils,types}
mkdir -p typescript/tests

# 3. 初始化 TypeScript 项目
cd typescript
pnpm init
pnpm add -D typescript @types/node tsup vitest
pnpm add @google/generative-ai clipboardy node-global-key-listener

# 4. 创建配置文件
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
EOF

# 5. 更新 .gitignore
cat >> ../.gitignore << 'EOF'

# TypeScript
typescript/node_modules/
typescript/dist/
typescript/.turbo/
typescript/*.tsbuildinfo
EOF

# 6. 创建初始文件
cat > src/index.ts << 'EOF'
console.log('🚀 Whisper CLI TypeScript版本启动');
EOF

# 7. 测试运行
pnpm add -D tsx
pnpm tsx src/index.ts
```

---

## 🎯 核心改进点

相比 Python 版本，TypeScript 重构将带来：

### 1. 类型安全

```typescript
// Python: 运行时才发现类型错误
config.GEMINI_API_KEY  # 可能是 None

// TypeScript: 编译时就能发现
config.gemini.apiKey   // 类型检查，确保非空
```

### 2. 更好的 IDE 支持

- 自动补全
- 类型提示
- 重构工具
- 即时错误提示

### 3. 跨平台能力

- Node.js 天然跨平台
- 可以打包成独立可执行文件
- 更容易制作 Electron 版本

### 4. 现代化工具链

- 快速的构建工具（esbuild）
- 完善的测试框架（Vitest）
- 强大的包管理（pnpm）

### 5. 更好的错误处理

```typescript
// 使用 Result 模式
type Result<T, E = Error> = 
  | { success: true; data: T }
  | { success: false; error: E };

async function transcribe(audio: AudioData): Promise<Result<string>> {
  try {
    const result = await gemini.transcribe(audio);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error };
  }
}
```

---

## 💡 推荐方案

**小猫咪推荐：方案 A（同仓库独立目录）** ✨

**理由：**

1. 保持完整的开发历史和文档
2. 方便对比两个版本的实现差异
3. 可以逐步迁移，降低风险
4. 未来可以保留 Python 版本作为备用
5. 便于团队协作和知识传承

**初始化步骤：**

```bash
# 第一步：重组 Python 代码
./scripts/reorganize_python.sh

# 第二步：创建 TypeScript 项目
./scripts/init_typescript.sh

# 第三步：开始开发
cd typescript && pnpm dev
```

---

## 📝 后续讨论

主人，小猫咪觉得还需要讨论以下问题喵：

1. **是否需要 GUI 版本？**
   - 可以用 Electron 制作跨平台桌面应用
   - 或者保持 CLI 优先

2. **是否需要云同步？**
   - 词典、纠错记忆等数据是否云端同步
   - 可以集成 Firebase / Supabase

3. **是否需要插件系统？**
   - 允许用户自定义处理流程
   - 类似 VSCode 的扩展机制

4. **性能目标？**
   - 是否需要比 Python 版本更快
   - 音频处理是否使用 WebAssembly

主人想采用哪个方案呢喵~ (=^･ω･^=)♡
