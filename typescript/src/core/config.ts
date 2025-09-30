/**
 * 配置管理系统 - 使用 Zod 进行验证
 */

import { z } from 'zod';
import * as dotenv from 'dotenv';
import { createLogger } from '../utils/logger';

const logger = createLogger('Config');

// 加载环境变量
dotenv.config();

/**
 * Gemini 配置 Schema
 */
const GeminiConfigSchema = z.object({
  apiKey: z.string().min(10, 'Gemini API Key 必须至少 10 个字符'),
  model: z
    .string()
    .default('gemini-2.5-flash')
    .refine(
      (model) =>
        ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'].includes(model),
      '不支持的 Gemini 模型'
    ),
  baseUrl: z.string().url().optional(),
  requestTimeout: z.number().min(1000).max(120000).default(30000),
  maxRetries: z.number().min(0).max(10).default(2),
  retryDelay: z.number().min(100).max(10000).default(1000),
});

/**
 * 热键配置 Schema
 */
const HotkeyConfigSchema = z.object({
  key: z
    .enum(['left_option', 'right_option', 'option', 'command', 'left_command', 'right_command'])
    .default('left_option'),
  threshold: z.number().min(0.01).max(2.0).default(0.03),
});

/**
 * 音频配置 Schema
 */
const AudioConfigSchema = z.object({
  sampleRate: z.number().positive().default(16000),
  channels: z.number().min(1).max(2).default(1),
  chunkDuration: z.number().positive().default(1.0),
  bufferDuration: z.number().positive().default(30.0),
  minTranscriptionDuration: z.number().min(0).default(1.0),
});

/**
 * 词典配置 Schema
 */
const DictionaryConfigSchema = z.object({
  enabled: z.boolean().default(true),
  filePath: z.string().default('./dic.txt'),
  weightThreshold: z.number().min(0).max(1).default(0.6),
  maxWeight: z.number().min(0).max(1).default(0.5),
});

/**
 * 纠错记忆配置 Schema
 */
const CorrectionMemoryConfigSchema = z.object({
  enabled: z.boolean().default(true),
  hotkey: z.string().default('<cmd>+<shift>+m'),
  minCharsIgnore: z.number().min(0).default(3),
  autoAcceptThreshold: z.number().min(0).default(7),
  maxLengthGrowthRatio: z.number().min(1.0).default(1.6),
  maxDiffRatio: z.number().min(0).max(1).default(0.5),
});

/**
 * 应用配置 Schema
 */
const AppConfigSchema = z.object({
  debugMode: z.boolean().default(true),
  enableClipboard: z.boolean().default(true),
  enableNotifications: z.boolean().default(true),
  autoPasteEnabled: z.boolean().default(true),
});

/**
 * 完整配置 Schema
 */
const ConfigSchema = z.object({
  gemini: GeminiConfigSchema,
  hotkey: HotkeyConfigSchema,
  audio: AudioConfigSchema,
  dictionary: DictionaryConfigSchema,
  correctionMemory: CorrectionMemoryConfigSchema,
  app: AppConfigSchema,
});

/**
 * 配置类型
 */
export type Config = z.infer<typeof ConfigSchema>;
export type GeminiConfig = z.infer<typeof GeminiConfigSchema>;
export type HotkeyConfig = z.infer<typeof HotkeyConfigSchema>;
export type AudioConfig = z.infer<typeof AudioConfigSchema>;
export type DictionaryConfig = z.infer<typeof DictionaryConfigSchema>;
export type CorrectionMemoryConfig = z.infer<typeof CorrectionMemoryConfigSchema>;
export type AppConfig = z.infer<typeof AppConfigSchema>;

/**
 * 从环境变量加载配置
 */
