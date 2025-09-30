/**
 * 文件系统适配器
 */

import { promises as fs } from 'fs';
import { dirname } from 'path';
import { Result, ok, err, tryCatchAsync } from './result';
import { FileSystemError } from './errors';
import { createLogger } from './logger';

const logger = createLogger('FileAdapter');

/**
 * 读取文本文件
 */
export async function readTextFile(filePath: string): Promise<Result<string, FileSystemError>> {
  logger.debug(`读取文件: ${filePath}`);

  const result = await tryCatchAsync(async () => {
    return await fs.readFile(filePath, 'utf-8');
  });

  if (result.success) {
    return ok(result.data);
  }

  return err(new FileSystemError(`读取文件失败: ${filePath}`, result.error));
}

/**
 * 写入文本文件
 */
export async function writeTextFile(
  filePath: string,
  content: string
): Promise<Result<void, FileSystemError>> {
  logger.debug(`写入文件: ${filePath}`);

  const result = await tryCatchAsync(async () => {
    // 确保目录存在
    await fs.mkdir(dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, content, 'utf-8');
  });

  if (result.success) {
    return ok(undefined);
  }

  return err(new FileSystemError(`写入文件失败: ${filePath}`, result.error));
}

/**
 * 追加内容到文件
 */
export async function appendTextFile(
  filePath: string,
  content: string
): Promise<Result<void, FileSystemError>> {
  logger.debug(`追加内容到文件: ${filePath}`);

  const result = await tryCatchAsync(async () => {
    // 确保目录存在
    await fs.mkdir(dirname(filePath), { recursive: true });
    await fs.appendFile(filePath, content, 'utf-8');
  });

  if (result.success) {
    return ok(undefined);
  }

  return err(new FileSystemError(`追加文件失败: ${filePath}`, result.error));
}

/**
 * 检查文件是否存在
 */
export async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * 读取 JSON 文件
 */
export async function readJsonFile<T>(filePath: string): Promise<Result<T, FileSystemError>> {
  const readResult = await readTextFile(filePath);

  if (!readResult.success) {
    return err(readResult.error);
  }

  const parseResult = await tryCatchAsync(async () => {
    return JSON.parse(readResult.data) as T;
  });

  if (parseResult.success) {
    return ok(parseResult.data);
  }

  return err(new FileSystemError(`解析 JSON 文件失败: ${filePath}`, parseResult.error));
}

/**
 * 写入 JSON 文件
 */
export async function writeJsonFile<T>(
  filePath: string,
  data: T,
  pretty: boolean = true
): Promise<Result<void, FileSystemError>> {
  const content = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
  return writeTextFile(filePath, content);
}
