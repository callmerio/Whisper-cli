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
│   ├── services/      # 外部服务（Gemini、音频等）
│   ├── managers/      # 状态管理器
│   ├── utils/         # 工具函数
│   └── types/         # TypeScript 类型定义
├── tests/             # 测试文件
└── dist/              # 构建输出
```

## 🔧 配置

复制 `.env.example` 到 `.env` 并配置：

```env
GEMINI_API_KEY=your_api_key_here
```

## 📚 文档

详细文档请参考：`../docs/memo/TS_REFACTOR_PLAN.md`

## 🛣️ 开发路线图

- [x] 项目初始化
- [ ] 核心配置系统
- [ ] Gemini 服务封装
- [ ] 音频录制模块
- [ ] 热键监听
- [ ] 完整工作流

## 📝 License

MIT
