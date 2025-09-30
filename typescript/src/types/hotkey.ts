/**
 * 热键相关的类型定义
 */

/**
 * 热键配置
 */
export interface HotkeyConfig {
  /** 热键名称 */
  key: string;
  /** 长按阈值（秒） */
  threshold: number;
  /** 是否启用 */
  enabled: boolean;
}

/**
 * 热键事件类型
 */
export enum HotkeyEventType {
  /** 按下 */
  PRESS = 'press',
  /** 释放 */
  RELEASE = 'release',
  /** 长按触发 */
  LONG_PRESS = 'longPress',
}

/**
 * 热键事件
 */
export interface HotkeyEvent {
  /** 事件类型 */
  type: HotkeyEventType;
  /** 热键名称 */
  key: string;
  /** 时间戳 */
  timestamp: number;
  /** 按下时长（秒，仅释放事件有效） */
  duration?: number;
}
