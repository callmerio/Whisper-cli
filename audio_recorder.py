#!/usr/bin/env python3
"""
音频录制模块
使用 sounddevice 进行实时音频录制和缓冲管理
"""

import sounddevice as sd
import numpy as np
import threading
import time
import queue
from typing import Optional, List, Callable
from pathlib import Path
import config

class AudioRecorder:
    def __init__(self):
        """初始化音频录制器"""
        self.sample_rate = config.SAMPLE_RATE
        self.channels = config.CHANNELS
        self.chunk_duration = config.CHUNK_DURATION
        self.buffer_duration = config.BUFFER_DURATION
        
        # 计算每次录制的帧数
        self.frames_per_chunk = int(self.sample_rate * self.chunk_duration)
        self.frames_per_buffer = int(self.sample_rate * self.buffer_duration)
        
        # 音频缓冲区 - 改用动态列表存储完整录音
        self.audio_chunks = []  # 存储所有音频块
        self.total_frames = 0   # 总帧数
        
        # 音频队列用于分段处理
        self.audio_queue = queue.Queue()
        
        # 录制状态
        self.is_recording = False
        self.stream = None
        self.recording_thread = None
        
        # 回调函数
        self.chunk_callback: Optional[Callable[[np.ndarray], None]] = None
        
        # 锁
        self.buffer_lock = threading.Lock()
        
        print(f"音频录制器初始化:")
        print(f"  采样率: {self.sample_rate} Hz")
        print(f"  通道数: {self.channels}")
        print(f"  分段时长: {self.chunk_duration} 秒")
        print(f"  缓冲区时长: {self.buffer_duration} 秒")
    
    def _audio_callback(self, indata, frames, time, status):
        """音频流回调函数"""
        if status:
            print(f"音频流状态: {status}")
        
        # 将音频数据添加到动态缓冲区
        with self.buffer_lock:
            audio_data = indata[:, 0] if self.channels == 1 else indata
            # 直接添加到音频块列表，不限制长度
            self.audio_chunks.append(audio_data.copy())
            self.total_frames += len(audio_data)
    
    def _processing_thread(self):
        """音频处理线程，定期提取分段进行转录"""
        last_chunk_time = time.time()
        
        while self.is_recording:
            current_time = time.time()
            
            # 检查是否应该处理新的音频分段（简化版本，不再使用实时分段）
            if current_time - last_chunk_time >= self.chunk_duration:
                with self.buffer_lock:
                    if self.audio_chunks:
                        # 获取最近的音频数据用于实时显示（可选）
                        recent_chunk = self.audio_chunks[-1] if self.audio_chunks else None
                        
                        if recent_chunk is not None and self.chunk_callback:
                            try:
                                self.chunk_callback(recent_chunk)
                            except Exception as e:
                                print(f"音频分段回调错误: {e}")
                        
                        last_chunk_time = current_time
            
            # 短暂休眠以减少 CPU 使用
            time.sleep(0.1)
    
    def start_recording(self, chunk_callback: Optional[Callable[[np.ndarray], None]] = None):
        """开始录制音频"""
        if self.is_recording:
            print("录制已在进行中")
            return False
        
        self.chunk_callback = chunk_callback
        
        try:
            # 重置缓冲区
            with self.buffer_lock:
                self.audio_chunks.clear()
                self.total_frames = 0
            
            # 清空队列
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 创建音频流
            self.stream = sd.InputStream(
                channels=self.channels,
                samplerate=self.sample_rate,
                callback=self._audio_callback,
                blocksize=1024,  # 较小的块大小以减少延迟
                dtype=np.float32
            )
            
            # 启动录制
            self.stream.start()
            self.is_recording = True
            
            # 启动处理线程
            self.recording_thread = threading.Thread(target=self._processing_thread, daemon=True)
            self.recording_thread.start()
            
            print("🎤 开始录音...")
            return True
            
        except Exception as e:
            print(f"启动录制失败: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """停止录制并返回完整的音频数据"""
        if not self.is_recording:
            print("当前未在录制")
            return None
        
        print("⏹️  停止录音...")
        
        # 停止录制
        self.is_recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # 等待处理线程结束
        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)
            self.recording_thread = None
        
        # 获取完整的音频数据
        with self.buffer_lock:
            if self.audio_chunks:
                # 合并所有音频块
                complete_audio = np.concatenate(self.audio_chunks)
                print(f"录制完成，音频长度: {len(complete_audio) / self.sample_rate:.2f} 秒")
                print(f"总块数: {len(self.audio_chunks)}, 总帧数: {self.total_frames}")
                return complete_audio
            else:
                print("未录制到有效音频数据")
                return None
    
    def get_audio_chunks(self) -> List[np.ndarray]:
        """获取所有待处理的音频分段"""
        chunks = []
        while not self.audio_queue.empty():
            try:
                chunk = self.audio_queue.get_nowait()
                chunks.append(chunk)
            except queue.Empty:
                break
        return chunks
    
    def save_audio_to_file(self, audio_data: np.ndarray, filename: str):
        """保存音频数据到文件（调试用）"""
        if config.LOG_AUDIO_FILES:
            try:
                import soundfile as sf
                filepath = Path(config.PROJECT_ROOT) / filename
                sf.write(filepath, audio_data, self.sample_rate)
                print(f"音频已保存到: {filepath}")
            except ImportError:
                print("需要安装 soundfile 库来保存音频文件")
            except Exception as e:
                print(f"保存音频文件失败: {e}")
    
    def get_device_info(self):
        """获取音频设备信息"""
        try:
            devices = sd.query_devices()
            default_device = sd.default.device
            
            print(f"默认输入设备: {default_device}")
            print("可用音频设备:")
            for i, device in enumerate(devices):
                device_type = "输入" if device['max_input_channels'] > 0 else ""
                device_type += "输出" if device['max_output_channels'] > 0 else ""
                print(f"  {i}: {device['name']} ({device_type})")
                
        except Exception as e:
            print(f"获取设备信息失败: {e}")

# 测试代码
if __name__ == "__main__":
    import sys
    
    def on_audio_chunk(chunk):
        rms = np.sqrt(np.mean(chunk**2))
        print(f"音频分段 RMS: {rms:.4f}")
    
    recorder = AudioRecorder()
    recorder.get_device_info()
    
    try:
        print("按 Enter 开始录制...")
        input()
        
        recorder.start_recording(on_audio_chunk)
        
        print("录制中... 按 Enter 停止")
        input()
        
        final_audio = recorder.stop_recording()
        
        if final_audio is not None:
            # 保存测试音频
            recorder.save_audio_to_file(final_audio, "test_recording.wav")
        
    except KeyboardInterrupt:
        print("\n测试被中断")
        recorder.stop_recording()
    
    print("测试完成")