#!/usr/bin/env python3
"""
音频重试队列管理器
实现音频暂存、指数退避重试、新录音强制覆盖等功能
"""

import hashlib
import json
import os
import queue
import tempfile
import threading
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any

import numpy as np

import config


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "待处理"
    PROCESSING = "处理中"
    RETRY_WAITING = "等待重试"
    SUCCESS = "成功"
    FAILED = "失败"
    CANCELLED = "已取消"


@dataclass
class RetryTask:
    """重试任务数据结构"""
    task_id: str
    audio_path: Path
    created_time: float
    fingerprint: str
    attempt_count: int = 0
    last_attempt_time: Optional[float] = None
    next_retry_time: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def load_audio(self) -> Optional[np.ndarray]:
        if not self.audio_path.exists():
            return None
        try:
            return np.load(self.audio_path, allow_pickle=False)
        except Exception as exc:
            print(f"⚠️  加载重试音频失败: {exc}")
            return None

    def cleanup(self) -> None:
        try:
            if self.audio_path.exists():
                self.audio_path.unlink()
        except OSError:
            pass

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['audio_path'] = str(self.audio_path)
        data['status'] = self.status.value
        return data


class AudioRetryManager:
    """音频重试队列管理器"""
    
    def __init__(self, max_retry_attempts: int = 8, base_delay: float = 30.0):
        """
        初始化重试管理器
        
        Args:
            max_retry_attempts: 最大重试次数
            base_delay: 基础延迟时间（秒）
        """
        self.max_retry_attempts = max_retry_attempts
        self.base_delay = base_delay
        
        # 任务队列和存储
        self.pending_tasks: queue.Queue = queue.Queue()
        self.high_priority_tasks: queue.Queue = queue.Queue()
        self.retry_tasks: Dict[str, RetryTask] = {}  # 等待重试的任务
        self.active_task: Optional[RetryTask] = None  # 当前处理的任务
        
        # 线程控制
        self.worker_thread: Optional[threading.Thread] = None
        self.retry_thread: Optional[threading.Thread] = None
        self.running = False
        self.lock = threading.Lock()
        
        # 回调函数
        self.transcription_callback: Optional[Callable[[np.ndarray], Optional[str]]] = None
        self.success_callback: Optional[Callable[[str, str], None]] = None  # (task_id, transcript)
        self.failure_callback: Optional[Callable[[str, str], None]] = None  # (task_id, error)
        
        # 持久化配置
        self.persistence_enabled = True
        self.state_file = Path(config.PROJECT_ROOT) / "logs" / "retry_queue.json"
        
        # 确保日志目录存在
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        print("🔄 音频重试管理器已初始化")
        print(f"   最大重试次数: {self.max_retry_attempts}")
        print(f"   基础延迟: {self.base_delay}秒")
        print(f"   指数退避序列: {self._get_retry_delays()}")
    
    def _get_retry_delays(self) -> List[float]:
        """获取重试延迟序列（用于显示）"""
        delays = []
        for i in range(self.max_retry_attempts):
            delay = self.base_delay * (2 ** i)
            delays.append(delay)
        return delays
    
    def set_callbacks(self, 
                     transcription_callback: Callable[[np.ndarray], Optional[str]],
                     success_callback: Optional[Callable[[str, str], None]] = None,
                     failure_callback: Optional[Callable[[str, str], None]] = None):
        """设置回调函数"""
        self.transcription_callback = transcription_callback
        self.success_callback = success_callback
        self.failure_callback = failure_callback
    
    def submit_audio(self, audio_data: np.ndarray, task_id: Optional[str] = None, 
                    force_immediate: bool = False, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        提交音频任务
        
        Args:
            audio_data: 音频数据
            task_id: 任务ID（如果为None则自动生成）
            force_immediate: 是否强制立即处理（新录音覆盖机制）
            metadata: 任务元数据
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = f"audio_task_{int(time.time() * 1000)}"

        audio_dir = Path(config.PROJECT_ROOT) / "logs" / "retry_audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(prefix=f"{task_id}_", suffix=".npy", dir=str(audio_dir))
        os.close(fd)

        safe_audio = audio_data.astype(np.float32, copy=True)
        np.save(temp_path, safe_audio, allow_pickle=False)

        slice_length = min(len(safe_audio), int(config.SAMPLE_RATE * 2))
        sample_bytes = safe_audio[:slice_length].tobytes()
        fingerprint = hashlib.sha1(sample_bytes).hexdigest()[:12]

        task = RetryTask(
            task_id=task_id,
            audio_path=Path(temp_path),
            created_time=time.time(),
            fingerprint=fingerprint,
            metadata=metadata or {}
        )
        
        with self.lock:
            if force_immediate:
                # 将任务放入高优先级队列，不再清空已有任务
                self.high_priority_tasks.put(task)
                print(f"🚨 高优先级音频任务: {task_id} ({fingerprint})")
            else:
                # 正常排队
                self.pending_tasks.put(task)
                print(f"📥 提交音频任务: {task_id} ({fingerprint})")
        
        # 保存状态
        self._save_state()
        
        return task_id
    
    def _cancel_all_pending_tasks(self, reason: str):
        """取消所有待处理和重试任务"""
        # 取消重试任务
        cancelled_count = 0
        for task_id, task in list(self.retry_tasks.items()):
            task.status = TaskStatus.CANCELLED
            task.error_message = reason
            task.cleanup()
            print(f"❌ 取消重试任务: {task_id} - {reason}")
            cancelled_count += 1

        # 清空重试队列
        self.retry_tasks.clear()
        
        # 取消待处理队列中的任务
        while not self.pending_tasks.empty():
            try:
                task = self.pending_tasks.get_nowait()
                task.status = TaskStatus.CANCELLED
                task.error_message = reason
                task.cleanup()
                cancelled_count += 1
            except queue.Empty:
                break

        # 取消高优先级队列中的任务
        while not self.high_priority_tasks.empty():
            try:
                task = self.high_priority_tasks.get_nowait()
                task.status = TaskStatus.CANCELLED
                task.error_message = reason
                task.cleanup()
                cancelled_count += 1
            except queue.Empty:
                break

        # 重新创建空队列
        self.pending_tasks = queue.Queue()
        self.high_priority_tasks = queue.Queue()

        if cancelled_count > 0:
            print(f"🧹 已取消 {cancelled_count} 个任务")
    
    def start(self):
        """启动重试管理器"""
        if self.running:
            return
        
        self.running = True
        
        # 恢复状态
        self._load_state()
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # 启动重试检查线程
        self.retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.start()
        
        print("✅ 音频重试管理器已启动")
    
    def stop(self):
        """停止重试管理器"""
        if not self.running:
            return
        
        print("🛑 正在停止音频重试管理器...")
        self.running = False
        
        # 保存状态
        self._save_state()
        
        # 等待线程结束
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        
        if self.retry_thread and self.retry_thread.is_alive():
            self.retry_thread.join(timeout=2.0)
        
        print("✅ 音频重试管理器已停止")
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self.running:
            try:
                # 从队列获取任务（阻塞等待）
                task = self._get_next_task(timeout=1.0)
                if not self.running:
                    break

                # 处理任务
                self._process_task(task)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 工作线程异常: {e}")
                if config.DEBUG_MODE:
                    import traceback
                    traceback.print_exc()
    
    def _retry_loop(self):
        """重试检查线程主循环"""
        while self.running:
            try:
                current_time = time.time()

                ready_tasks = []
                next_wakeup: Optional[float] = None

                # 检查需要重试的任务，并计算最短等待时间
                with self.lock:
                    for task_id, task in list(self.retry_tasks.items()):
                        if task.status != TaskStatus.RETRY_WAITING or not task.next_retry_time:
                            continue

                        if current_time >= task.next_retry_time:
                            ready_tasks.append(task)
                        else:
                            delay = task.next_retry_time - current_time
                            if next_wakeup is None or delay < next_wakeup:
                                next_wakeup = delay

                # 将准备好的任务重新提交
                for task in ready_tasks:
                    with self.lock:
                        if task.task_id in self.retry_tasks:
                            del self.retry_tasks[task.task_id]

                    task.status = TaskStatus.PENDING
                    self.pending_tasks.put(task)
                    print(f"🔄 重试任务: {task.task_id} (第{task.attempt_count + 1}次尝试，指纹 {task.fingerprint})")

                # 动态休眠，至少 0.1s，最多 2s，默认 0.5s
                sleep_time = 0.5
                if next_wakeup is not None:
                    sleep_time = max(0.1, min(next_wakeup, 2.0))
                elif not ready_tasks:
                    sleep_time = 0.5
                else:
                    sleep_time = 0.05

                time.sleep(sleep_time)

            except Exception as e:
                print(f"❌ 重试线程异常: {e}")
                if config.DEBUG_MODE:
                    import traceback
                    traceback.print_exc()
                time.sleep(1.0)
    
    def _process_task(self, task: RetryTask):
        """处理单个任务"""
        if not self.transcription_callback:
            print(f"❌ 未设置转录回调函数")
            return
        
        with self.lock:
            self.active_task = task
        task.status = TaskStatus.PROCESSING
        task.attempt_count += 1
        task.last_attempt_time = time.time()
        
        print(f"🎯 处理音频任务: {task.task_id} (第{task.attempt_count}次尝试，指纹 {task.fingerprint})")
        
        try:
            audio_payload = task.load_audio()
            if audio_payload is None:
                task.status = TaskStatus.FAILED
                task.cleanup()
                print(f"❌ 任务失败: {task.task_id} - 音频数据缺失")
                if self.failure_callback:
                    try:
                        self.failure_callback(task.task_id, "音频数据缺失")
                    except Exception as exc:
                        print(f"⚠️  失败回调异常: {exc}")
                self._save_state()
                return

            transcript = self.transcription_callback(audio_payload)
            
            if transcript and transcript.strip():
                # 转录成功
                task.status = TaskStatus.SUCCESS
                print(f"✅ 任务成功: {task.task_id}")
                clean_text = transcript.strip()
                if len(clean_text) > 80:
                    clean_text = clean_text[:77] + "..."
                print(f"📝 转录结果: {clean_text}")
                task.cleanup()
                
                # 调用成功回调
                if self.success_callback:
                    try:
                        self.success_callback(task.task_id, transcript.strip())
                    except Exception as e:
                        print(f"⚠️  成功回调异常: {e}")
                self._save_state()
            else:
                # 转录失败，安排重试
                self._schedule_retry(task, "转录返回空结果")

        except Exception as e:
            # 转录异常，安排重试
            self._schedule_retry(task, f"转录异常: {str(e)}")

        finally:
            # 清除当前活跃任务引用
            with self.lock:
                if self.active_task and self.active_task.task_id == task.task_id:
                    self.active_task = None
                
    
    def _schedule_retry(self, task: RetryTask, error_message: str):
        """安排任务重试"""
        task.error_message = error_message
        
        if task.attempt_count >= self.max_retry_attempts:
            # 达到最大重试次数，标记为失败
            task.status = TaskStatus.FAILED
            print(f"❌ 任务最终失败: {task.task_id} - {error_message}")
            print(f"   已尝试 {task.attempt_count} 次")
            task.cleanup()
            self._save_state()
            
            # 调用失败回调
            if self.failure_callback:
                try:
                    self.failure_callback(task.task_id, f"重试{task.attempt_count}次后失败: {error_message}")
                except Exception as e:
                    print(f"⚠️  失败回调异常: {e}")
        else:
            # 计算下次重试时间（指数退避）
            delay = self.base_delay * (2 ** (task.attempt_count - 1))
            task.next_retry_time = time.time() + delay
            task.status = TaskStatus.RETRY_WAITING
            
            # 添加到重试队列
            with self.lock:
                self.retry_tasks[task.task_id] = task
            
            print(f"⏰ 任务安排重试: {task.task_id} ({task.fingerprint})")
            print(f"   失败原因: {error_message}")
            print(f"   {delay:.0f}秒后重试 ({self._format_time(task.next_retry_time)})")
        self._save_state()
    
    def _format_time(self, timestamp: float) -> str:
        """格式化时间显示"""
        import datetime
        return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

    def _get_next_task(self, timeout: float) -> RetryTask:
        """按优先级获取下一个任务"""
        try:
            return self.high_priority_tasks.get_nowait()
        except queue.Empty:
            pass

        return self.pending_tasks.get(timeout=timeout)

    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        with self.lock:
            pending_count = self.pending_tasks.qsize()
            high_priority_count = self.high_priority_tasks.qsize()
            retry_count = len(self.retry_tasks)
            active_task_id = self.active_task.task_id if self.active_task else None

        return {
            "running": self.running,
            "pending_count": pending_count,
            "high_priority_count": high_priority_count,
            "retry_count": retry_count,
            "active_task": active_task_id,
            "max_retry_attempts": self.max_retry_attempts,
            "base_delay": self.base_delay
        }
    
    def print_status(self):
        """打印状态信息"""
        status = self.get_status_summary()
        
        print(f"\n📊 重试管理器状态:")
        print(f"   运行状态: {'✅ 运行中' if status['running'] else '❌ 已停止'}")
        print(f"   待处理任务: {status['pending_count']}")
        print(f"   高优先级任务: {status['high_priority_count']}")
        print(f"   重试队列: {status['retry_count']}")
        print(f"   当前任务: {status['active_task'] or '无'}")
        
        # 显示重试任务详情
        if status['retry_count'] > 0:
            print(f"   重试任务详情:")
            with self.lock:
                for task_id, task in self.retry_tasks.items():
                    next_retry = self._format_time(task.next_retry_time) if task.next_retry_time else "未知"
                    print(f"     - {task_id}: {task.attempt_count}/{self.max_retry_attempts}次, 指纹 {task.fingerprint}, 下次重试: {next_retry}")
    
    def _save_state(self):
        """保存状态到文件"""
        if not self.persistence_enabled:
            return
        
        try:
            state_data = {
                "timestamp": time.time(),
                "retry_tasks": {}
            }
            
            # 只保存重试任务的元数据（不包含音频数据）
            with self.lock:
                for task_id, task in self.retry_tasks.items():
                    state_data["retry_tasks"][task_id] = task.to_dict()
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️  保存重试状态失败: {e}")
    
    def _load_state(self):
        """从文件加载状态"""
        if not self.persistence_enabled or not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)

            restored = 0
            for task_id, payload in state_data.get("retry_tasks", {}).items():
                audio_path = Path(payload.get("audio_path", ""))
                if not audio_path.exists():
                    print(f"⚠️  历史重试任务 {task_id} 的音频文件缺失，已跳过")
                    continue

                try:
                    status = TaskStatus(payload.get("status", TaskStatus.PENDING.value))
                except ValueError:
                    status = TaskStatus.PENDING

                task = RetryTask(
                    task_id=task_id,
                    audio_path=audio_path,
                    created_time=payload.get("created_time", time.time()),
                    fingerprint=payload.get("fingerprint", "unknown"),
                    attempt_count=payload.get("attempt_count", 0),
                    last_attempt_time=payload.get("last_attempt_time"),
                    next_retry_time=payload.get("next_retry_time"),
                    status=status,
                    error_message=payload.get("error_message"),
                    metadata=payload.get("metadata"),
                )

                if status == TaskStatus.RETRY_WAITING:
                    with self.lock:
                        self.retry_tasks[task_id] = task
                else:
                    task.status = TaskStatus.PENDING
                    self.pending_tasks.put(task)
                restored += 1

            if restored:
                print(f"📂 已恢复 {restored} 个重试任务")

        except Exception as e:
            print(f"⚠️  加载重试状态失败: {e}")
    
    def clear_failed_tasks(self):
        """清理失败的任务"""
        with self.lock:
            failed_tasks = [tid for tid, task in self.retry_tasks.items() 
                          if task.status in [TaskStatus.FAILED, TaskStatus.CANCELLED]]
        
        for task_id in failed_tasks:
            with self.lock:
                task = self.retry_tasks.pop(task_id, None)
            if task:
                task.cleanup()
        
        if failed_tasks:
            print(f"🧹 已清理 {len(failed_tasks)} 个失败/取消的任务")
        
        self._save_state()


# 全局实例
audio_retry_manager = AudioRetryManager()
