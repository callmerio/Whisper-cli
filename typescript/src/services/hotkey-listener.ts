/**
 * 热键监听器
 * 负责监听全局热键事件
 */

import { EventEmitter } from 'events';
import { createLogger } from '../utils/logger';
import { Result, ok, err } from '../utils/result';
import { AppError } from '../utils/errors';
import type { HotkeyConfig, HotkeyEvent, HotkeyEventType } from '../types/hotkey';

const logger = createLogger('HotkeyListener');

/**
 * 热键监听器事件
 */
export interface HotkeyListenerEvents {
  /** 热键按下 */
  press: (event: HotkeyEvent) => void;
  /** 热键释放 */
  release: (event: HotkeyEvent) => void;
  /** 长按触发 */
  longPress: (event: HotkeyEvent) => void;
  /** 错误 */
  error: (error: Error) => void;
}

/**
 * 热键监听器接口
 */
export interface IHotkeyListener {
  /** 开始监听 */
  start(): Promise<Result<void, AppError>>;
  /** 停止监听 */
  stop(): Promise<Result<void, AppError>>;
  /** 是否正在监听 */
  isListening(): boolean;
}

/**
 * 模拟热键监听器
 * 用于测试和开发
 */
export class MockHotkeyListener extends EventEmitter implements IHotkeyListener {
  private config: HotkeyConfig;
  private listening: boolean = false;
  private pressTime: number = 0;

  constructor(config: Partial<HotkeyConfig> = {}) {
    super();

    this.config = {
      key: config.key ?? 'left_option',
      threshold: config.threshold ?? 0.03,
      enabled: config.enabled ?? true,
    };

    logger.info(`模拟热键监听器已创建: ${this.config.key}`);
  }

  /**
   * 开始监听
   */
  async start(): Promise<Result<void, AppError>> {
    if (this.listening) {
      return err(new AppError('热键监听已在运行', 'HOTKEY_ERROR'));
    }

    if (!this.config.enabled) {
      return err(new AppError('热键监听已禁用', 'HOTKEY_ERROR'));
    }

    this.listening = true;
    logger.info(`✅ 开始监听热键: ${this.config.key}`);

    return ok(undefined);
  }

  /**
   * 停止监听
   */
  async stop(): Promise<Result<void, AppError>> {
    if (!this.listening) {
      return err(new AppError('热键监听未运行', 'HOTKEY_ERROR'));
    }

    this.listening = false;
    logger.info('✅ 停止监听热键');

    return ok(undefined);
  }

  /**
   * 是否正在监听
   */
  isListening(): boolean {
    return this.listening;
  }

  /**
   * 模拟按下热键（用于测试）
   */
  simulatePress(): void {
    if (!this.listening) {
      logger.warn('热键监听器未运行，无法模拟');
      return;
    }

    this.pressTime = Date.now();

    const event: HotkeyEvent = {
      type: 'press',
      key: this.config.key,
      timestamp: this.pressTime,
    };

    logger.debug(`🔽 模拟按下: ${this.config.key}`);
    this.emit('press', event);
  }

  /**
   * 模拟释放热键（用于测试）
   */
  simulateRelease(): void {
    if (!this.listening) {
      logger.warn('热键监听器未运行，无法模拟');
      return;
    }

    if (!this.pressTime) {
      logger.warn('未检测到按下事件');
      return;
    }

    const releaseTime = Date.now();
    const duration = (releaseTime - this.pressTime) / 1000;

    const event: HotkeyEvent = {
      type: 'release',
      key: this.config.key,
      timestamp: releaseTime,
      duration,
    };

    logger.debug(`🔼 模拟释放: ${this.config.key} (${duration.toFixed(3)}s)`);
    this.emit('release', event);

    // 检查是否为长按
    if (duration >= this.config.threshold) {
      const longPressEvent: HotkeyEvent = {
        type: 'longPress',
        key: this.config.key,
        timestamp: releaseTime,
        duration,
      };

      logger.debug(`⏱️  触发长按: ${duration.toFixed(3)}s`);
      this.emit('longPress', longPressEvent);
    }

    this.pressTime = 0;
  }
}

/**
 * 创建热键监听器
 * 目前返回模拟监听器，后续可以根据环境选择真实实现
 */
export function createHotkeyListener(config?: Partial<HotkeyConfig>): IHotkeyListener {
  // TODO: 根据平台选择真实的监听器实现
  // if (process.platform === 'darwin') {
  //   return new MacOSHotkeyListener(config);
  // } else if (process.platform === 'win32') {
  //   return new WindowsHotkeyListener(config);
  // } else {
  //   return new LinuxHotkeyListener(config);
  // }

  logger.warn('⚠️  使用模拟热键监听器（开发模式）');
  return new MockHotkeyListener(config);
}
