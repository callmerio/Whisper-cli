/**
 * 简单的日志工具
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
}

class Logger {
  private prefix: string;

  constructor(prefix: string = 'APP') {
    this.prefix = prefix;
  }

  private formatMessage(level: LogLevel, message: string): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${this.prefix}] [${level}] ${message}`;
  }

  debug(message: string, ...args: unknown[]): void {
    console.debug(this.formatMessage(LogLevel.DEBUG, message), ...args);
  }

  info(message: string, ...args: unknown[]): void {
    console.info(this.formatMessage(LogLevel.INFO, message), ...args);
  }

  warn(message: string, ...args: unknown[]): void {
    console.warn(this.formatMessage(LogLevel.WARN, message), ...args);
  }

  error(message: string, ...args: unknown[]): void {
    console.error(this.formatMessage(LogLevel.ERROR, message), ...args);
  }
}

export const createLogger = (prefix: string): Logger => new Logger(prefix);
