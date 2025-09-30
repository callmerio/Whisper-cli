/**
 * 会话管理器
 * 管理"一口气"模式和"逐步上屏"模式，协调各个组件的工作
 */

import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';
import type { GeminiClient } from '../services/gemini-client';
import type { DictionaryManager } from './dictionary-manager';
import type { ClipboardManager } from './clipboard-manager';
import { SegmentProcessor, type SegmentProcessorConfig } from './segment-processor';
import { createLogger } from '../utils/logger';
import { Result, ok, err, isOk } from '../utils/result';
import { AppError } from '../utils/errors';
import type {
  SessionMode,
  SessionState,
  SessionConfig,
  SessionStats,
  AudioSegment,
  ProcessedSegment,
} from '../types/session';
import { countCharacters, countWords } from '../utils/text-utils';

const logger = createLogger('SessionManager');

/**
 * 会话事件
 */
export interface SessionEvents {
  /** 会话开始 */
  sessionStart: (sessionId: string, mode: SessionMode) => void;
  /** 会话结束 */
  sessionComplete: (stats: SessionStats) => void;
  /** 分段完成 */
  segmentComplete: (segmentId: string, text: string) => void;
  /** 实时输出 */
  realtimeOutput: (text: string) => void;
  /** 错误 */
  error: (error: Error) => void;
  /** 状态变化 */
  stateChange: (oldState: SessionState, newState: SessionState) => void;
}

/**
 * 会话管理器
 */
export class SessionManager extends EventEmitter {
  private geminiClient: GeminiClient;
  private dictionaryManager: DictionaryManager;
  private clipboardManager: ClipboardManager;
  private segmentProcessor: SegmentProcessor;

  // 会话状态
  private currentSessionId: string | null = null;
  private currentState: SessionState = 'idle';
  private currentMode: SessionMode = 'batch';
  private sessionConfig: SessionConfig;
  private sessionStartTime: number = 0;
  private sessionEndTime: number = 0;

  // 会话数据
  private sessionSegments: ProcessedSegment[] = [];
  private sessionAudioBuffer: Buffer[] = [];

  constructor(
    geminiClient: GeminiClient,
    dictionaryManager: DictionaryManager,
    clipboardManager: ClipboardManager,
    config?: Partial<SessionConfig>
  ) {
    super();

    this.geminiClient = geminiClient;
    this.dictionaryManager = dictionaryManager;
    this.clipboardManager = clipboardManager;

    // 默认配置
    this.sessionConfig = {
      mode: 'batch',
      silenceDuration: 4.0,
      minSegmentDuration: 1.0,
      volumeThreshold: 0.01,
      autoOutputEnabled: true,
      clipboardBackup: true,
      enableCorrection: true,
      enableDictionary: true,
      ...config,
    };

    // 初始化分段处理器
    this.segmentProcessor = new SegmentProcessor(
      this.geminiClient,
      this.dictionaryManager,
      this.clipboardManager,
      {
        enableCorrection: this.sessionConfig.enableCorrection,
        enableDictionary: this.sessionConfig.enableDictionary,
        enableAutoOutput: this.sessionConfig.autoOutputEnabled,
      }
    );

    logger.info('会话管理器初始化完成');
  }

  /**
   * 开始新会话
   */
  async startSession(mode: SessionMode = 'batch'): Promise<Result<string, AppError>> {
    if (this.currentState !== 'idle') {
      return err(new AppError('会话已在进行中', 'SESSION_ERROR'));
    }

    const sessionId = uuidv4();
    this.currentSessionId = sessionId;
    this.currentMode = mode;
    this.sessionStartTime = Date.now();
    this.sessionSegments = [];
    this.sessionAudioBuffer = [];

    this.setState('recording');
    this.segmentProcessor.startSession(sessionId);

    logger.info(`✅ 会话开始: ${sessionId} (${mode})`);
    this.emit('sessionStart', sessionId, mode);

    return ok(sessionId);
  }

  /**
   * 添加音频数据
   */
  async addAudioSegment(audioSegment: AudioSegment): Promise<Result<void, AppError>> {
    if (this.currentState !== 'recording') {
      return err(new AppError('当前不在录音状态', 'SESSION_ERROR'));
    }

    logger.debug(`添加音频分段: ${audioSegment.duration.toFixed(2)}s`);

    // 根据模式处理
    if (this.currentMode === 'realtime') {
      // 实时模式：立即处理
      const result = await this.segmentProcessor.processSegment(
        audioSegment,
        this.sessionConfig
      );

      if (isOk(result)) {
        this.sessionSegments.push(result.data.segment);
        this.emit('segmentComplete', result.data.segmentId, result.data.finalText);
        this.emit('realtimeOutput', result.data.finalText);
      } else {
        logger.error('分段处理失败:', result.error);
        this.emit('error', result.error);
      }
    } else {
      // 批量模式：缓存音频
      this.sessionAudioBuffer.push(audioSegment.audioData);
    }

    return ok(undefined);
  }

