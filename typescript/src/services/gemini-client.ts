/**
 * Gemini AI 客户端封装
 */

import { GoogleGenerativeAI, GenerativeModel, GenerateContentResult } from '@google/generative-ai';
import { createHash } from 'crypto';
import type { GeminiConfig } from '../core/config';
import { createLogger } from '../utils/logger';
import { Result, ok, err, fromPromise } from '../utils/result';
import { GeminiError } from '../utils/errors';

const logger = createLogger('GeminiClient');

/**
 * 转录请求参数
 */
export interface TranscriptionRequest {
  audioData: Buffer;
  mimeType: string;
  prompt?: string;
}

/**
 * 转录结果
 */
export interface TranscriptionResult {
  text: string;
  duration: number;
  timestamp: Date;
}

/**
 * 纠错请求参数
 */
export interface CorrectionRequest {
  text: string;
  prompt?: string;
}

/**
 * Gemini 客户端
 */
export class GeminiClient {
  private ai: GoogleGenerativeAI;
  private model: GenerativeModel;
  private config: GeminiConfig;
  private isReady: boolean = false;

  constructor(config: GeminiConfig) {
    this.config = config;

    if (!config.apiKey) {
      logger.error('Gemini API Key 未配置');
      throw new GeminiError('Gemini API Key 未配置');
    }

    // 初始化 Gemini AI（支持自定义 baseUrl）
    const aiConfig: { apiKey: string; baseUrl?: string } = { apiKey: config.apiKey };
    
    if (config.baseUrl) {
      aiConfig.baseUrl = config.baseUrl;
      logger.info(`使用自定义 Base URL: ${config.baseUrl}`);
    }

    this.ai = new GoogleGenerativeAI(aiConfig.apiKey);
    
    // 注意: Google Generative AI SDK 可能不支持自定义 baseUrl
    // 如果你使用的是自定义 proxy，可能需要设置环境变量或使用其他方法
    if (config.baseUrl) {
      logger.warn('注意: @google/generative-ai SDK 可能不支持自定义 baseUrl');
      logger.warn('建议使用环境变量 HTTPS_PROXY 或其他 HTTP 代理方式');
    }
    
    this.model = this.ai.getGenerativeModel({ model: config.model });

    this.isReady = true;
    logger.info(`Gemini 客户端初始化成功 (${config.model})`);

    if (process.env.DEBUG_MODE === 'true') {
      const digest = this.hashApiKey(config.apiKey);
      logger.debug(`API 密钥指纹: ${digest}`);
    }
  }

  /**
   * 生成 API 密钥的 SHA256 指纹
   */
  private hashApiKey(apiKey: string): string {
    return createHash('sha256').update(apiKey).digest('hex').substring(0, 12);
  }

  /**
   * 健康检查
   */
  async checkHealth(): Promise<Result<boolean, GeminiError>> {
    if (!this.isReady) {
      return err(new GeminiError('Gemini 客户端未初始化'));
    }

    try {
      logger.debug('执行 Gemini 健康检查...');
      const result = await this.model.generateContent({
        contents: [{ role: 'user', parts: [{ text: 'health check ping' }] }],
      });

      const response = result.response;
      if (response && response.text()) {
        logger.debug('Gemini 健康检查成功');
        return ok(true);
      }

      return err(new GeminiError('Gemini 健康检查失败：无响应'));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Gemini 健康检查失败', error);

      // 检查是否为认证错误
      if (message.includes('401') || message.toUpperCase().includes('UNAUTHORIZED')) {
        return err(
          new GeminiError(
            'Gemini API 认证失败，请检查 GEMINI_API_KEY 配置',
            401,
            error
          )
        );
      }

      return err(new GeminiError(`Gemini 健康检查失败: ${message}`, undefined, error));
    }
  }

