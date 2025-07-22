#!/usr/bin/env python3
"""
语音转录模块
使用 whisper.cpp 进行语音识别转录
"""

import subprocess
import tempfile
import numpy as np
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import config

class WhisperTranscriber:
    def __init__(self):
        """初始化 Whisper 转录器"""
        # 使用自定义模型路径或默认路径
        if hasattr(config, 'WHISPER_MODEL_PATH') and Path(config.WHISPER_MODEL_PATH).exists():
            self.model_path = Path(config.WHISPER_MODEL_PATH)
        else:
            self.model_path = Path(config.PROJECT_ROOT) / "models" / f"ggml-{config.WHISPER_MODEL}.bin"
        
        self.whisper_executable = self._find_whisper_executable()
        self.is_ready = False
        
        # 简化版本，移除实时处理相关组件
        
        self._initialize()
    
    def _find_whisper_executable(self) -> Optional[str]:
        """查找 whisper.cpp 可执行文件"""
        possible_paths = [
            "/opt/homebrew/bin/whisper-cli",  # 新的可执行文件名
            "/opt/homebrew/bin/whisper-cpp",
            "/usr/local/bin/whisper-cli",
            "/usr/local/bin/whisper-cpp",
            "/opt/homebrew/bin/main",
            "/usr/local/bin/main",
            "whisper-cli",
            "whisper-cpp",
            "main"
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "--help"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 or "whisper" in result.stderr.lower():
                    print(f"找到 whisper.cpp: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        print("未找到 whisper.cpp 可执行文件")
        return None
    
    def _initialize(self):
        """初始化转录器"""
        if not self.whisper_executable:
            print("❌ Whisper 可执行文件未找到")
            return
        
        if not self.model_path.exists():
            print(f"❌ 模型文件未找到: {self.model_path}")
            print("请确保模型文件已下载到 models/ 目录")
            return
        
        # 测试 whisper.cpp
        try:
            cmd = [
                self.whisper_executable,
                "--version"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            print(f"✅ Whisper.cpp 初始化成功")
            print(f"   模型: {config.WHISPER_MODEL}")
            print(f"   语言: {config.WHISPER_LANGUAGE}")
            self.is_ready = True
            
        except Exception as e:
            print(f"❌ Whisper 初始化失败: {e}")
    
    def _save_audio_to_temp_wav(self, audio_data: np.ndarray) -> Optional[str]:
        """将音频数据保存为临时 WAV 文件"""
        try:
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # 使用 soundfile 保存（如果有的话）
            try:
                import soundfile as sf
                sf.write(temp_path, audio_data, config.SAMPLE_RATE)
                return temp_path
            except ImportError:
                pass
            
            # 使用 scipy 保存
            try:
                from scipy.io import wavfile
                # 转换到 16-bit PCM
                audio_int16 = (audio_data * 32767).astype(np.int16)
                wavfile.write(temp_path, config.SAMPLE_RATE, audio_int16)
                return temp_path
            except ImportError:
                pass
            
            # 手动写入 WAV 文件头
            import struct
            import wave
            
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(config.SAMPLE_RATE)
                
                # 转换为 16-bit PCM
                audio_int16 = (audio_data * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            
            return temp_path
            
        except Exception as e:
            print(f"保存临时音频文件失败: {e}")
            return None
    
    def _transcribe_audio_file(self, audio_file: str) -> Optional[List[Dict[str, Any]]]:
        """使用 whisper.cpp 转录音频文件"""
        try:
            cmd = [
                self.whisper_executable,
                "-m", str(self.model_path),
                "-f", audio_file,
                "-l", config.WHISPER_LANGUAGE,  # 明确指定语言为中文
                "-t", str(config.WHISPER_THREADS),
                "--output-txt",  # 输出纯文本
                "--no-timestamps",  # 不输出时间戳
            ]
            
            if config.DEBUG_MODE:
                print(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print(f"Whisper 转录失败: {result.stderr}")
                return None
            
            # 解析输出
            output_text = result.stdout.strip()
            if not output_text:
                if config.DEBUG_MODE:
                    print("Whisper 输出为空")
                return None
            
            # 简单解析文本输出
            transcript = [{
                'start': 0.0,
                'duration': 2.0,  # 默认持续时间
                'text': output_text
            }]
            
            if config.DEBUG_MODE:
                print(f"转录结果: {output_text}")
            
            return transcript
            
        except subprocess.TimeoutExpired:
            print("Whisper 转录超时")
            return None
        except Exception as e:
            print(f"Whisper 转录错误: {e}")
            return None
    
    def stop_processing(self):
        """停止转录处理（简化版，无实际处理）"""
        pass
    
    def transcribe_complete_audio(self, audio_data: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """转录完整的音频数据（同步方法）"""
        if not self.is_ready:
            print("转录器未准备就绪")
            return None
        
        temp_path = self._save_audio_to_temp_wav(audio_data)
        if not temp_path:
            return None
        
        try:
            transcript = self._transcribe_audio_file(temp_path)
            return transcript
        finally:
            # 删除临时文件
            try:
                Path(temp_path).unlink()
            except:
                pass
    
    def get_available_models(self):
        """获取可用的模型列表"""
        models_dir = Path(config.PROJECT_ROOT) / "models"
        if not models_dir.exists():
            return []
        
        models = []
        for model_file in models_dir.glob("ggml-*.bin"):
            model_name = model_file.stem.replace("ggml-", "")
            models.append(model_name)
        
        return models

# 测试代码
if __name__ == "__main__":
    def on_partial(text):
        print(f"部分结果: {text}")
    
    def on_complete(transcript):
        print(f"完整结果: {transcript}")
    
    transcriber = WhisperTranscriber()
    
    if transcriber.is_ready:
        print("可用模型:", transcriber.get_available_models())
        
        # 生成测试音频（1秒的正弦波）
        test_audio = np.sin(2 * np.pi * 440 * np.linspace(0, 1, config.SAMPLE_RATE)).astype(np.float32)
        
        print("测试转录功能...")
        result = transcriber.transcribe_complete_audio(test_audio)
        print(f"测试结果: {result}")
    else:
        print("转录器未准备就绪，请检查配置")