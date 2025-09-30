/**
 * Result 类型 - 优雅的错误处理
 * 参考 Rust 的 Result<T, E> 模式
 */

/**
 * 成功结果
 */
export interface Success<T> {
  success: true;
  data: T;
}

/**
 * 失败结果
 */
export interface Failure<E = Error> {
  success: false;
  error: E;
}

/**
 * Result 类型
 */
export type Result<T, E = Error> = Success<T> | Failure<E>;

/**
 * 创建成功结果
 */
export function ok<T>(data: T): Success<T> {
  return { success: true, data };
}

/**
 * 创建失败结果
 */
export function err<E = Error>(error: E): Failure<E> {
  return { success: false, error };
}

/**
 * 检查是否为成功结果
 */
export function isOk<T, E>(result: Result<T, E>): result is Success<T> {
  return result.success === true;
}

/**
 * 检查是否为失败结果
 */
export function isErr<T, E>(result: Result<T, E>): result is Failure<E> {
  return result.success === false;
}

/**
 * 从 Result 中提取数据，如果失败则抛出错误
 */
export function unwrap<T, E>(result: Result<T, E>): T {
  if (isOk(result)) {
    return result.data;
  }
  throw result.error;
}

/**
 * 从 Result 中提取数据，如果失败则返回默认值
 */
export function unwrapOr<T, E>(result: Result<T, E>, defaultValue: T): T {
  return isOk(result) ? result.data : defaultValue;
}

/**
 * 映射成功值
 */
export function map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
  return isOk(result) ? ok(fn(result.data)) : result;
}

/**
 * 映射错误值
 */
export function mapErr<T, E, F>(result: Result<T, E>, fn: (error: E) => F): Result<T, F> {
  return isErr(result) ? err(fn(result.error)) : result;
}

/**
 * 链式调用（flatMap）
 */
export function andThen<T, U, E>(
  result: Result<T, E>,
  fn: (value: T) => Result<U, E>
): Result<U, E> {
  return isOk(result) ? fn(result.data) : result;
}

/**
 * 将 Promise 包装为 Result
 */
export async function fromPromise<T>(promise: Promise<T>): Promise<Result<T, Error>> {
  try {
    const data = await promise;
    return ok(data);
  } catch (error) {
    return err(error instanceof Error ? error : new Error(String(error)));
  }
}

/**
 * 将可能抛出异常的函数包装为 Result
 */
export function tryCatch<T>(fn: () => T): Result<T, Error> {
  try {
    return ok(fn());
  } catch (error) {
    return err(error instanceof Error ? error : new Error(String(error)));
  }
}

/**
 * 异步版本的 tryCatch
 */
export async function tryCatchAsync<T>(fn: () => Promise<T>): Promise<Result<T, Error>> {
  return fromPromise(fn());
}

/**
 * 合并多个 Result，全部成功才返回成功
 */
export function all<T, E>(results: Result<T, E>[]): Result<T[], E> {
  const data: T[] = [];

  for (const result of results) {
    if (isErr(result)) {
      return result;
    }
    data.push(result.data);
  }

  return ok(data);
}
