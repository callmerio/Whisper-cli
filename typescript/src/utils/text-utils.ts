/**
 * 文本处理工具函数
 */

/**
 * 计算两个字符串的相似度（使用 Levenshtein 距离）
 * @returns 0-1 之间的相似度值，1 表示完全相同
 */
export function calculateSimilarity(str1: string, str2: string): number {
  if (str1 === str2) return 1;
  if (str1.length === 0 || str2.length === 0) return 0;

  const matrix: number[][] = [];

  // 初始化矩阵
  for (let i = 0; i <= str1.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= str2.length; j++) {
    matrix[0][j] = j;
  }

  // 填充矩阵
  for (let i = 1; i <= str1.length; i++) {
    for (let j = 1; j <= str2.length; j++) {
      const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1, // 删除
        matrix[i][j - 1] + 1, // 插入
        matrix[i - 1][j - 1] + cost // 替换
      );
    }
  }

  const distance = matrix[str1.length][str2.length];
  const maxLength = Math.max(str1.length, str2.length);

  return 1 - distance / maxLength;
}

/**
 * 规范化文本（去除多余空格、统一大小写等）
 */
export function normalizeText(text: string): string {
  return text
    .trim()
    .replace(/\s+/g, ' ') // 多个空格替换为单个
    .toLowerCase();
}

/**
 * 检查字符串是否包含中文
 */
export function containsChinese(text: string): boolean {
  return /[\u4e00-\u9fa5]/.test(text);
}

/**
 * 统计文本中的字符数（不包括空格）
 */
export function countCharacters(text: string): number {
  return text.replace(/\s/g, '').length;
}

/**
 * 统计文本中的单词数
 */
export function countWords(text: string): number {
  // 中文按字数统计，英文按空格分隔
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  const englishWords = text
    .replace(/[\u4e00-\u9fa5]/g, '')
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0).length;

  return chineseChars + englishWords;
}

/**
 * 清理文本中的特殊字符
 */
export function sanitizeText(text: string): string {
  return text
    .replace(/[\r\n]+/g, ' ') // 换行替换为空格
    .replace(/\s+/g, ' ') // 多个空格替换为单个
    .trim();
}

