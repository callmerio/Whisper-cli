# Whisper CLI - TypeScript 版本

> 🚀 基于 Gemini-2.5-Flash 的智能语音转录系统 TypeScript 重构版

## ✨ 特性

- 🎯 **类型安全**：完整的 TypeScript 类型系统
- 🛡️ **错误处理**：强大的 Result 模式和异常处理
- 🧪 **测试完善**：单元测试 + 集成测试覆盖
- 📦 **模块化设计**：清晰的分层架构
- 🔧 **现代工具链**：ESLint + Prettier + Vitest

## 🚀 快速开始

### 安装依赖

```bash
# 使用 pnpm (推荐)
pnpm install

# 或使用 npm
npm install
```

### 配置环境变量

创建 `.env` 文件：

```env
# Gemini API 配置
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# 如果使用自定义 proxy/网关
# 注意: 官方 SDK 不支持直接修改 baseUrl
# 建议使用环境变量设置代理
# GEMINI_BASE_URL=http://localhost:3001/proxy/gemini
HTTP_PROXY=http://localhost:3001
HTTPS_PROXY=http://localhost:3001

# 热键配置
HOTKEY_KEY=left_option
HOTKEY_THRESHOLD=0.03

# 调试模式
DEBUG_MODE=true
```

### 使用代理访问 Gemini

如果你使用本地 proxy 或自建网关，有两种方式：

**方式 1: 环境变量代理（推荐）**

```bash
export HTTP_PROXY=http://localhost:3001
export HTTPS_PROXY=http://localhost:3001
pnpm dev
```

**方式 2: 使用 proxy-agent**

```bash
# 安装 proxy agent
pnpm add https-proxy-agent

# 代码中会自动使用环境变量中的代理设置
```

### 开发模式

```bash
pnpm dev
```

### 构建

```bash
pnpm build
```

### 运行测试

```bash
pnpm test
```

## 📁 项目结构

```
typescript/
├── src/
│   ├── core/          # 核心业务逻辑
│   │   └── config.ts  # 配置管理（Zod 验证）
│   ├── services/      # 外部服务
│   │   └── gemini-client.ts  # Gemini API 封装
│   ├── managers/      # 状态管理器
│   ├── utils/         # 工具函数
│   │   ├── logger.ts  # 日志系统
│   │   ├── result.ts  # Result 类型
│   │   └── errors.ts  # 错误类型
│   └── types/         # TypeScript 类型定义
├── tests/             # 测试文件
└── dist/              # 构建输出
```

## 🎯 已完成功能（Phase 1）

### ✅ 基础设施

- [x] 项目初始化和配置
- [x] TypeScript 严格模式
- [x] ESLint + Prettier
- [x] 开发工具链（tsup + tsx）

### ✅ 核心系统

- [x] 配置管理系统（Zod 验证）
- [x] 增强版日志系统（彩色、分级）
- [x] Result 类型错误处理
- [x] 自定义错误体系

### ✅ Gemini 服务

- [x] Gemini 客户端封装
- [x] 音频转录（带重试）
- [x] 文本纠错
- [x] 健康检查
- [x] SHA256 密钥指纹

## 🚧 开发中（Phase 2）

- [ ] 音频录制模块
- [ ] 词典管理器
- [ ] 热键监听
- [ ] 剪贴板集成

## 📝 使用示例

### 基础用法

```typescript
import { getConfig } from './core/config';
import { createGeminiClient } from './services/gemini-client';

// 1. 加载配置
const config = getConfig();

// 2. 创建 Gemini 客户端
const gemini = createGeminiClient(config.gemini);

// 3. 健康检查
const healthResult = await gemini.checkHealth();
if (isOk(healthResult)) {
  console.log('✅ Gemini 健康检查通过');
}

// 4. 转录音频
const audioBuffer = Buffer.from(audioData);
const result = await gemini.transcribeAudio({
  audioData: audioBuffer,
  mimeType: 'audio/wav',
});

if (isOk(result)) {
  console.log('转录结果:', result.data.text);
}
```

### Result 类型使用

```typescript
import { Result, ok, err, isOk } from './utils/result';

function divide(a: number, b: number): Result<number, Error> {
  if (b === 0) {
    return err(new Error('除数不能为零'));
  }
  return ok(a / b);
}

const result = divide(10, 2);
if (isOk(result)) {
  console.log('结果:', result.data);
} else {
  console.error('错误:', result.error.message);
}
```

## 🔧 配置项说明

### Gemini 配置

- `GEMINI_API_KEY` - API 密钥（必需）
- `GEMINI_MODEL` - 模型名称（默认: gemini-2.5-flash）
- `GEMINI_BASE_URL` - 自定义 API 端点（可选）
- `GEMINI_REQUEST_TIMEOUT` - 请求超时（默认: 30000ms）
- `GEMINI_MAX_RETRIES` - 最大重试次数（默认: 2）

### 热键配置

- `HOTKEY_KEY` - 热键名称（默认: left_option）
- `HOTKEY_THRESHOLD` - 长按阈值（默认: 0.03s）

### 音频配置

- `AUDIO_SAMPLE_RATE` - 采样率（默认: 16000Hz）
- `AUDIO_CHANNELS` - 声道数（默认: 1）

## 🐛 故障排除

### 1. Gemini API 连接失败

**问题**: `fetch failed` 或 `ECONNREFUSED`

**解决方案**:

- 检查 API 密钥是否正确
- 确认网络连接正常
- 如果使用 proxy，确保 proxy 正在运行
- 设置环境变量 `HTTP_PROXY` 和 `HTTPS_PROXY`

### 2. 配置验证失败

**问题**: `配置验证失败`

**解决方案**:

- 检查 `.env` 文件是否存在
- 确认所有必需的配置项都已设置
- 查看错误提示中的具体字段

### 3. 模块导入错误

**问题**: `Cannot find module`

**解决方案**:

```bash
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

## 📚 文档

- 重构计划：`../docs/memo/TS_REFACTOR_PLAN.md`
- Python 版本参考：`../python/`
- API 文档：运行 `pnpm docs` 生成

## 🛣️ 开发路线图

- [x] Phase 1: 基础设施（Week 1-2）
- [ ] Phase 2: 核心服务（Week 3-5）
- [ ] Phase 3: 业务逻辑（Week 6-8）
- [ ] Phase 4: 用户交互（Week 9-10）
- [ ] Phase 5: 性能优化（Week 11）
- [ ] Phase 6: 文档与发布（Week 12）

## 📝 License

MIT

---

🎉 **享受类型安全的语音转录体验！**
