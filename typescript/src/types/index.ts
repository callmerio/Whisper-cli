/**
 * 核心类型定义
 */

/**
 * Result 类型 - 用于优雅的错误处理
 */
export type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };

/**
 * 配置接口
 */
export interface Config {
  gemini: {
    apiKey: string;
    model: string;
    baseUrl?: string;
  };
  hotkey: {
    key: string;
    threshold: number;
  };
  audio: {
    sampleRate: number;
    channels: number;
  };
}

/**
 * 音频数据
 */
export interface AudioData {
  samples: Float32Array;
  sampleRate: number;
  duration: number;
}

/**
 * 转录结果
 */
export interface TranscriptionResult {
  text: string;
  duration: number;
  timestamp: Date;
}
