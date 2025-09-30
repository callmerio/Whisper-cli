/**
 * 分段处理器
 * 负责协调语音分段的检测、转录、后处理和输出
 */

import { v4 as uuidv4 } from 'uuid';
import type { GeminiClient } from '../services/gemini-client';
import type { DictionaryManager } from './dictionary-manager';
import type { ClipboardManager } from './clipboard-manager';
import { createLogger } from '../utils/logger';
import { Result, ok, err, isOk } from '../utils/result';
import { AppError } from '../utils/errors';
import type {
  AudioSegment,
  ProcessedSegment,
  SegmentStatus,
  SessionConfig,
} from '../types/session';
import { countCharacters, countWords } from '../utils/text-utils';

const logger = createLogger('SegmentProcessor');

/**
 * 分段处理器配置
 */
export interface SegmentProcessorConfig {
  /** 最大并发处理数 */
  maxConcurrent: number;
  /** 启用纠错 */
  enableCorrection: boolean;
  /** 启用词典 */
  enableDictionary: boolean;
  /** 自动输出 */
  enableAutoOutput: boolean;
}

/**
 * 分段处理结果
 */
export interface ProcessingResult {
  /** 分段ID */
  segmentId: string;
  /** 最终文本 */
  finalText: string;
  /** 处理后的分段 */
  segment: ProcessedSegment;
}

/**
 * 分段处理器
 */
export class SegmentProcessor {
  private config: SegmentProcessorConfig;
  private geminiClient: GeminiClient;
  private dictionaryManager: DictionaryManager;
  private clipboardManager: ClipboardManager;
  private activeSegments: Map<string, ProcessedSegment> = new Map();
  private completedSegments: ProcessedSegment[] = [];
  private sessionSegments: string[] = [];

  constructor(
    geminiClient: GeminiClient,
    dictionaryManager: DictionaryManager,
    clipboardManager: ClipboardManager,
    config: Partial<SegmentProcessorConfig> = {}
  ) {
    this.geminiClient = geminiClient;
    this.dictionaryManager = dictionaryManager;
    this.clipboardManager = clipboardManager;

    this.config = {
      maxConcurrent: config.maxConcurrent ?? 3,
      enableCorrection: config.enableCorrection ?? true,
      enableDictionary: config.enableDictionary ?? true,
      enableAutoOutput: config.enableAutoOutput ?? true,
    };

    logger.info('分段处理器初始化完成');
  }

  /**
   * 开始新会话
   */
  startSession(sessionId: string): void {
    logger.info(`开始新会话: ${sessionId}`);
    this.sessionSegments = [];
    this.activeSegments.clear();
  }

