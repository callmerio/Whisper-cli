/**
 * 音频录制器
 * 负责音频采集和管理
 */

import { EventEmitter } from 'events';
import { createLogger } from '../utils/logger';
import { Result, ok, err } from '../utils/result';
import { AudioError } from '../utils/errors';
import type {
  AudioConfig,
  RecordingState,
  AudioChunk,
  RecordingStats,
  AudioDeviceInfo,
} from '../types/audio';

const logger = createLogger('AudioRecorder');

/**
 * 音频录制器事件
 */
export interface AudioRecorderEvents {
  /** 录音开始 */
  start: () => void;
  /** 录音停止 */
  stop: (stats: RecordingStats) => void;
  /** 音频数据块 */
  data: (chunk: AudioChunk) => void;
  /** 错误 */
  error: (error: Error) => void;
  /** 状态变化 */
  stateChange: (oldState: RecordingState, newState: RecordingState) => void;
}

/**
 * 音频录制器接口
 */
export interface IAudioRecorder {
  /** 开始录音 */
  start(): Promise<Result<void, AudioError>>;
  /** 停止录音 */
  stop(): Promise<Result<RecordingStats, AudioError>>;
  /** 暂停录音 */
  pause(): Promise<Result<void, AudioError>>;
  /** 恢复录音 */
  resume(): Promise<Result<void, AudioError>>;
  /** 获取当前状态 */
  getState(): RecordingState;
  /** 获取录音统计 */
  getStats(): RecordingStats;
  /** 获取可用设备列表 */
  getDevices(): Promise<Result<AudioDeviceInfo[], AudioError>>;
}

/**
 * 模拟音频录制器
 * 用于测试和开发，生成模拟音频数据
 */
export class MockAudioRecorder extends EventEmitter implements IAudioRecorder {
  private config: AudioConfig;
  private state: RecordingState = 'idle';
  private startTime: number = 0;
  private chunkSequence: number = 0;
  private interval: NodeJS.Timeout | null = null;
  private totalBytes: number = 0;
  private totalFrames: number = 0;

  constructor(config: Partial<AudioConfig> = {}) {
    super();

    this.config = {
      sampleRate: config.sampleRate ?? 16000,
      channels: config.channels ?? 1,
      bitDepth: config.bitDepth ?? 16,
      format: config.format ?? 'pcm',
      deviceId: config.deviceId,
    };

    logger.info('模拟音频录制器已创建');
  }

  /**
   * 开始录音
   */
  async start(): Promise<Result<void, AudioError>> {
    if (this.state === 'recording') {
      return err(new AudioError('录音已在进行中'));
    }

    this.setState('recording');
    this.startTime = Date.now();
    this.chunkSequence = 0;
    this.totalBytes = 0;
    this.totalFrames = 0;

    logger.info('📝 开始模拟录音');
    this.emit('start');

    // 模拟每秒生成一个音频块
    this.interval = setInterval(() => {
      this.generateMockChunk();
    }, 1000);

    return ok(undefined);
  }

  /**
   * 停止录音
   */
  async stop(): Promise<Result<RecordingStats, AudioError>> {
    if (this.state !== 'recording' && this.state !== 'paused') {
      return err(new AudioError('当前不在录音状态'));
    }

    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }

    this.setState('stopped');

    const stats = this.getStats();
    logger.info(`✅ 停止录音: ${stats.duration.toFixed(2)}s`);
    this.emit('stop', stats);

    // 重置为空闲
    setTimeout(() => {
      this.setState('idle');
    }, 100);

    return ok(stats);
  }

  /**
   * 暂停录音
   */
  async pause(): Promise<Result<void, AudioError>> {
    if (this.state !== 'recording') {
      return err(new AudioError('当前不在录音状态'));
    }

    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }

    this.setState('paused');
    logger.info('⏸️  暂停录音');

    return ok(undefined);
  }

  /**
   * 恢复录音
   */
  async resume(): Promise<Result<void, AudioError>> {
    if (this.state !== 'paused') {
      return err(new AudioError('当前不在暂停状态'));
    }

    this.setState('recording');
    logger.info('▶️  恢复录音');

    this.interval = setInterval(() => {
      this.generateMockChunk();
    }, 1000);

    return ok(undefined);
  }

  /**
   * 获取当前状态
   */
  getState(): RecordingState {
    return this.state;
  }

  /**
   * 获取录音统计
   */
  getStats(): RecordingStats {
    const duration = this.startTime ? (Date.now() - this.startTime) / 1000 : 0;

    return {
      duration,
      totalFrames: this.totalFrames,
      totalBytes: this.totalBytes,
      chunkCount: this.chunkSequence,
      sampleRate: this.config.sampleRate,
      channels: this.config.channels,
    };
  }

  /**
   * 获取可用设备列表
   */
  async getDevices(): Promise<Result<AudioDeviceInfo[], AudioError>> {
    // 模拟设备列表
    const devices: AudioDeviceInfo[] = [
      {
        id: 'default',
        name: '默认麦克风',
        isDefault: true,
        maxSampleRate: 48000,
        maxChannels: 2,
      },
      {
        id: 'mock-device-1',
        name: '模拟麦克风 1',
        isDefault: false,
        maxSampleRate: 44100,
        maxChannels: 1,
      },
    ];

    return ok(devices);
  }

  /**
   * 生成模拟音频块
   */
  private generateMockChunk(): void {
    // 生成 1 秒的模拟音频数据
    const bytesPerSample = this.config.bitDepth / 8;
    const bytesPerSecond = this.config.sampleRate * this.config.channels * bytesPerSample;
    const mockData = Buffer.alloc(bytesPerSecond);

    // 填充模拟数据（静音）
    mockData.fill(0);

    const chunk: AudioChunk = {
      data: mockData,
      timestamp: (Date.now() - this.startTime) / 1000,
      duration: 1.0,
      sequence: this.chunkSequence++,
    };

    this.totalBytes += mockData.length;
    this.totalFrames += this.config.sampleRate;

    logger.debug(`📦 生成音频块 #${chunk.sequence}: ${chunk.data.length} 字节`);
    this.emit('data', chunk);
  }

  /**
   * 设置状态
   */
  private setState(newState: RecordingState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      logger.debug(`状态变化: ${oldState} → ${newState}`);
      this.emit('stateChange', oldState, newState);
    }
  }
}

/**
 * 创建音频录制器
 * 目前返回模拟录制器，后续可以根据环境选择真实实现
 */
export function createAudioRecorder(config?: Partial<AudioConfig>): IAudioRecorder {
  // TODO: 根据平台选择真实的录制器实现
  // if (process.platform === 'darwin') {
  //   return new MacOSAudioRecorder(config);
  // } else if (process.platform === 'win32') {
  //   return new WindowsAudioRecorder(config);
  // } else {
  //   return new LinuxAudioRecorder(config);
  // }

  logger.warn('⚠️  使用模拟音频录制器（开发模式）');
  return new MockAudioRecorder(config);
}
