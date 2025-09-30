/**
 * 词典管理器
 * 负责加载和应用用户自定义词汇
 */

import { resolve } from 'path';
import type { DictionaryConfig } from '../core/config';
import { createLogger } from '../utils/logger';
import { Result, ok, err, isOk } from '../utils/result';
import { FileSystemError, ValidationError } from '../utils/errors';
import { readTextFile, fileExists } from '../utils/file-adapter';
import { calculateSimilarity } from '../utils/text-utils';

const logger = createLogger('DictionaryManager');

/**
 * 词典条目
 */
export interface DictionaryEntry {
  original: string; // 原词汇
  target: string; // 目标词汇
  weight: number; // 权重 (0-1)
  enabled: boolean; // 是否启用
}

/**
 * 替换结果
 */
export interface ReplacementResult {
  text: string; // 替换后的文本
  replacements: Array<{
    original: string;
    target: string;
    position: number;
  }>;
}

/**
 * 词典管理器
 */
export class DictionaryManager {
  private config: DictionaryConfig;
  private entries: DictionaryEntry[] = [];
  private isLoaded: boolean = false;

  constructor(config: DictionaryConfig) {
    this.config = config;
  }

  /**
   * 加载词典文件
   */
  async load(): Promise<Result<number, FileSystemError | ValidationError>> {
    if (!this.config.enabled) {
      logger.info('词典功能已禁用');
      return ok(0);
    }

    logger.info(`加载词典文件: ${this.config.filePath}`);

    // 检查文件是否存在
    const exists = await fileExists(this.config.filePath);
    if (!exists) {
      logger.warn(`词典文件不存在: ${this.config.filePath}`);
      return ok(0);
    }

    // 读取文件
    const readResult = await readTextFile(this.config.filePath);
    if (!isOk(readResult)) {
      return err(readResult.error);
    }

    const content = readResult.data;

    // 解析词典条目
    this.entries = [];
    const lines = content.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // 跳过空行和注释
      if (!line || line.startsWith('#')) {
        continue;
      }

      // 解析格式: "词汇:权重%" 或 "原词汇->目标词汇:权重%"
      const parseResult = this.parseLine(line, i + 1);
      if (parseResult) {
        this.entries.push(parseResult);
      }
    }

    this.isLoaded = true;
    logger.info(`✅ 词典加载成功: ${this.entries.length} 个条目`);

    return ok(this.entries.length);
  }

  /**
   * 解析词典行
   */
  private parseLine(line: string, lineNumber: number): DictionaryEntry | null {
    try {
      // 格式1: "词汇:30.0%" - 仅权重，原词汇和目标词汇相同
      // 格式2: "原词汇->目标词汇:30.0%" - 指定替换目标
      let original: string;
      let target: string;
      let weightStr: string;

      if (line.includes('->')) {
        // 格式2: 包含替换目标
        const [mapping, weight] = line.split(':');
        const [orig, tgt] = mapping.split('->');

        original = orig.trim();
        target = tgt.trim();
        weightStr = weight.trim();
      } else {
        // 格式1: 仅权重
        const [word, weight] = line.split(':');

        original = word.trim();
        target = original;
        weightStr = weight.trim();
      }

      // 解析权重
      const weightMatch = weightStr.match(/(\d+(?:\.\d+)?)/);
      if (!weightMatch) {
        logger.warn(`行 ${lineNumber}: 无法解析权重: ${line}`);
        return null;
      }

      const weight = parseFloat(weightMatch[1]) / 100; // 转换为 0-1

      if (weight < 0 || weight > 1) {
        logger.warn(`行 ${lineNumber}: 权重超出范围 [0, 100]: ${line}`);
        return null;
      }

      return {
        original,
        target,
        weight,
        enabled: true,
      };
    } catch (error) {
      logger.warn(`行 ${lineNumber}: 解析失败: ${line}`, error);
      return null;
    }
  }

  /**
   * 应用词典替换
   */
  applyDictionary(text: string): ReplacementResult {
    if (!this.config.enabled || !this.isLoaded || this.entries.length === 0) {
      return {
        text,
        replacements: [],
      };
    }

    logger.debug(`应用词典替换: ${text.length} 字符`);

    let resultText = text;
    const replacements: ReplacementResult['replacements'] = [];

    // 按权重排序（高权重优先）
    const sortedEntries = [...this.entries]
      .filter((e) => e.enabled)
      .sort((a, b) => b.weight - a.weight);

    for (const entry of sortedEntries) {
      // 查找所有匹配项
      const regex = new RegExp(this.escapeRegex(entry.original), 'gi');
      let match;

      while ((match = regex.exec(resultText)) !== null) {
        // 计算相似度
        const matchText = match[0];
        const similarity = calculateSimilarity(
          matchText.toLowerCase(),
          entry.original.toLowerCase()
        );

        // 如果相似度超过阈值，进行替换
        if (similarity >= this.config.weightThreshold) {
          // 应用权重影响
          const shouldReplace = this.shouldReplace(entry.weight);

          if (shouldReplace) {
            // 记录替换
            replacements.push({
              original: matchText,
              target: entry.target,
              position: match.index,
            });

            // 执行替换（保持原文的大小写风格）
            const replacement = this.preserveCase(matchText, entry.target);
            resultText =
              resultText.substring(0, match.index) +
              replacement +
              resultText.substring(match.index + matchText.length);

            // 重置正则表达式的 lastIndex
            regex.lastIndex = match.index + replacement.length;
          }
        }
      }
    }

    if (replacements.length > 0) {
      logger.debug(`✅ 完成 ${replacements.length} 处替换`);
    }

    return {
      text: resultText,
      replacements,
    };
  }

  /**
   * 根据权重决定是否替换
   */
  private shouldReplace(weight: number): boolean {
    // 权重影响替换概率
    const effectiveWeight = Math.min(weight, this.config.maxWeight);
    return Math.random() < effectiveWeight || effectiveWeight >= 0.9;
  }

  /**
   * 保持原文的大小写风格
   */
  private preserveCase(original: string, target: string): string {
    // 如果原文全大写
    if (original === original.toUpperCase()) {
      return target.toUpperCase();
    }

    // 如果原文首字母大写
    if (original[0] === original[0].toUpperCase() && original.slice(1) === original.slice(1).toLowerCase()) {
      return target.charAt(0).toUpperCase() + target.slice(1).toLowerCase();
    }

    // 其他情况保持目标词汇原样
    return target;
  }

  /**
   * 转义正则表达式特殊字符
   */
  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * 获取词典统计信息
   */
  getStats(): {
    total: number;
    enabled: number;
    averageWeight: number;
  } {
    const enabled = this.entries.filter((e) => e.enabled);
    const averageWeight =
      enabled.length > 0 ? enabled.reduce((sum, e) => sum + e.weight, 0) / enabled.length : 0;

    return {
      total: this.entries.length,
      enabled: enabled.length,
      averageWeight,
    };
  }

  /**
   * 获取所有词典条目
   */
  getEntries(): DictionaryEntry[] {
    return [...this.entries];
  }

  /**
   * 是否已加载
   */
  isReady(): boolean {
    return this.isLoaded;
  }
}

/**
 * 创建词典管理器
 */
export function createDictionaryManager(config: DictionaryConfig): DictionaryManager {
  return new DictionaryManager(config);
}
