/**
 * 自定义错误类型
 */

/**
 * 基础应用错误
 */
export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = 'AppError';
    Error.captureStackTrace(this, this.constructor);
  }
}

/**
 * 配置错误
 */
export class ConfigError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'CONFIG_ERROR', details);
    this.name = 'ConfigError';
  }
}

/**
 * Gemini API 错误
 */
export class GeminiError extends AppError {
  constructor(
    message: string,
    public readonly statusCode?: number,
    details?: unknown
  ) {
    super(message, 'GEMINI_ERROR', details);
    this.name = 'GeminiError';
  }
}

/**
 * 音频处理错误
 */
export class AudioError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'AUDIO_ERROR', details);
    this.name = 'AudioError';
  }
}

/**
 * 热键错误
 */
export class HotkeyError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'HOTKEY_ERROR', details);
    this.name = 'HotkeyError';
  }
}

/**
 * 文件系统错误
 */
export class FileSystemError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'FILE_SYSTEM_ERROR', details);
    this.name = 'FileSystemError';
  }
}

/**
 * 验证错误
 */
export class ValidationError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'VALIDATION_ERROR', details);
    this.name = 'ValidationError';
  }
}

/**
 * 判断是否为特定错误类型
 */
export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}

/**
 * 格式化错误信息
 */
export function formatError(error: unknown): string {
  if (isAppError(error)) {
    return `[${error.code}] ${error.message}`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}