  /**
   * 处理音频分段
   */
  async processSegment(
    audioSegment: AudioSegment,
    sessionConfig: SessionConfig
  ): Promise<Result<ProcessingResult, AppError>> {
    const segmentId = audioSegment.id || uuidv4();
    const startTime = Date.now();

    logger.info(`开始处理分段: ${segmentId}`);

    // 创建处理分段对象
    const processedSegment: ProcessedSegment = {
      segmentId,
      originalAudio: audioSegment,
      status: 'pending',
      processingTimes: {},
      metadata: {},
      createdTime: startTime,
    };

    this.activeSegments.set(segmentId, processedSegment);
    this.sessionSegments.push(segmentId);

    try {
      // 1. 转录
      processedSegment.status = 'transcribing';
      const transcriptionResult = await this.transcribe(audioSegment);

      if (!isOk(transcriptionResult)) {
        throw transcriptionResult.error;
      }

      processedSegment.rawTranscript = transcriptionResult.data.text;
      processedSegment.processingTimes.transcription = transcriptionResult.data.duration;
      logger.debug(`转录完成: "${processedSegment.rawTranscript.substring(0, 50)}..."`);

      // 2. 词典处理
      processedSegment.status = 'processing';
      let currentText = processedSegment.rawTranscript;

      if (this.config.enableDictionary && sessionConfig.enableDictionary) {
        const dictStart = Date.now();
        const dictResult = this.dictionaryManager.applyDictionary(currentText);
        processedSegment.processedTranscript = dictResult.text;
        processedSegment.processingTimes.dictionary = Date.now() - dictStart;
        currentText = dictResult.text;

        if (dictResult.replacements.length > 0) {
          logger.debug(`词典替换: ${dictResult.replacements.length} 处`);
        }
      } else {
        processedSegment.processedTranscript = currentText;
      }

      // 3. 纠错（可选）
      if (this.config.enableCorrection && sessionConfig.enableCorrection) {
        const correctionStart = Date.now();
        const correctionResult = await this.geminiClient.correctText({
          text: currentText,
          context: '语音转录',
        });

        if (isOk(correctionResult)) {
          processedSegment.correctedTranscript = correctionResult.data.correctedText;
          processedSegment.processingTimes.correction = Date.now() - correctionStart;
          currentText = correctionResult.data.correctedText;

          if (correctionResult.data.hasChanges) {
            logger.debug('纠错完成，检测到变化');
          }
        } else {
          logger.warn('纠错失败，使用原文本:', correctionResult.error.message);
          processedSegment.correctedTranscript = currentText;
        }
      } else {
        processedSegment.correctedTranscript = currentText;
      }

      // 4. 设置最终文本
      processedSegment.finalText = currentText;
      processedSegment.status = 'completed';
      processedSegment.completedTime = Date.now();
      processedSegment.processingTimes.total = processedSegment.completedTime - startTime;

      // 5. 输出到剪贴板（如果启用）
      if (this.config.enableAutoOutput && sessionConfig.autoOutputEnabled) {
        processedSegment.status = 'outputting';
        const outputStart = Date.now();

        const outputResult = await this.clipboardManager.write(
          currentText,
          sessionConfig.clipboardBackup
        );

        if (isOk(outputResult)) {
          logger.info('✅ 已输出到剪贴板');
          processedSegment.processingTimes.output = Date.now() - outputStart;
        } else {
          logger.warn('剪贴板输出失败:', outputResult.error.message);
        }
      }

      // 移动到完成列表
      this.activeSegments.delete(segmentId);
      this.completedSegments.push(processedSegment);

      logger.info(`✅ 分段处理完成: ${segmentId} (${processedSegment.processingTimes.total}ms)`);

      return ok({
        segmentId,
        finalText: currentText,
        segment: processedSegment,
      });
    } catch (error) {
      processedSegment.status = 'failed';
      processedSegment.errorMessage = error instanceof Error ? error.message : String(error);
      processedSegment.completedTime = Date.now();

      this.activeSegments.delete(segmentId);
      this.completedSegments.push(processedSegment);

      logger.error(`❌ 分段处理失败: ${segmentId}`, error);

      return err(
        new AppError(`分段处理失败: ${processedSegment.errorMessage}`, 'SEGMENT_ERROR', error)
      );
    }
  }

  /**
   * 转录音频
   */
  private async transcribe(
    audioSegment: AudioSegment
  ): Promise<Result<{ text: string; duration: number }, AppError>> {
    const startTime = Date.now();

    const result = await this.geminiClient.transcribeAudio({
      audioData: audioSegment.audioData,
      mimeType: 'audio/wav',
    });

    const duration = Date.now() - startTime;

    if (isOk(result)) {
      return ok({
        text: result.data.text,
        duration,
      });
    }

    return err(new AppError('转录失败', 'TRANSCRIPTION_ERROR', result.error));
  }

  /**
   * 等待所有分段处理完成
   */
  async waitForCompletion(): Promise<void> {
    // 简单实现：等待活动分段清空
    while (this.activeSegments.size > 0) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  /**
   * 结束会话
   */
  endSession(): ProcessedSegment[] {
    logger.info('结束会话');
    const segments = this.completedSegments.filter((seg) =>
      this.sessionSegments.includes(seg.segmentId)
    );

    this.sessionSegments = [];
    return segments;
  }

  /**
   * 获取会话统计
   */
  getSessionStats(): {
    total: number;
    completed: number;
    failed: number;
    active: number;
    totalText: string;
    totalChars: number;
    totalWords: number;
  } {
    const sessionSegs = this.completedSegments.filter((seg) =>
      this.sessionSegments.includes(seg.segmentId)
    );

    const completed = sessionSegs.filter((s) => s.status === 'completed').length;
    const failed = sessionSegs.filter((s) => s.status === 'failed').length;
    const totalText = sessionSegs
      .filter((s) => s.finalText)
      .map((s) => s.finalText!)
      .join('');

    return {
      total: sessionSegs.length,
      completed,
      failed,
      active: this.activeSegments.size,
      totalText,
      totalChars: countCharacters(totalText),
      totalWords: countWords(totalText),
    };
  }

  /**
   * 清理已完成的分段
   */
  clearCompleted(): void {
    this.completedSegments = [];
    logger.debug('已清理完成的分段');
  }
}

/**
 * 创建分段处理器
 */
export function createSegmentProcessor(
  geminiClient: GeminiClient,
  dictionaryManager: DictionaryManager,
  clipboardManager: ClipboardManager,
  config?: Partial<SegmentProcessorConfig>
): SegmentProcessor {
  return new SegmentProcessor(geminiClient, dictionaryManager, clipboardManager, config);
}

