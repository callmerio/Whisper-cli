/**
 * Whisper CLI - TypeScript 版本
 * 基于 Gemini-2.5-Flash 的智能语音转录系统
 */

import { version } from '../package.json';

console.log(`🎙️ Whisper CLI TypeScript v${version}`);
console.log('🚀 正在启动智能语音转录系统...\n');

async function main(): Promise<void> {
  try {
    console.log('✅ 系统初始化成功！');
    console.log('📝 开发进行中...');
    console.log('\n提示：使用 pnpm dev 启动开发模式');
  } catch (error) {
    console.error('❌ 启动失败:', error);
    process.exit(1);
  }
}

main();