  /**
   * 转录音频（使用 Gemini）
   */
  async transcribeAudio(
    request: TranscriptionRequest
  ): Promise<Result<TranscriptionResult, GeminiError>> {
    if (!this.isReady) {
      return err(new GeminiError('Gemini 客户端未初始化'));
    }

    const startTime = Date.now();

    try {
      logger.info(
        `开始转录音频 (大小: ${(request.audioData.length / 1024).toFixed(1)}KB)`
      );

      // 准备内容
      const prompt =
        request.prompt ||
        `请转录这段中文或英文音频，并严格按以下优先级输出简体中文文本（可含必要英文单词）：

【必删】
1. 删除所有以"注意"开头的说明（包括"注意,""注意：""注意-"等），自"注意"及后续解释直到该句或分句结束全部移除，不保留解释文字。
2. 若同一句或段落出现多个"注意"，请逐个删除，并整理多余空格或连续标点。

【保留】
3. 其余内容需处理原始语气和口语化表达（如"嗯""哦""啊"等），为保证通顺可以清理一些。
4. 自动补全恰当标点（句号、逗号、问号、感叹号、破折号、省略号等），并修正明显错别字或语法错误，不增删事实信息。

【格式】
5. 输出纯文本，不添加前后缀或额外说明；中文与英文混排时保持单词或缩写之间的空格/连字符。
6. 仅输出简体中文字符，不出现繁体字。
7. 如果是陈述句末尾不要带上句号`;

      const parts = [
        { text: prompt },
        {
          inlineData: {
            data: request.audioData.toString('base64'),
            mimeType: request.mimeType,
          },
        },
      ];

      // 重试逻辑
      let lastError: Error | null = null;
      for (let attempt = 1; attempt <= this.config.maxRetries; attempt++) {
        try {
          logger.debug(`API 调用尝试 ${attempt}/${this.config.maxRetries}`);

          const result = await this.model.generateContent({
            contents: [{ role: 'user', parts }],
          });

          const response = result.response;
          const text = response.text();

          if (text) {
            const duration = Date.now() - startTime;
            logger.info(`✅ 转录成功 (${text.length} 字符, ${duration}ms)`);

            return ok({
              text: text.trim(),
              duration,
              timestamp: new Date(),
            });
          }

          logger.warn(`第 ${attempt} 次尝试：API 返回空响应`);
        } catch (error) {
          lastError = error instanceof Error ? error : new Error(String(error));
          logger.warn(`第 ${attempt} 次尝试失败: ${lastError.message}`);

          if (attempt < this.config.maxRetries) {
            await this.delay(this.config.retryDelay);
          }
        }
      }

      // 所有重试都失败
      const errorMessage = lastError
        ? `所有重试失败: ${lastError.message}`
        : '所有重试失败：未知错误';

      return err(new GeminiError(errorMessage, undefined, lastError));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('转录失败', error);
      return err(new GeminiError(`转录失败: ${message}`, undefined, error));
    }
  }

  /**
   * 纠错文本
   */
  async correctText(request: CorrectionRequest): Promise<Result<string, GeminiError>> {
    if (!this.isReady) {
      return err(new GeminiError('Gemini 客户端未初始化'));
    }

    try {
      logger.debug(`开始纠错文本 (${request.text.length} 字符)`);

      const prompt =
        request.prompt ||
        `请对以下中文语音转录文本进行纠错和基础润色：

原始转录文本：
${request.text}

要求：
1. 【语音识别纠错】纠正同音字、近音字、多音字等识别错误
2. 【标点符号优化】添加必要的句号、逗号、问号、感叹号
3. 【基础语法纠错】修正明显的语法错误和语序问题
4. 【保持原貌】严格保持说话者的语气、态度、用词习惯和表达风格

重要约束：
- 绝对不要改变说话者的语气和态度
- 不要替换俚语、网络用语、口语化表达
- 不要进行风格转换（口语转书面语等）
- 不要添加原文中没有的信息

只输出纠错后的文本，不要添加任何说明：`;

      const result = await this.model.generateContent({
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
      });

      const response = result.response;
      const correctedText = response.text();

      if (correctedText) {
        logger.debug(`✅ 纠错成功 (${correctedText.length} 字符)`);
        return ok(correctedText.trim());
      }

      return err(new GeminiError('纠错失败：API 返回空响应'));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('纠错失败', error);
      return err(new GeminiError(`纠错失败: ${message}`, undefined, error));
    }
  }

  /**
   * 延迟函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * 获取模型信息
   */
  getModelInfo(): {
    model: string;
    isReady: boolean;
  } {
    return {
      model: this.config.model,
      isReady: this.isReady,
    };
  }
}

/**
 * 创建 Gemini 客户端
 */
export function createGeminiClient(config: GeminiConfig): GeminiClient {
  return new GeminiClient(config);
}