  /**
   * 结束会话
   */
  async endSession(): Promise<Result<SessionStats, AppError>> {
    if (this.currentState === 'idle') {
      return err(new AppError('没有活动的会话', 'SESSION_ERROR'));
    }

    logger.info('结束会话');
    this.setState('processing');

    try {
      // 批量模式：处理整个音频
      if (this.currentMode === 'batch' && this.sessionAudioBuffer.length > 0) {
        // 合并音频
        const fullAudio = Buffer.concat(this.sessionAudioBuffer);

        // 创建完整的音频分段
        const audioSegment: AudioSegment = {
          id: uuidv4(),
          audioData: fullAudio,
          startTime: 0,
          endTime: 0,
          duration: 0,
          isFinal: true,
          sampleRate: 16000,
          channels: 1,
        };

        // 处理
        const result = await this.segmentProcessor.processSegment(
          audioSegment,
          this.sessionConfig
        );

        if (isOk(result)) {
          this.sessionSegments.push(result.data.segment);
          logger.info(`✅ 批量处理完成: "${result.data.finalText.substring(0, 50)}..."`);
        } else {
          logger.error('批量处理失败:', result.error);
          throw result.error;
        }
      }

      // 等待所有处理完成
      await this.segmentProcessor.waitForCompletion();

      // 生成统计
      this.sessionEndTime = Date.now();
      const stats = this.generateStats();

      this.setState('completed');
      this.emit('sessionComplete', stats);

      // 重置状态
      setTimeout(() => {
        this.reset();
      }, 100);

      return ok(stats);
    } catch (error) {
      this.setState('error');
      const appError = error instanceof AppError ? error : new AppError('会话处理失败', 'SESSION_ERROR', error);
      this.emit('error', appError);
      return err(appError);
    }
  }

  /**
   * 取消会话
   */
  cancelSession(): void {
    logger.info('取消会话');
    this.reset();
  }

  /**
   * 生成会话统计
   */
  private generateStats(): SessionStats {
    const processorStats = this.segmentProcessor.getSessionStats();
    const totalDuration = (this.sessionEndTime - this.sessionStartTime) / 1000;

    // 计算处理时长（从所有分段的处理时间总和）
    const processingDuration =
      this.sessionSegments.reduce((sum, seg) => {
        return sum + (seg.processingTimes.total || 0);
      }, 0) / 1000;

    return {
      sessionId: this.currentSessionId!,
      mode: this.currentMode,
      recordingDuration: totalDuration - processingDuration,
      processingDuration,
      totalDuration,
      segmentCount: processorStats.total,
      successCount: processorStats.completed,
      failureCount: processorStats.failed,
      finalText: processorStats.totalText,
      characterCount: processorStats.totalChars,
      wordCount: processorStats.totalWords,
    };
  }

  /**
   * 设置状态
   */
  private setState(newState: SessionState): void {
    if (this.currentState !== newState) {
      const oldState = this.currentState;
      this.currentState = newState;
      logger.debug(`状态变化: ${oldState} → ${newState}`);
      this.emit('stateChange', oldState, newState);
    }
  }

  /**
   * 重置会话
   */
  private reset(): void {
    this.currentSessionId = null;
    this.currentState = 'idle';
    this.sessionSegments = [];
    this.sessionAudioBuffer = [];
    this.sessionStartTime = 0;
    this.sessionEndTime = 0;
    this.segmentProcessor.clearCompleted();
    logger.debug('会话已重置');
  }

  /**
   * 获取当前状态
   */
  getState(): SessionState {
    return this.currentState;
  }

  /**
   * 获取当前会话ID
   */
  getCurrentSessionId(): string | null {
    return this.currentSessionId;
  }

  /**
   * 获取当前模式
   */
  getCurrentMode(): SessionMode {
    return this.currentMode;
  }

  /**
   * 更新配置
   */
  updateConfig(config: Partial<SessionConfig>): void {
    this.sessionConfig = {
      ...this.sessionConfig,
      ...config,
    };
    logger.info('会话配置已更新');
  }
}

/**
 * 创建会话管理器
 */
export function createSessionManager(
  geminiClient: GeminiClient,
  dictionaryManager: DictionaryManager,
  clipboardManager: ClipboardManager,
  config?: Partial<SessionConfig>
): SessionManager {
  return new SessionManager(geminiClient, dictionaryManager, clipboardManager, config);
}

