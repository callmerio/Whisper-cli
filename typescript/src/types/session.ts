/**
 * 会话相关的类型定义
 */

/**
 * 会话模式
 */
export enum SessionMode {
  /** 一口气模式 - 完整录音后统一处理 */
  BATCH = 'batch',
  /** 逐步上屏模式 - 实时分段处理并输出 */
  REALTIME = 'realtime',
}

/**
 * 会话状态
 */
export enum SessionState {
  /** 空闲 */
  IDLE = 'idle',
  /** 录音中 */
  RECORDING = 'recording',
  /** 处理中 */
  PROCESSING = 'processing',
  /** 完成 */
  COMPLETED = 'completed',
  /** 错误 */
  ERROR = 'error',
}

/**
 * 分段状态
 */
export enum SegmentStatus {
  /** 待处理 */
  PENDING = 'pending',
  /** 转录中 */
  TRANSCRIBING = 'transcribing',
  /** 后处理中 */
  PROCESSING = 'processing',
  /** 输出中 */
  OUTPUTTING = 'outputting',
  /** 已完成 */
  COMPLETED = 'completed',
  /** 失败 */
  FAILED = 'failed',
}

/**
 * 音频分段
 */
export interface AudioSegment {
  /** 分段ID */
  id: string;
  /** 音频数据 */
  audioData: Buffer;
  /** 开始时间（秒） */
  startTime: number;
  /** 结束时间（秒） */
  endTime: number;
  /** 时长（秒） */
  duration: number;
  /** 是否为最终分段 */
  isFinal: boolean;
  /** 采样率 */
  sampleRate: number;
  /** 声道数 */
  channels: number;
}

/**
 * 处理后的分段
 */
export interface ProcessedSegment {
  /** 分段ID */
  segmentId: string;
  /** 原始音频分段 */
  originalAudio: AudioSegment;
  /** 原始转录结果 */
  rawTranscript?: string;
  /** 词典处理后的文本 */
  processedTranscript?: string;
  /** 纠错后的文本 */
  correctedTranscript?: string;
  /** 最终文本 */
  finalText?: string;
  /** 状态 */
  status: SegmentStatus;
  /** 错误信息 */
  errorMessage?: string;
  /** 处理时间统计 */
  processingTimes: {
    transcription?: number;
    dictionary?: number;
    correction?: number;
    output?: number;
    total?: number;
  };
  /** 元数据 */
  metadata: Record<string, unknown>;
  /** 创建时间 */
  createdTime: number;
  /** 完成时间 */
  completedTime?: number;
}

/**
 * 会话配置
 */
export interface SessionConfig {
  /** 会话模式 */
  mode: SessionMode;
  /** 静音检测时长（秒） */
  silenceDuration: number;
  /** 最小分段时长（秒） */
  minSegmentDuration: number;
  /** 音量阈值 */
  volumeThreshold: number;
  /** 自动输出到光标位置 */
  autoOutputEnabled: boolean;
  /** 剪贴板备份 */
  clipboardBackup: boolean;
  /** 启用纠错 */
  enableCorrection: boolean;
  /** 启用词典 */
  enableDictionary: boolean;
}

/**
 * 会话统计
 */
export interface SessionStats {
  /** 会话ID */
  sessionId: string;
  /** 会话模式 */
  mode: SessionMode;
  /** 录音时长（秒） */
  recordingDuration: number;
  /** 处理时长（秒） */
  processingDuration: number;
  /** 总时长（秒） */
  totalDuration: number;
  /** 分段数量 */
  segmentCount: number;
  /** 成功分段数 */
  successCount: number;
  /** 失败分段数 */
  failureCount: number;
  /** 最终文本 */
  finalText: string;
  /** 字符数 */
  characterCount: number;
  /** 词数 */
  wordCount: number;
}