function loadConfigFromEnv(): Config {
  const rawConfig = {
    gemini: {
      apiKey: process.env.GEMINI_API_KEY || '',
      model: process.env.GEMINI_MODEL || 'gemini-2.5-flash',
      baseUrl: process.env.GEMINI_BASE_URL,
      requestTimeout: Number(process.env.GEMINI_REQUEST_TIMEOUT) || 30000,
      maxRetries: Number(process.env.GEMINI_MAX_RETRIES) || 2,
      retryDelay: Number(process.env.GEMINI_RETRY_DELAY) || 1000,
    },
    hotkey: {
      key: (process.env.HOTKEY_KEY as any) || 'left_option',
      threshold: Number(process.env.HOTKEY_THRESHOLD) || 0.03,
    },
    audio: {
      sampleRate: Number(process.env.AUDIO_SAMPLE_RATE) || 16000,
      channels: Number(process.env.AUDIO_CHANNELS) || 1,
      chunkDuration: Number(process.env.AUDIO_CHUNK_DURATION) || 1.0,
      bufferDuration: Number(process.env.AUDIO_BUFFER_DURATION) || 30.0,
      minTranscriptionDuration: Number(process.env.MIN_TRANSCRIPTION_DURATION) || 1.0,
    },
    dictionary: {
      enabled: process.env.DICTIONARY_ENABLED !== 'false',
      filePath: process.env.DICTIONARY_FILE || './dic.txt',
      weightThreshold: Number(process.env.DICTIONARY_WEIGHT_THRESHOLD) || 0.6,
      maxWeight: Number(process.env.DICTIONARY_MAX_WEIGHT) || 0.5,
    },
    correctionMemory: {
      enabled: process.env.CORRECTION_MEMORY_ENABLED !== 'false',
      hotkey: process.env.CORRECTION_MEMORY_HOTKEY || '<cmd>+<shift>+m',
      minCharsIgnore: Number(process.env.CORRECTION_MIN_CHARS_IGNORE) || 3,
      autoAcceptThreshold: Number(process.env.CORRECTION_AUTO_ACCEPT_THRESHOLD) || 7,
      maxLengthGrowthRatio: Number(process.env.CORRECTION_MAX_LENGTH_GROWTH_RATIO) || 1.6,
      maxDiffRatio: Number(process.env.CORRECTION_MAX_DIFF_RATIO) || 0.5,
    },
    app: {
      debugMode: process.env.DEBUG_MODE === 'true',
      enableClipboard: process.env.ENABLE_CLIPBOARD !== 'false',
      enableNotifications: process.env.ENABLE_NOTIFICATIONS !== 'false',
      autoPasteEnabled: process.env.AUTO_PASTE_ENABLED !== 'false',
    },
  };

  return rawConfig;
}

/**
 * 验证并返回配置
 */
export function getConfig(): Config {
  try {
    const rawConfig = loadConfigFromEnv();
    const validatedConfig = ConfigSchema.parse(rawConfig);

    if (validatedConfig.app.debugMode) {
      logger.debug('配置验证成功');
      logger.debug(`Gemini 模型: ${validatedConfig.gemini.model}`);
      logger.debug(`热键: ${validatedConfig.hotkey.key}`);
    }

    return validatedConfig;
  } catch (error) {
    if (error instanceof z.ZodError) {
      logger.error('配置验证失败:');
      error.errors.forEach((err) => {
        logger.error(`  - ${err.path.join('.')}: ${err.message}`);
      });
      throw new Error('配置验证失败，请检查环境变量');
    }
    throw error;
  }
}

/**
 * 验证配置（用于启动时检查）
 */
export function validateConfig(config: Config): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  // 关键配置检查
  if (!config.gemini.apiKey) {
    errors.push('GEMINI_API_KEY 未配置');
  }

  if (config.gemini.apiKey.length < 10) {
    errors.push('GEMINI_API_KEY 长度异常');
  }

  if (config.hotkey.threshold < 0.01) {
    errors.push('热键阈值过小，可能导致误触发');
  }

  if (config.audio.minTranscriptionDuration < 0) {
    errors.push('最小转录时长不能为负数');
  }

  if (config.correctionMemory.maxDiffRatio < 0 || config.correctionMemory.maxDiffRatio > 1) {
    errors.push('纠错最大差异比例必须在 [0, 1] 范围内');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * 打印配置摘要
 */
export function printConfigSummary(config: Config): void {
  console.log('📋 当前配置摘要:');
  console.log(`  • Gemini 模型: ${config.gemini.model}`);
  console.log(`  • 热键: ${config.hotkey.key} (阈值 ${config.hotkey.threshold}s)`);
  console.log(`  • 音频采样率: ${config.audio.sampleRate}Hz`);
  console.log(`  • 词典: ${config.dictionary.enabled ? '启用' : '禁用'}`);
  console.log(`  • 纠错记忆: ${config.correctionMemory.enabled ? '启用' : '禁用'}`);
  console.log(`  • 调试模式: ${config.app.debugMode ? '开启' : '关闭'}`);
  console.log();
}
