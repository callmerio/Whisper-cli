#!/usr/bin/env python3
"""
语音活动检测器 (Voice Activity Detector)
用于实时检测用户语音活动，支持智能分段和可配置的静音检测
"""

import time
import threading
import queue
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import numpy as np

import config


class VoiceActivityState(Enum):
    """语音活动状态"""
    SILENT = "静音"
    SPEAKING = "说话中"
    PAUSED = "暂停"


@dataclass
class VoiceSegment:
    """语音段数据结构"""
    start_time: float  # 开始时间
    end_time: float    # 结束时间
    audio_data: np.ndarray  # 音频数据
    duration: float    # 时长（秒）
    segment_id: str    # 段落ID
    
    @property
    def duration_ms(self) -> int:
        """时长（毫秒）"""
        return int(self.duration * 1000)


class VoiceActivityDetector:
    """语音活动检测器"""
    
    def __init__(self):
        """初始化VAD"""
        # 配置参数
        self.volume_threshold = config.VAD_VOLUME_THRESHOLD  # 音量阈值
        self.silence_duration = config.VAD_SILENCE_DURATION  # 静音时长（秒）
        self.min_segment_duration = config.VAD_MIN_SEGMENT_DURATION  # 最小段落时长
        self.sample_rate = config.SAMPLE_RATE
        self.analysis_window = config.VAD_ANALYSIS_WINDOW  # 分析窗口（秒）
        
        # 状态管理
        self.current_state = VoiceActivityState.SILENT
        self.last_voice_time = None
        self.current_segment_start = None
        self.segment_audio_buffer = []
        self.segment_counter = 0
        
        # 线程控制
        self.running = False
        self.audio_queue = queue.Queue()
        self.processing_thread = None
        self.lock = threading.Lock()
        
        # 回调函数
        self.on_segment_complete: Optional[Callable[[VoiceSegment], None]] = None
        self.on_voice_start: Optional[Callable[[], None]] = None
        self.on_voice_stop: Optional[Callable[[], None]] = None
        self.on_state_change: Optional[Callable[[VoiceActivityState], None]] = None
        
        print(f"🎯 语音活动检测器初始化完成")
        print(f"   音量阈值: {self.volume_threshold}")
        print(f"   静音检测: {self.silence_duration}秒")
        print(f"   最小段落: {self.min_segment_duration}秒")
    
    def set_callbacks(self, 
                     on_segment_complete: Optional[Callable[[VoiceSegment], None]] = None,
                     on_voice_start: Optional[Callable[[], None]] = None,
                     on_voice_stop: Optional[Callable[[], None]] = None,
                     on_state_change: Optional[Callable[[VoiceActivityState], None]] = None):
        """设置回调函数"""
        self.on_segment_complete = on_segment_complete
        self.on_voice_start = on_voice_start
        self.on_voice_stop = on_voice_stop
        self.on_state_change = on_state_change
    
    def update_config(self, silence_duration: Optional[float] = None,
                     volume_threshold: Optional[float] = None,
                     min_segment_duration: Optional[float] = None):
        """更新配置参数"""
        with self.lock:
            if silence_duration is not None:
                self.silence_duration = silence_duration
                print(f"🔧 更新静音检测时长: {silence_duration}秒")
            
            if volume_threshold is not None:
                self.volume_threshold = volume_threshold
                print(f"🔧 更新音量阈值: {volume_threshold}")
            
            if min_segment_duration is not None:
                self.min_segment_duration = min_segment_duration
                print(f"🔧 更新最小段落时长: {min_segment_duration}秒")
    
    def start(self) -> bool:
        """启动VAD"""
        if self.running:
            return True
        
        self.running = True
        self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
        self.processing_thread.start()
        
        print("🚀 语音活动检测器已启动")
        return True
    
    def stop(self):
        """停止VAD"""
        if not self.running:
            return
        
        self.running = False
        
        # 处理最后一个段落（如果有）
        self._finalize_current_segment()
        
        # 等待处理线程结束
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        print("⏹️ 语音活动检测器已停止")
    
    def feed_audio(self, audio_data: np.ndarray, timestamp: Optional[float] = None):
        """输入音频数据进行分析"""
        if not self.running:
            return
        
        if timestamp is None:
            timestamp = time.time()
        
        # 将音频数据放入队列
        try:
            self.audio_queue.put((audio_data, timestamp), timeout=0.1)
        except queue.Full:
            # 队列满了，丢弃旧数据
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put((audio_data, timestamp), timeout=0.1)
            except (queue.Empty, queue.Full):
                pass
    
    def _processing_worker(self):
        """音频处理工作线程"""
        print("🔄 VAD处理线程已启动")
        
        while self.running:
            try:
                # 获取音频数据
                audio_data, timestamp = self.audio_queue.get(timeout=0.5)
                
                # 分析音频
                self._analyze_audio_chunk(audio_data, timestamp)
                
                # 每次处理完音频后都检查静音超时，确保及时检测到静音
                self._check_silence_timeout()
                
            except queue.Empty:
                # 超时，检查是否需要处理静音
                self._check_silence_timeout()
                continue
            except Exception as e:
                if config.DEBUG_MODE:
                    print(f"⚠️ VAD处理异常: {e}")
        
        print("🔄 VAD处理线程已结束")
    
    def _analyze_audio_chunk(self, audio_data: np.ndarray, timestamp: float):
        """分析音频数据块"""
        # 计算音频能量/音量
        if len(audio_data) == 0:
            return
        
        # 确保音频数据是正确的格式
        if audio_data.dtype == np.float32:
            # 如果已经是float32，假设范围是-1到1
            audio_float = audio_data
        else:
            # 转换为float32，假设是16位整数
            audio_float = audio_data.astype(np.float32) / 32768.0
        
        # 计算RMS音量
        rms_volume = np.sqrt(np.mean(audio_float ** 2))
        
        # 判断是否有语音活动
        has_voice = rms_volume > self.volume_threshold
        
        with self.lock:
            previous_state = self.current_state
            
            if has_voice:
                # 检测到语音
                self.last_voice_time = timestamp
                
                if self.current_state == VoiceActivityState.SILENT:
                    # 从静音转为说话
                    self._start_new_segment(timestamp)
                    self.current_state = VoiceActivityState.SPEAKING
                    
                    if self.on_voice_start:
                        try:
                            self.on_voice_start(timestamp)
                        except Exception as e:
                            if config.DEBUG_MODE:
                                print(f"⚠️ 语音开始回调异常: {e}")
                
                elif self.current_state == VoiceActivityState.PAUSED:
                    # 从暂停恢复说话
                    self.current_state = VoiceActivityState.SPEAKING
                
                # 将音频数据添加到当前段落
                self.segment_audio_buffer.append(audio_data)
            
            else:
                # 没有检测到语音
                if self.current_state == VoiceActivityState.SPEAKING:
                    # 从说话转为暂停
                    self.current_state = VoiceActivityState.PAUSED
                
                # 即使是静音，也要将音频数据添加到当前段落（保持音频连续性）
                if self.current_state in [VoiceActivityState.SPEAKING, VoiceActivityState.PAUSED]:
                    self.segment_audio_buffer.append(audio_data)
            
            # 检查状态变化
            if previous_state != self.current_state:
                if self.on_state_change:
                    try:
                        self.on_state_change(previous_state, self.current_state)
                    except Exception as e:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 状态变化回调异常: {e}")
    
    def _check_silence_timeout(self):
        """检查静音超时"""
        if not self.last_voice_time:
            return
        
        current_time = time.time()
        silence_time = current_time - self.last_voice_time
        
        with self.lock:
            if (self.current_state in [VoiceActivityState.SPEAKING, VoiceActivityState.PAUSED] and
                silence_time >= self.silence_duration):
                
                # 静音超时，完成当前段落
                self._finalize_current_segment()
                self.current_state = VoiceActivityState.SILENT
                
                if self.on_voice_stop:
                    try:
                        self.on_voice_stop(current_time)
                    except Exception as e:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 语音停止回调异常: {e}")
    
    def _start_new_segment(self, timestamp: float):
        """开始新的语音段落"""
        self.current_segment_start = timestamp
        self.segment_audio_buffer = []
        self.segment_counter += 1
    
    def _finalize_current_segment(self):
        """完成当前语音段落"""
        if not self.current_segment_start or not self.segment_audio_buffer:
            return
        
        current_time = time.time()
        duration = current_time - self.current_segment_start
        
        # 检查段落长度
        if duration < self.min_segment_duration:
            self._reset_segment()
            return
        
        # 合并音频数据
        if self.segment_audio_buffer:
            combined_audio = np.concatenate(self.segment_audio_buffer)
        else:
            combined_audio = np.array([], dtype=np.int16)
        
        # 创建语音段落对象
        segment = VoiceSegment(
            start_time=self.current_segment_start,
            end_time=current_time,
            audio_data=combined_audio,
            duration=duration,
            segment_id=f"segment_{self.segment_counter}_{int(self.current_segment_start * 1000)}"
        )
        
        print(f"✅ 完成段落: {segment.segment_id} ({duration:.1f}s, {len(combined_audio)} 采样点)")
        
        # 调用回调函数
        if self.on_segment_complete:
            try:
                self.on_segment_complete(segment)
            except Exception as e:
                print(f"❌ 段落完成回调异常: {e}")
                if config.DEBUG_MODE:
                    import traceback
                    traceback.print_exc()
        
        # 重置段落状态
        self._reset_segment()
    
    def _reset_segment(self):
        """重置段落状态"""
        self.current_segment_start = None
        self.segment_audio_buffer = []
    
    def get_current_state(self) -> VoiceActivityState:
        """获取当前状态"""
        return self.current_state
    
    def get_current_silence_duration(self) -> float:
        """获取当前静音时长"""
        if not self.last_voice_time:
            return 0.0
        
        return time.time() - self.last_voice_time
    
    def force_segment_complete(self):
        """强制完成当前段落"""
        with self.lock:
            if self.current_state in [VoiceActivityState.SPEAKING, VoiceActivityState.PAUSED]:
                self._finalize_current_segment()
                self.current_state = VoiceActivityState.SILENT
                
                if self.on_voice_stop:
                    try:
                        current_time = time.time()
                        self.on_voice_stop(current_time)
                    except Exception as e:
                        if config.DEBUG_MODE:
                            print(f"⚠️ 强制停止回调异常: {e}")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "current_state": self.current_state.value,
            "segment_count": self.segment_counter,
            "current_silence_duration": self.get_current_silence_duration(),
            "config": {
                "volume_threshold": self.volume_threshold,
                "silence_duration": self.silence_duration,
                "min_segment_duration": self.min_segment_duration
            }
        }


