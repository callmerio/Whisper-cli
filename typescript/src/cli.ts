#!/usr/bin/env node
/**
 * Whisper CLI - 命令行工具
 * 用于测试和调试各种功能
 */

import { getConfig } from './core/config';
import { createLogger } from './utils/logger';
import { createGeminiClient } from './services/gemini-client';
import { createDictionaryManager } from './managers/dictionary-manager';
import { createClipboardManager } from './managers/clipboard-manager';
import { isOk } from './utils/result';

const logger = createLogger('CLI');

interface CLICommand {
  name: string;
  description: string;
  execute: () => Promise<void>;
}

/**
 * 测试 Gemini 转录（使用示例音频）
 */
async function testTranscribe(): Promise<void> {
  console.log('\n🎯 测试 Gemini 转录功能\n');
  
  const config = getConfig();
  const gemini = createGeminiClient(config.gemini);
  
  // 这里需要实际的音频文件
  console.log('⚠️  此功能需要音频录制模块支持');
  console.log('📋 当前状态: 音频录制模块开发中');
}

/**
 * 测试词典替换
 */
async function testDictionary(): Promise<void> {
  console.log('\n📚 测试词典替换功能\n');
  
  const config = getConfig();
  const dictionary = createDictionaryManager(config.dictionary);
  
  const loadResult = await dictionary.load();
  if (!isOk(loadResult)) {
    console.error('❌ 词典加载失败');
    return;
  }
  
  console.log(`✅ 加载了 ${loadResult.data} 个词典条目\n`);
  
  const testCases = [
    'TypeScript 是一个很好的编程语言',
    '我正在使用 Gemini API 开发应用',
    '谷歌和微软都是科技公司',
    'React 和 Vue 是流行的前端框架',
  ];
  
  testCases.forEach((text, i) => {
    const result = dictionary.applyDictionary(text);
    console.log(`测试 ${i + 1}:`);
    console.log(`  原文: ${text}`);
    console.log(`  结果: ${result.text}`);
    if (result.replacements.length > 0) {
      console.log(`  替换: ${result.replacements.map(r => `"${r.original}" → "${r.target}"`).join(', ')}`);
    }
    console.log();
  });
}

/**
 * 测试剪贴板
 */
async function testClipboard(): Promise<void> {
  console.log('\n📋 测试剪贴板功能\n');
  
  const clipboard = createClipboardManager();
  
  // 1. 读取当前内容
  console.log('1️⃣ 读取当前剪贴板内容:');
  const readResult = await clipboard.read();
  if (isOk(readResult)) {
    const preview = readResult.data.length > 50 
      ? readResult.data.substring(0, 50) + '...' 
      : readResult.data;
    console.log(`   内容: "${preview}"`);
    console.log(`   长度: ${readResult.data.length} 字符\n`);
  }
  
  // 2. 写入测试文本
  console.log('2️⃣ 写入测试文本:');
  const testText = 'Whisper CLI TypeScript - 智能语音转录系统';
  const writeResult = await clipboard.write(testText);
  if (isOk(writeResult)) {
    console.log(`   ✅ 写入成功: "${testText}"\n`);
  }
  
  // 3. 验证写入
  console.log('3️⃣ 验证写入:');
  const verifyResult = await clipboard.read();
  if (isOk(verifyResult) && verifyResult.data === testText) {
    console.log('   ✅ 验证成功\n');
  }
  
  // 4. 获取统计信息
  console.log('4️⃣ 统计信息:');
  const statsResult = await clipboard.getStats();
  if (isOk(statsResult)) {
    const stats = statsResult.data;
    console.log(`   字符数: ${stats.characters}`);
    console.log(`   词数: ${stats.words}`);
    console.log(`   行数: ${stats.lines}\n`);
  }
  
  // 5. 恢复备份
  console.log('5️⃣ 恢复备份:');
  if (clipboard.hasBackup()) {
    const restoreResult = await clipboard.restore();
    if (isOk(restoreResult)) {
      console.log('   ✅ 备份已恢复\n');
    }
  }
}

