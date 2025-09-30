/**
 * Whisper CLI - TypeScript 版本
 * 基于 Gemini-2.5-Flash 的智能语音转录系统
 */

import { getConfig, validateConfig, printConfigSummary } from './core/config';
import { createLogger } from './utils/logger';
import { createGeminiClient } from './services/gemini-client';
import { isErr } from './utils/result';
import { formatError } from './utils/errors';

const logger = createLogger('Main');

async function main(): Promise<void> {
  try {
    console.log('🎙️ Whisper CLI TypeScript');
    console.log('🚀 正在启动智能语音转录系统...\n');

    // 1. 加载配置
    logger.info('加载配置...');
    const config = getConfig();

    // 2. 验证配置
    const validation = validateConfig(config);
    if (!validation.valid) {
      logger.error('配置验证失败:');
      validation.errors.forEach((error) => logger.error(`  - ${error}`));
      process.exit(1);
    }

    // 3. 打印配置摘要
    printConfigSummary(config);

    // 4. 初始化 Gemini 客户端
    logger.info('初始化 Gemini 客户端...');
    const geminiClient = createGeminiClient(config.gemini);

    // 5. 健康检查
    logger.info('执行 Gemini 健康检查...');
    const healthResult = await geminiClient.checkHealth();

    if (isErr(healthResult)) {
      logger.error('Gemini 健康检查失败:', formatError(healthResult.error));
      process.exit(1);
    }

    logger.info('✅ Gemini 健康检查通过');

    // 6. 系统就绪
    console.log('\n' + '='.repeat(60));
    console.log('✅ 系统初始化成功！');
    console.log('='.repeat(60));
    console.log('\n📝 已完成的功能:');
    console.log('  ✅ 配置管理系统 (Zod 验证)');
    console.log('  ✅ 增强版日志系统');
    console.log('  ✅ Result 类型错误处理');
    console.log('  ✅ Gemini 客户端封装');
    console.log('  ✅ 健康检查机制');

    console.log('\n🚧 开发中的功能:');
    console.log('  ⏳ 音频录制模块');
    console.log('  ⏳ 热键监听');
    console.log('  ⏳ 词典管理');
    console.log('  ⏳ 剪贴板集成');

    console.log('\n💡 提示：');
    console.log('  - 使用 pnpm dev 启动开发模式');
    console.log('  - 使用 pnpm test 运行测试');
    console.log('  - 查看 README.md 了解详细文档');
    console.log();
  } catch (error) {
    logger.error('启动失败:', error);
    console.error('\n❌ 启动失败:', formatError(error));
    process.exit(1);
  }
}

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
  logger.error('未捕获的异常:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  logger.error('未处理的 Promise 拒绝:', reason);
  process.exit(1);
});

main();