def test_vad():
    """测试VAD功能"""
    print("🧪 测试语音活动检测器...")
    
    def on_segment(segment: VoiceSegment):
        print(f"📝 段落完成: {segment.segment_id}, 时长: {segment.duration:.1f}s")
    
    def on_voice_start():
        print("🎤 开始说话")
    
    def on_voice_stop():
        print("⏹️ 停止说话")
    
    def on_state_change(state: VoiceActivityState):
        print(f"🔄 状态变化: {state.value}")
    
    vad = VoiceActivityDetector()
    vad.set_callbacks(
        on_segment_complete=on_segment,
        on_voice_start=on_voice_start,
        on_voice_stop=on_voice_stop,
        on_state_change=on_state_change
    )
    
    vad.start()
    
    # 模拟音频输入
    try:
        for i in range(100):
            # 生成模拟音频（有/无语音）
            if 20 <= i <= 40 or 60 <= i <= 80:
                # 模拟有语音的音频
                audio = np.random.normal(0, 0.1, 1600).astype(np.int16)  # 0.1秒的音频
            else:
                # 模拟静音
                audio = np.random.normal(0, 0.005, 1600).astype(np.int16)
            
            vad.feed_audio(audio)
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        vad.stop()
        print("✅ VAD测试完成")


if __name__ == "__main__":
    test_vad()