/**
 * 音频相关的类型定义
 */

/**
 * 音频配置
 */
export interface AudioConfig {
  /** 采样率 (Hz) */
  sampleRate: number;
  /** 声道数 */
  channels: number;
  /** 位深度 */
  bitDepth: number;
  /** 音频格式 */
  format: AudioFormat;
  /** 设备ID（可选） */
  deviceId?: string;
}

/**
 * 音频格式
 */
export enum AudioFormat {
  WAV = 'wav',
  PCM = 'pcm',
  MP3 = 'mp3',
  FLAC = 'flac',
}

/**
 * 录音状态
 */
export enum RecordingState {
  /** 空闲 */
  IDLE = 'idle',
  /** 录音中 */
  RECORDING = 'recording',
  /** 暂停 */
  PAUSED = 'paused',
  /** 停止 */
  STOPPED = 'stopped',
  /** 错误 */
  ERROR = 'error',
}

/**
 * 音频数据块
 */
export interface AudioChunk {
  /** 音频数据 */
  data: Buffer;
  /** 时间戳（秒） */
  timestamp: number;
  /** 持续时间（秒） */
  duration: number;
  /** 序列号 */
  sequence: number;
}

/**
 * 录音统计
 */
export interface RecordingStats {
  /** 录音时长（秒） */
  duration: number;
  /** 总帧数 */
  totalFrames: number;
  /** 总字节数 */
  totalBytes: number;
  /** 音频块数量 */
  chunkCount: number;
  /** 采样率 */
  sampleRate: number;
  /** 声道数 */
  channels: number;
}

/**
 * 音频设备信息
 */
export interface AudioDeviceInfo {
  /** 设备ID */
  id: string;
  /** 设备名称 */
  name: string;
  /** 是否为默认设备 */
  isDefault: boolean;
  /** 最大采样率 */
  maxSampleRate: number;
  /** 最大声道数 */
  maxChannels: number;
}