/**
 * 测试纠错功能
 */
async function testCorrection(): Promise<void> {
  console.log('\n✏️ 测试 Gemini 纠错功能\n');
  
  const config = getConfig();
  const gemini = createGeminiClient(config.gemini);
  
  const testTexts = [
    '这是一段测试文本，可能有一些小的错误',
    'TypeScript is a programming language that builds on JavaScript',
  ];
  
  for (let i = 0; i < testTexts.length; i++) {
    const text = testTexts[i];
    console.log(`测试 ${i + 1}:`);
    console.log(`  原文: ${text}`);
    
    const result = await gemini.correctText({
      text,
      context: '技术文档',
    });
    
    if (isOk(result)) {
      console.log(`  纠正: ${result.data.correctedText}`);
      if (result.data.hasChanges) {
        console.log(`  ✅ 检测到变化`);
      } else {
        console.log(`  ℹ️ 无需修改`);
      }
    } else {
      console.log(`  ❌ 纠错失败: ${result.error.message}`);
    }
    console.log();
  }
}

/**
 * 显示配置信息
 */
async function showConfig(): Promise<void> {
  console.log('\n⚙️ 当前配置\n');
  
  const config = getConfig();
  
  console.log('Gemini:');
  console.log(`  模型: ${config.gemini.model}`);
  console.log(`  超时: ${config.gemini.requestTimeout}ms`);
  console.log(`  最大重试: ${config.gemini.maxRetries}\n`);
  
  console.log('热键:');
  console.log(`  按键: ${config.hotkey.key}`);
  console.log(`  阈值: ${config.hotkey.threshold}s\n`);
  
  console.log('音频:');
  console.log(`  采样率: ${config.audio.sampleRate}Hz`);
  console.log(`  声道: ${config.audio.channels}\n`);
  
  console.log('词典:');
  console.log(`  启用: ${config.dictionary.enabled}`);
  console.log(`  文件: ${config.dictionary.filePath}\n`);
  
  console.log('应用:');
  console.log(`  剪贴板: ${config.app.enableClipboard}`);
  console.log(`  自动粘贴: ${config.app.enableAutoPaste}`);
  console.log(`  调试模式: ${config.app.debugMode}\n`);
}

/**
 * 命令列表
 */
const commands: CLICommand[] = [
  {
    name: 'transcribe',
    description: '测试 Gemini 转录功能',
    execute: testTranscribe,
  },
  {
    name: 'dictionary',
    description: '测试词典替换功能',
    execute: testDictionary,
  },
  {
    name: 'clipboard',
    description: '测试剪贴板功能',
    execute: testClipboard,
  },
  {
    name: 'correction',
    description: '测试 Gemini 纠错功能',
    execute: testCorrection,
  },
  {
    name: 'config',
    description: '显示当前配置',
    execute: showConfig,
  },
];

/**
 * 显示帮助
 */
function showHelp(): void {
  console.log('\n🎙️ Whisper CLI - 命令行工具\n');
  console.log('用法: pnpm cli [command]\n');
  console.log('可用命令:\n');
  
  commands.forEach((cmd) => {
    console.log(`  ${cmd.name.padEnd(15)} ${cmd.description}`);
  });
  
  console.log('\n示例:');
  console.log('  pnpm cli dictionary    # 测试词典功能');
  console.log('  pnpm cli clipboard     # 测试剪贴板功能');
  console.log('  pnpm cli config        # 显示配置\n');
}

/**
 * 主函数
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const commandName = args[0];
  
  if (!commandName || commandName === 'help' || commandName === '--help' || commandName === '-h') {
    showHelp();
    return;
  }
  
  const command = commands.find((cmd) => cmd.name === commandName);
  
  if (!command) {
    console.error(`❌ 未知命令: ${commandName}\n`);
    showHelp();
    process.exit(1);
  }
  
  try {
    await command.execute();
  } catch (error) {
    console.error('\n❌ 执行失败:', error);
    process.exit(1);
  }
}

// 运行
main().catch((error) => {
  console.error('❌ 程序错误:', error);
  process.exit(1);
});
