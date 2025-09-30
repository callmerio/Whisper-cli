/**
 * 剪贴板管理器
 */

import clipboardy from 'clipboardy';
import { createLogger } from '../utils/logger';
import { Result, ok, err, tryCatchAsync } from '../utils/result';
import { AppError } from '../utils/errors';
import { sanitizeText, countCharacters, countWords } from '../utils/text-utils';

const logger = createLogger('ClipboardManager');

/**
 * 剪贴板操作错误
 */
export class ClipboardError extends AppError {
  constructor(message: string, details?: unknown) {
    super(message, 'CLIPBOARD_ERROR', details);
    this.name = 'ClipboardError';
  }
}

/**
 * 剪贴板统计信息
 */
export interface ClipboardStats {
  characters: number;
  words: number;
  lines: number;
}

/**
 * 剪贴板管理器
 */
export class ClipboardManager {
  private lastBackup: string | null = null;

  /**
   * 读取剪贴板内容
   */
  async read(): Promise<Result<string, ClipboardError>> {
    logger.debug('读取剪贴板内容');

    const result = await tryCatchAsync(async () => {
      return await clipboardy.read();
    });

    if (result.success) {
      logger.debug(`✅ 读取成功: ${result.data.length} 字符`);
      return ok(result.data);
    }

    return err(new ClipboardError('读取剪贴板失败', result.error));
  }

  /**
   * 写入剪贴板内容
   */
  async write(text: string, backup: boolean = true): Promise<Result<void, ClipboardError>> {
    logger.debug(`写入剪贴板: ${text.length} 字符`);

    // 备份当前内容
    if (backup) {
      const currentResult = await this.read();
      if (currentResult.success) {
        this.lastBackup = currentResult.data;
        logger.debug('已备份当前剪贴板内容');
      }
    }

    const result = await tryCatchAsync(async () => {
      await clipboardy.write(text);
    });

    if (result.success) {
      logger.debug('✅ 写入成功');
      return ok(undefined);
    }

    return err(new ClipboardError('写入剪贴板失败', result.error));
  }

  /**
   * 恢复备份的内容
   */
  async restore(): Promise<Result<void, ClipboardError>> {
    if (!this.lastBackup) {
      logger.warn('没有备份内容可恢复');
      return err(new ClipboardError('没有备份内容'));
    }

    logger.debug('恢复剪贴板备份');

    const result = await tryCatchAsync(async () => {
      await clipboardy.write(this.lastBackup!);
      this.lastBackup = null;
    });

    if (result.success) {
      logger.debug('✅ 恢复成功');
      return ok(undefined);
    }

    return err(new ClipboardError('恢复剪贴板失败', result.error));
  }

  /**
   * 清空剪贴板
   */
  async clear(): Promise<Result<void, ClipboardError>> {
    return this.write('', false);
  }

  /**
   * 获取剪贴板统计信息
   */
  async getStats(): Promise<Result<ClipboardStats, ClipboardError>> {
    const readResult = await this.read();

    if (!readResult.success) {
      return err(readResult.error);
    }

    const text = readResult.data;
    const stats: ClipboardStats = {
      characters: countCharacters(text),
      words: countWords(text),
      lines: text.split('\n').length,
    };

    return ok(stats);
  }

  /**
   * 清理并写入文本
   * @param text 要写入的文本
   * @param options 选项
   */
  async writeSanitized(
    text: string,
    options: {
      backup?: boolean;
      trim?: boolean;
      removeNewlines?: boolean;
    } = {}
  ): Promise<Result<string, ClipboardError>> {
    const { backup = true, trim = true, removeNewlines = false } = options;

    let processedText = text;

    if (removeNewlines) {
      processedText = sanitizeText(processedText);
    } else if (trim) {
      processedText = processedText.trim();
    }

    const writeResult = await this.write(processedText, backup);

    if (!writeResult.success) {
      return err(writeResult.error);
    }

    return ok(processedText);
  }

  /**
   * 追加文本到剪贴板
   */
  async append(
    text: string,
    separator: string = '\n'
  ): Promise<Result<void, ClipboardError>> {
    const readResult = await this.read();

    if (!readResult.success) {
      return err(readResult.error);
    }

    const currentText = readResult.data;
    const newText = currentText ? `${currentText}${separator}${text}` : text;

    return this.write(newText, false);
  }

  /**
   * 检查剪贴板是否有备份
   */
  hasBackup(): boolean {
    return this.lastBackup !== null;
  }

  /**
   * 清除备份
   */
  clearBackup(): void {
    this.lastBackup = null;
    logger.debug('已清除备份');
  }
}

/**
 * 创建剪贴板管理器
 */
export function createClipboardManager(): ClipboardManager {
  return new ClipboardManager();
}

/**
 * 全局剪贴板管理器实例（单例）
 */
export const clipboardManager = createClipboardManager();
