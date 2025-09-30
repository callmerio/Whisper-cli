/**
 * 增强版日志工具
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  SILENT = 4,
}

const LOG_LEVEL_NAMES: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: 'DEBUG',
  [LogLevel.INFO]: 'INFO',
  [LogLevel.WARN]: 'WARN',
  [LogLevel.ERROR]: 'ERROR',
  [LogLevel.SILENT]: 'SILENT',
};

const LOG_LEVEL_COLORS: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: '\x1b[36m', // Cyan
  [LogLevel.INFO]: '\x1b[32m', // Green
  [LogLevel.WARN]: '\x1b[33m', // Yellow
  [LogLevel.ERROR]: '\x1b[31m', // Red
  [LogLevel.SILENT]: '',
};

const RESET_COLOR = '\x1b[0m';

interface LoggerOptions {
  prefix?: string;
  minLevel?: LogLevel;
  enableColors?: boolean;
  enableTimestamp?: boolean;
}

class Logger {
  private prefix: string;
  private minLevel: LogLevel;
  private enableColors: boolean;
  private enableTimestamp: boolean;

  constructor(options: LoggerOptions = {}) {
    this.prefix = options.prefix || 'APP';
    this.minLevel = options.minLevel ?? LogLevel.INFO;
    this.enableColors = options.enableColors ?? true;
    this.enableTimestamp = options.enableTimestamp ?? true;
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.minLevel;
  }

  private formatMessage(level: LogLevel, message: string): string {
    const parts: string[] = [];

    if (this.enableTimestamp) {
      const timestamp = new Date().toISOString();
      parts.push(`[${timestamp}]`);
    }

    parts.push(`[${this.prefix}]`);

    const levelName = LOG_LEVEL_NAMES[level];
    if (this.enableColors && process.stdout.isTTY) {
      const color = LOG_LEVEL_COLORS[level];
      parts.push(`${color}[${levelName}]${RESET_COLOR}`);
    } else {
      parts.push(`[${levelName}]`);
    }

    parts.push(message);

    return parts.join(' ');
  }

  debug(message: string, ...args: unknown[]): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      console.debug(this.formatMessage(LogLevel.DEBUG, message), ...args);
    }
  }

  info(message: string, ...args: unknown[]): void {
    if (this.shouldLog(LogLevel.INFO)) {
      console.info(this.formatMessage(LogLevel.INFO, message), ...args);
    }
  }

  warn(message: string, ...args: unknown[]): void {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(this.formatMessage(LogLevel.WARN, message), ...args);
    }
  }

  error(message: string, ...args: unknown[]): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.error(this.formatMessage(LogLevel.ERROR, message), ...args);
    }
  }

  /**
   * 记录带代码的错误
   */
  errorWithCode(code: string, message: string, ...args: unknown[]): void {
    this.error(`[${code}] ${message}`, ...args);
  }

  /**
   * 设置日志级别
   */
  setLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  /**
   * 获取当前日志级别
   */
  getLevel(): LogLevel {
    return this.minLevel;
  }

  /**
   * 创建子 Logger
   */
  child(childPrefix: string): Logger {
    return new Logger({
      prefix: `${this.prefix}:${childPrefix}`,
      minLevel: this.minLevel,
      enableColors: this.enableColors,
      enableTimestamp: this.enableTimestamp,
    });
  }
}

/**
 * 全局日志级别（从环境变量读取）
 */
const getGlobalLogLevel = (): LogLevel => {
  const level = process.env.LOG_LEVEL?.toUpperCase();
  switch (level) {
    case 'DEBUG':
      return LogLevel.DEBUG;
    case 'INFO':
      return LogLevel.INFO;
    case 'WARN':
      return LogLevel.WARN;
    case 'ERROR':
      return LogLevel.ERROR;
    case 'SILENT':
      return LogLevel.SILENT;
    default:
      return process.env.DEBUG_MODE === 'true' ? LogLevel.DEBUG : LogLevel.INFO;
  }
};

/**
 * 创建 Logger 实例
 */
export const createLogger = (prefix: string, options?: Partial<LoggerOptions>): Logger => {
  return new Logger({
    prefix,
    minLevel: getGlobalLogLevel(),
    ...options,
  });
};

/**
 * 默认 Logger
 */
export const logger = createLogger('APP');
