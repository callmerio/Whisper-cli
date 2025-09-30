#!/usr/bin/env python3
"""
音频录制模块
采用临时文件落盘与块队列，兼顾内存占用与实时分段需求
"""

import os
import queue
import tempfile
import wave
from pathlib import Path
from typing import Optional, Callable
import threading

import numpy as np
import sounddevice as sd

import config


class AudioRecorder:
    def __init__(self):
        """初始化音频录制器"""
        self.sample_rate = config.SAMPLE_RATE
        self.channels = config.CHANNELS
        self.chunk_duration = config.CHUNK_DURATION
        self.buffer_duration = config.BUFFER_DURATION

        self.frames_per_chunk = max(1, int(self.sample_rate * self.chunk_duration))

        # 录制状态
        self.is_recording = False
        self.stream = None
        self.chunk_callback: Optional[Callable[[np.ndarray], None]] = None

        # 临时文件写入
        self._temp_file_path: Optional[Path] = None
        self._wave_writer: Optional[wave.Wave_write] = None
        self._write_lock = threading.Lock()

        # 队列用于实时模式消费音频块
        max_queue = max(1, int(self.buffer_duration / max(self.chunk_duration, 0.01)) + 2)
        self.chunk_queue: queue.Queue = queue.Queue(max_queue)

        # 统计数据
        self.total_frames = 0
        self.chunk_counter = 0
        self._last_total_frames = 0
        self._last_chunk_count = 0

        print("音频录制器初始化:")
        print(f"  采样率: {self.sample_rate} Hz")
        print(f"  通道数: {self.channels}")
        print(f"  分段时长: {self.chunk_duration} 秒")
        print(f"  缓冲区时长: {self.buffer_duration} 秒")

    def _allocate_writer(self) -> None:
        temp_root = Path(config.PROJECT_ROOT) / "logs" / "recordings"
        temp_root.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            prefix="session_",
            suffix=".wav",
            delete=False,
            dir=str(temp_root),
        )
        self._temp_file_path = Path(handle.name)
        handle.close()

        writer = wave.open(str(self._temp_file_path), "wb")
        writer.setnchannels(self.channels)
        writer.setsampwidth(2)
        writer.setframerate(self.sample_rate)
        self._wave_writer = writer
        self.total_frames = 0
        self.chunk_counter = 0

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"音频流状态: {status}")

        float_chunk = indata.copy()
        if self.channels == 1:
            float_payload = float_chunk[:, 0]
        else:
            float_payload = float_chunk

        if self.chunk_callback:
            try:
                self.chunk_callback(float_payload.copy())
            except Exception as exc:
                print(f"音频分段回调错误: {exc}")

        try:
            self.chunk_queue.put_nowait(float_payload.copy())
        except queue.Full:
            try:
                self.chunk_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.chunk_queue.put_nowait(float_payload.copy())
            except queue.Full:
                pass

        int_chunk = np.clip(float_payload, -1.0, 1.0)
        int_chunk = (int_chunk * 32767).astype(np.int16)

        if self.channels > 1 and int_chunk.ndim == 1:
            int_chunk = int_chunk.reshape(-1, self.channels)

        with self._write_lock:
            if self._wave_writer:
                self._wave_writer.writeframes(int_chunk.tobytes())
                self.total_frames += len(int_chunk)
        self.chunk_counter += 1

    def start_recording(self, chunk_callback: Optional[Callable[[np.ndarray], None]] = None) -> bool:
        """开始录制音频"""
        if self.is_recording:
            print("录制已在进行中")
            return False

        self.chunk_callback = chunk_callback

        while not self.chunk_queue.empty():
            try:
                self.chunk_queue.get_nowait()
            except queue.Empty:
                break

        try:
            self._allocate_writer()
        except Exception as exc:
            print(f"创建临时录音文件失败: {exc}")
            return False

        try:
            self.stream = sd.InputStream(
                channels=self.channels,
                samplerate=self.sample_rate,
                callback=self._audio_callback,
                blocksize=1024,
                dtype=np.float32,
            )
            self.stream.start()
            self.is_recording = True
            print("🎤 开始录音...")
            return True
        except Exception as exc:
            print(f"启动录制失败: {exc}")
            self.is_recording = False
            with self._write_lock:
                if self._wave_writer:
                    self._wave_writer.close()
                self._wave_writer = None
            if self._temp_file_path and self._temp_file_path.exists():
                self._temp_file_path.unlink(missing_ok=True)  # type: ignore[arg-type]
            self._temp_file_path = None
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """停止录制并返回完整的音频数据"""
        if not self.is_recording:
            print("当前未在录制")
            return None

        print("⏹️  停止录音...")
        self.is_recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        with self._write_lock:
            if self._wave_writer:
                self._wave_writer.close()
            self._wave_writer = None

        temp_path = self._temp_file_path
        self._temp_file_path = None

        if not temp_path or not temp_path.exists():
            print("未录制到有效音频数据")
            return None

        try:
            with wave.open(str(temp_path), "rb") as reader:
                frame_count = reader.getnframes()
                raw = reader.readframes(frame_count)

            audio_int16 = np.frombuffer(raw, dtype=np.int16)
            if self.channels > 1:
                audio_int16 = audio_int16.reshape(-1, self.channels)
            audio_float = audio_int16.astype(np.float32) / 32767.0
            if self.channels == 1:
                audio_float = audio_float.reshape(-1)

            duration = len(audio_float) / float(self.sample_rate)
            print(f"录制完成，音频长度: {duration:.2f} 秒")
            print(f"总帧数: {len(audio_float)}")

            self._last_total_frames = len(audio_float)
            self._last_chunk_count = self.chunk_counter

            if not config.LOG_AUDIO_FILES:
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            else:
                print(f"📁 录音文件保存在: {temp_path}")

            return audio_float
        finally:
            self.total_frames = 0
            self.chunk_counter = 0

    def get_latest_audio_chunk(self) -> Optional[np.ndarray]:
        """获取最新音频块供 VAD 消费"""
        try:
            return self.chunk_queue.get_nowait()
        except queue.Empty:
            return None

    def get_recording_stats(self) -> dict:
        """返回最近一次录音的统计信息"""
        duration_seconds = 0.0
        if self.sample_rate:
            duration_seconds = self._last_total_frames / float(self.sample_rate)
        return {
            "total_frames": self._last_total_frames,
            "duration_seconds": duration_seconds,
            "chunk_count": self._last_chunk_count,
        }

    def save_audio_to_file(self, audio_data: np.ndarray, filename: str):
        """保存音频数据到文件（调试用）"""
        if not audio_data.size:
            return

        target = Path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as writer:
            writer.setnchannels(self.channels)
            writer.setsampwidth(2)
            writer.setframerate(self.sample_rate)
            data = np.clip(audio_data, -1.0, 1.0)
            data = (data * 32767).astype(np.int16)
            writer.writeframes(data.tobytes())
        print(f"💾 调试录音已保存: {target}")

    # 兼容旧启动流程：打印/返回设备信息
    def get_device_info(self) -> dict:
        """打印并返回当前输入设备的关键信息（采样率/通道/名称）。"""
        info = {
            "configured_samplerate": self.sample_rate,
            "configured_channels": self.channels,
        }
        try:
            default_in, default_out = sd.default.device
            query_target = default_in if isinstance(default_in, (int, str)) else None
            device_info = sd.query_devices(query_target, "input")
            if isinstance(device_info, list):
                # 回退到第一个输入设备，通常包含默认设备信息
                device_info = device_info[0]
            resolved_index = device_info.get("index")
            if isinstance(resolved_index, int):
                default_in = resolved_index
            hostapi_name = ""
            hostapi_index = device_info.get("hostapi")
            if isinstance(hostapi_index, int):
                hostapis = sd.query_hostapis()
                if 0 <= hostapi_index < len(hostapis):
                    hostapi_name = hostapis[hostapi_index]["name"]

            info.update(
                {
                    "default_input_index": default_in,
                    "default_output_index": default_out,
                    "input_name": device_info.get("name"),
                    "default_samplerate": device_info.get("default_samplerate"),
                    "max_input_channels": device_info.get("max_input_channels"),
                    "hostapi": hostapi_name,
                }
            )

            print("\n🎧 音频设备信息：")
            print(
                f"  输入设备: {device_info.get('name')} (index={default_in})"
            )
            if hostapi_name:
                print(f"  Host API: {hostapi_name}")
            print(
                "  设备默认采样率: "
                f"{device_info.get('default_samplerate')} Hz, 最大输入通道: {device_info.get('max_input_channels')}"
            )
            print(
                f"  当前配置: {self.sample_rate} Hz / {self.channels} ch"
            )
        except Exception as exc:
            print(f"⚠️ 获取音频设备信息失败: {exc}")
        return info


if __name__ == "__main__":
    recorder = AudioRecorder()
    if recorder.start_recording():
        try:
            print("录音中，按 Ctrl+C 停止...")
            while recorder.is_recording:
                pass
        except KeyboardInterrupt:
            pass
        finally:
            final_audio = recorder.stop_recording()
            if final_audio is not None:
                recorder.save_audio_to_file(final_audio, "test_recording.wav")
