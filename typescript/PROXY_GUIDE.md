# 🌐 代理配置指南

## 问题说明

Google Generative AI SDK 使用 Node.js 原生 fetch，而原生 fetch 不会自动识别 `HTTP_PROXY` 环境变量。

## 解决方案

### 方案 1：跳过健康检查（快速方案）

如果你的 proxy 正常工作，可以暂时跳过健康检查：

```bash
# 设置环境变量跳过健康检查
SKIP_HEALTH_CHECK=true pnpm dev
```

### 方案 2：使用 undici 代理（推荐）

安装 undici 的代理支持：

```bash
pnpm add undici

# 设置代理并运行
NODE_OPTIONS="--import ./proxy-setup.js" pnpm dev
```

创建 `proxy-setup.js`：
```javascript
import { setGlobalDispatcher, ProxyAgent } from 'undici';

const proxyAgent = new ProxyAgent('http://localhost:3001');
setGlobalDispatcher(proxyAgent);
```

### 方案 3：使用 global-agent

```bash
pnpm add global-agent

# 运行前设置
GLOBAL_AGENT_HTTP_PROXY=http://localhost:3001 \
NODE_OPTIONS="-r global-agent/bootstrap" \
pnpm dev
```

### 方案 4：直接配置（开发中）

修改代码使用自定义 fetch：

```typescript
import { fetch } from 'undici';
import { ProxyAgent } from 'undici';

const agent = new ProxyAgent('http://localhost:3001');
// 配置 Gemini 客户端使用自定义 fetch
```

## 临时测试

在 Python 版本中测试你的 proxy 是否正常工作：

```bash
cd ../python
python -c "
import os
os.environ['HTTPS_PROXY'] = 'http://localhost:3001'
import requests
print(requests.get('https://www.google.com').status_code)
"
```

## 当前状态

- ✅ Proxy 服务运行正常 (localhost:3001)
- ⚠️ Node.js fetch 不支持自动代理
- 🔧 需要额外配置才能使用代理

## 建议

**最快的解决方案**：先跳过健康检查，直接使用功能

```bash
# 在 .env 中添加
SKIP_HEALTH_CHECK=true

# 或在命令行
SKIP_HEALTH_CHECK=true pnpm dev
```
