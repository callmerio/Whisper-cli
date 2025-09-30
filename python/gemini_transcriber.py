#!/usr/bin/env python3
"""
Gemini 音频转录器
使用 Gemini-2.5-Flash 模型进行音频转录，基于已有的纠错器实现
"""

import concurrent.futures
import hashlib
import io
import json
import os
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-genai 未安装，请运行: uv add google-genai")

import config


class GeminiTranscriber:
    """Gemini 音频转录器 - 基于纠错器的实现"""
    
    def __init__(self):
        """初始化 Gemini 转录器"""
        self.api_key = config.GEMINI_TRANSCRIPTION_API_KEY
        self.model = config.GEMINI_TRANSCRIPTION_MODEL  # 使用配置中的模型
        self.is_ready = False
        self.last_run_info: Dict[str, Any] = {}
        self._prompt_cache: Optional[str] = None
        self._prompt_cache_mtime: Optional[Tuple[float, float]] = None
        
        if not GEMINI_AVAILABLE:
            print("❌ Google Gen AI SDK 未安装")
            return
        
        # 检查 API 密钥
        if not self.api_key:
            print("❌ 未找到 GEMINI_API_KEY 环境变量")
            return
        
        self.is_ready = bool(self.api_key)
        
        if self.is_ready:
            try:
                # 配置代理 - 使用环境变量方式 (照搬纠错器的实现)
                if config.USE_PROXY:
                    proxy_url = config.HTTPS_PROXY if config.HTTPS_PROXY else config.HTTP_PROXY
                    if proxy_url:
                        # 设置环境变量让底层库使用代理
                        os.environ['HTTP_PROXY'] = proxy_url
                        os.environ['HTTPS_PROXY'] = proxy_url
                        print(f"🌐 使用代理: {proxy_url}")
                
                # 创建Gemini客户端 (支持自定义BASE_URL)
                http_options = None
                if config.GEMINI_BASE_URL:
                    # 如果配置了自定义BASE_URL，使用它
                    from google.genai import types
                    http_options = types.HttpOptions(base_url=config.GEMINI_BASE_URL)
                    print(f"🔗 使用自定义BASE_URL: {config.GEMINI_BASE_URL}")
                
                self.client = genai.Client(api_key=self.api_key, http_options=http_options)
                
                print(f"✅ Gemini转录器已就绪 ({self.model})")
                if config.DEBUG_MODE and self.api_key:
                    digest = hashlib.sha256(self.api_key.encode()).hexdigest()[:12]
                    print(f"   API密钥指纹: {digest}")
                    
            except Exception as e:
                print(f"❌ Gemini转录器初始化失败: {e}")
                self.is_ready = False
        else:
            print("⚠️  Gemini API密钥未配置，转录功能不可用")
            print(f"   请在.env文件中设置 GEMINI_API_KEY")
    
    def transcribe_complete_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """
        转录完整音频 - 优化版本支持多种策略
        
        Args:
            audio_data: 音频数据 (numpy array)
            
        Returns:
            转录文本或 None
        """
        if not self.is_ready:
            print("❌ Gemini 转录器未准备就绪")
            return None
        
        if audio_data is None or len(audio_data) == 0:
            print("❌ 音频数据为空")
            return None
        
        audio_duration = len(audio_data) / config.SAMPLE_RATE
        self.last_run_info = {
            "audio_duration_s": audio_duration,
            "sample_count": len(audio_data),
            "model": self.model,
            "strategy": "single",
            "compressed_kb": None,
            "transcript_chars": 0,
            "api_attempts": 0,
            "payload_type": None,
            "chunks_total": 0,
            "chunks_success": 0,
        }
        print(f"📊 音频时长: {audio_duration:.1f}秒")

        # 根据音频长度选择处理策略
        if audio_duration <= 30:  # 短音频：直接处理
            return self._transcribe_single_audio(audio_data)
        elif audio_duration <= 120:  # 中等长度：压缩优化
            self.last_run_info["strategy"] = "compressed"
            return self._transcribe_compressed_audio(audio_data)
        else:  # 长音频：分片并行处理
            self.last_run_info["strategy"] = "chunked"
            return self._transcribe_chunked_audio(audio_data)
    
    def _transcribe_single_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """处理短音频（≤30秒）"""
        try:
            # 创建压缩的音频数据
            audio_bytes = self._create_compressed_audio_bytes(audio_data)
            if not audio_bytes:
                return None
            
            compressed_kb = len(audio_bytes) / 1024
            self.last_run_info["compressed_kb"] = compressed_kb
            self.last_run_info["payload_type"] = "single"
            print(f"📁 压缩音频大小: {compressed_kb:.1f}KB")

            # 直接调用API，无需临时文件
            prompt_text = self._build_prompt()

            transcript = self._call_gemini_audio_api_bytes(audio_bytes, prompt_text)

            if transcript:
                self.last_run_info["transcript_chars"] = len(transcript)
                print(f"✅ Gemini 转录完成: {len(transcript)} 字符")
                return transcript
            else:
                print("❌ Gemini 转录失败")
                return None
                
        except Exception as e:
            print(f"❌ Gemini 转录错误: {e}")
        
        return None
    
    def _transcribe_compressed_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """处理中等长度音频（30-120秒）- 使用音频压缩"""
        try:
            # 降采样以减少文件大小
            if config.SAMPLE_RATE > 16000:
                # 降采样到16kHz
                downsample_factor = config.SAMPLE_RATE // 16000
                if downsample_factor > 1:
                    audio_data = audio_data[::downsample_factor]
                    print(f"📉 降采样: {config.SAMPLE_RATE}Hz → 16000Hz")
            
            # 音量标准化
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = (audio_data / max_val * 0.9).astype(audio_data.dtype)
            
            # 创建压缩音频
            audio_bytes = self._create_compressed_audio_bytes(audio_data, sample_rate=16000)
            if not audio_bytes:
                return None
            
            compressed_kb = len(audio_bytes) / 1024
            self.last_run_info["compressed_kb"] = compressed_kb
            self.last_run_info["payload_type"] = "compressed"
            print(f"📁 压缩音频大小: {compressed_kb:.1f}KB")

            # 调用API
            prompt_text = self._build_prompt()

            transcript = self._call_gemini_audio_api_bytes(audio_bytes, prompt_text)

            if transcript:
                self.last_run_info["transcript_chars"] = len(transcript)
                print(f"✅ Gemini 转录完成: {len(transcript)} 字符")
                return transcript
            else:
                print("❌ Gemini 转录失败")
                return None
                
        except Exception as e:
            print(f"❌ Gemini 转录错误: {e}")
        
        return None
    
    def _transcribe_chunked_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """处理长音频（>120秒）- 分片并行处理"""
        try:
            chunk_size = 60 * config.SAMPLE_RATE  # 60秒分片
            chunks = []
            
            # 分片处理
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) > config.SAMPLE_RATE:  # 至少1秒
                    chunks.append((i // config.SAMPLE_RATE, chunk))
            
            self.last_run_info["chunks_total"] = len(chunks)
            print(f"📊 分片处理: {len(chunks)} 个片段")
            
            # 并行转录
            transcripts = []
            prompt_text = self._build_prompt()
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_chunk = {
                    executor.submit(self._transcribe_chunk, chunk_id, chunk_data, prompt_text): chunk_id 
                    for chunk_id, chunk_data in chunks
                }
                
                for future in concurrent.futures.as_completed(future_to_chunk):
                    chunk_id = future_to_chunk[future]
                    try:
                        result = future.result()
                        if result:
                            transcripts.append((chunk_id, result))
                    except Exception as e:
                        print(f"❌ 分片 {chunk_id} 转录失败: {e}")
            
            # 按顺序合并结果
            transcripts.sort(key=lambda x: x[0])
            final_transcript = ' '.join([t[1] for t in transcripts])
            
            if final_transcript:
                self.last_run_info["transcript_chars"] = len(final_transcript)
                self.last_run_info["chunks_success"] = len(transcripts)
                self.last_run_info["payload_type"] = "chunked"
                print(f"✅ 分片转录完成: {len(transcripts)}/{len(chunks)} 个片段成功")
                return final_transcript
            else:
                print("❌ 所有分片转录失败")
                return None
                
        except Exception as e:
            print(f"❌ 分片转录错误: {e}")
        
        return None
    
    def _transcribe_chunk(self, chunk_id: int, chunk_data: np.ndarray, prompt_text: Optional[str]) -> Optional[str]:
        """转录单个音频分片"""
        try:
            # 压缩分片
            audio_bytes = self._create_compressed_audio_bytes(chunk_data, sample_rate=16000)
            if not audio_bytes:
                return None
            
            # 调用API
            return self._call_gemini_audio_api_bytes(audio_bytes, prompt_text)
            
        except Exception as e:
            print(f"❌ 分片 {chunk_id} 处理失败: {e}")
            return None

    def check_health(self) -> Tuple[bool, str]:
        """检查 Gemini 接口是否可用"""
        if not self.is_ready:
            return False, "Gemini 转录器未初始化"

        if not hasattr(self, 'client'):
            return False, "Gemini 客户端未创建"

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="health check ping")]
                )
            ]
            config = types.GenerateContentConfig(
                response_mime_type="text/plain",
                temperature=0.0,
                max_output_tokens=8,
            )
            self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return True, ""
        except Exception as exc:
            return False, str(exc)
    
    def _call_gemini_audio_api_bytes(self, audio_bytes: bytes, prompt_text: Optional[str] = None) -> Optional[str]:
        """直接使用音频字节数据调用Gemini API"""
        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                print(f"🔄 API调用尝试 {attempt + 1}/{config.GEMINI_MAX_RETRIES}")
                
                # 构建内容
                base_prompt = prompt_text or config.GEMINI_TRANSCRIPTION_PROMPT

                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=base_prompt),
                            types.Part.from_bytes(
                                data=audio_bytes,
                                mime_type="audio/wav"
                            )
                        ],
                    ),
                ]
                
                # 生成配置，优化参数
                thinking_budget = config.GEMINI_THINKING_BUDGET
                generate_content_config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=thinking_budget,
                    ),
                    response_mime_type="text/plain",
                    temperature=0.0,  # 更低温度，更快响应
                    max_output_tokens=1000,  # 减少输出token限制
                )

                # API调用
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=generate_content_config,
                )
                
                if response and response.text:
                    self.last_run_info["api_attempts"] = attempt + 1
                    return response.text.strip()
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试：API返回空响应")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️  第 {attempt + 1} 次尝试失败: {error_msg}")
                
                # 判断是否应该重试
                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    if "UPSTREAM_ERROR" in error_msg or "EOF" in error_msg or "500" in error_msg:
                        print(f"🔄 检测到网络错误，{config.GEMINI_RETRY_DELAY}秒后重试...")
                        time.sleep(config.GEMINI_RETRY_DELAY)
                        continue
                    elif "timeout" in error_msg.lower():
                        print(f"⏰ 请求超时，{config.GEMINI_RETRY_DELAY}秒后重试...")
                        time.sleep(config.GEMINI_RETRY_DELAY)
                        continue
                    else:
                        # 不可重试的错误
                        print(f"❌ 不可重试的错误: {error_msg}")
                        break
                else:
                    print(f"❌ 所有重试都失败了")
        
        self.last_run_info["api_attempts"] = config.GEMINI_MAX_RETRIES
        return None
    
    def _call_gemini_audio_api(self, audio_file_path: str) -> Optional[str]:
        """调用Gemini音频API，包含重试机制和错误处理"""
        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                # 检查文件大小
                file_size = os.path.getsize(audio_file_path)
                print(f"📁 音频文件大小: {file_size / 1024:.1f}KB")
                
                if file_size > config.GEMINI_AUDIO_MAX_SIZE:
                    print(f"❌ 音频文件过大: {file_size / 1024 / 1024:.1f}MB (最大: {config.GEMINI_AUDIO_MAX_SIZE / 1024 / 1024}MB)")
                    return None
                
                # 读取音频文件
                with open(audio_file_path, 'rb') as f:
                    audio_data_bytes = f.read()
                
                print(f"🔄 API调用尝试 {attempt + 1}/{config.GEMINI_MAX_RETRIES}")
                
                # 构建内容
                base_prompt = self._build_prompt()

                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=base_prompt),
                            types.Part.from_bytes(
                                data=audio_data_bytes,
                                mime_type="audio/wav"
                            )
                        ],
                    ),
                ]
                
                # 生成配置，支持动态 thinking 设置
                thinking_budget = config.GEMINI_THINKING_BUDGET
                generate_content_config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=thinking_budget,
                    ),
                    response_mime_type="text/plain",
                    temperature=0.1,
                    max_output_tokens=2000,
                )

                # API调用
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=generate_content_config,
                )
                
                if response and response.text:
                    return response.text.strip()
                else:
                    print(f"⚠️  第 {attempt + 1} 次尝试：API返回空响应")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️  第 {attempt + 1} 次尝试失败: {error_msg}")
                
                # 判断是否应该重试
                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    if "UPSTREAM_ERROR" in error_msg or "EOF" in error_msg or "500" in error_msg:
                        print(f"🔄 检测到网络错误，{config.GEMINI_RETRY_DELAY}秒后重试...")
                        time.sleep(config.GEMINI_RETRY_DELAY)
                        continue
                    elif "timeout" in error_msg.lower():
                        print(f"⏰ 请求超时，{config.GEMINI_RETRY_DELAY}秒后重试...")
                        time.sleep(config.GEMINI_RETRY_DELAY)
                        continue
                    else:
                        # 不可重试的错误
                        print(f"❌ 不可重试的错误: {error_msg}")
                        break
                else:
                    print(f"❌ 所有重试都失败了")
        
        return None
    
    def _create_compressed_audio_bytes(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> Optional[bytes]:
        """
        创建压缩的音频字节数据（直接在内存中处理，无需临时文件）
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率（可选，用于降采样）
            
        Returns:
            WAV格式的字节数据或 None
        """
        try:
            # 确保音频数据是正确的格式
            if audio_data.dtype != np.int16:
                if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                    # 浮点格式转换
                    audio_data = (audio_data * 32767).astype(np.int16)
                else:
                    audio_data = audio_data.astype(np.int16)
            
            # 使用内存缓冲区创建WAV
            buffer = io.BytesIO()
            
            # 写入 WAV 数据
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(config.CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate or config.SAMPLE_RATE)
                wav_file.writeframes(audio_data.tobytes())
            
            # 获取字节数据
            audio_bytes = buffer.getvalue()
            buffer.close()
            
            return audio_bytes
            
        except Exception as e:
            print(f"❌ 创建压缩音频数据失败: {e}")
            return None
    
    def _save_audio_to_temp_file(self, audio_data: np.ndarray) -> Optional[str]:
        """
        将音频数据保存为临时 WAV 文件（向后兼容）
        
        Args:
            audio_data: 音频数据
            
        Returns:
            临时文件路径或 None
        """
        try:
            # 创建临时文件
            fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='gemini_audio_')
            os.close(fd)
            
            # 使用压缩方法创建音频数据
            audio_bytes = self._create_compressed_audio_bytes(audio_data)
            if not audio_bytes:
                return None
            
            # 写入文件
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)
            
            print(f"📁 临时音频文件: {temp_path} ({os.path.getsize(temp_path) / 1024:.1f}KB)")
            return temp_path
            
        except Exception as e:
            print(f"❌ 创建临时音频文件失败: {e}")
            return None
    
    def stop_processing(self):
        """停止处理（兼容接口）"""
        # Gemini 是请求-响应模式，无需特殊停止操作
        pass
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return config.GEMINI_AUDIO_FORMATS.copy()

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "name": "Gemini Audio Transcriber",
            "model": self.model,
            "language": config.GEMINI_AUDIO_LANGUAGE,
            "max_audio_size": config.GEMINI_AUDIO_MAX_SIZE,
            "supported_formats": self.get_supported_formats(),
            "is_ready": self.is_ready
        }

    # ==================== Prompt 构建 ====================

    def _build_prompt(self) -> str:
        """生成包含词典与纠错记忆的提示词"""

        inject_dict = getattr(config, "INJECT_DICTIONARY_IN_PROMPT", True)
        inject_corr = getattr(config, "INJECT_CORRECTIONS_IN_PROMPT", True)
        inject_history = getattr(config, "INJECT_HISTORY_IN_PROMPT", True)

        if not any([inject_dict, inject_corr, inject_history]):
            return config.GEMINI_TRANSCRIPTION_PROMPT

        cache_key = self._get_prompt_cache_key(inject_dict, inject_corr, inject_history)
        if (
            cache_key == self._prompt_cache_mtime
            and self._prompt_cache is not None
        ):
            return self._prompt_cache

        parts: List[str] = [config.GEMINI_TRANSCRIPTION_PROMPT.strip()]

        if inject_dict:
            dict_section = self._load_dictionary_section()
            if dict_section:
                header = getattr(
                    config,
                    "PROMPT_DICTIONARY_HEADER",
                    "词汇偏好（百分比为参考权重）：",
                )
                parts.append(f"{header}\n{dict_section}")

        if inject_corr:
            corr_section = self._load_corrections_section()
            if corr_section:
                header = getattr(
                    config,
                    "PROMPT_CORRECTIONS_HEADER",
                    "示例纠错（用于参考）：",
                )
                parts.append(f"{header}\n{corr_section}")

        if inject_history:
            history_section = self._load_history_section()
            if history_section:
                header = getattr(
                    config,
                    "PROMPT_HISTORY_HEADER",
                    "近期会话上下文（仅供参考）：",
                )
                parts.append(f"{header}\n{history_section}")

        prompt_text = "\n\n".join(parts)
        if getattr(config, "PRINT_PROMPT_ON_TRANSCRIBE", False):
            print("\n===== PROMPT START =====")
            print(prompt_text)
            print("===== PROMPT END =====\n")
        self._prompt_cache = prompt_text
        self._prompt_cache_mtime = cache_key
        return prompt_text

    def _get_prompt_cache_key(
        self, inject_dict: bool, inject_corr: bool, inject_history: bool
    ) -> Tuple[float, float, float]:
        dictionary_path = Path(config.DICTIONARY_FILE)
        corrections_path = Path(config.PROJECT_ROOT) / "logs" / "corrections.txt"
        history_path = Path(config.PROJECT_ROOT) / "logs" / "history.json"

        dict_mtime = dictionary_path.stat().st_mtime if (inject_dict and dictionary_path.exists()) else 0.0
        corr_mtime = corrections_path.stat().st_mtime if (inject_corr and corrections_path.exists()) else 0.0
        history_mtime = history_path.stat().st_mtime if (inject_history and history_path.exists()) else 0.0
        return dict_mtime, corr_mtime, history_mtime

    def _load_dictionary_section(self) -> str:
        dictionary_path = Path(config.DICTIONARY_FILE)
        if not dictionary_path.exists():
            return ""
        try:
            lines: List[str] = []
            with dictionary_path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.rstrip("\n")
                    if not stripped or stripped.lstrip().startswith("#"):
                        continue
                    lines.append(stripped)
            return "\n".join(lines)
        except Exception as exc:
            if config.DEBUG_MODE:
                print(f"⚠️ 读取词典用于提示词失败: {exc}")
            return ""

    def _load_corrections_section(self) -> str:
        corrections_path = Path(config.PROJECT_ROOT) / "logs" / "corrections.txt"
        if not corrections_path.exists():
            return ""
        try:
            content = corrections_path.read_text(encoding="utf-8")
            return content.strip()
        except Exception as exc:
            if config.DEBUG_MODE:
                print(f"⚠️ 读取 corrections.txt 失败: {exc}")
            return ""

    def _load_history_section(self) -> str:
        history_path = Path(config.PROJECT_ROOT) / "logs" / "history.json"
        if not history_path.exists():
            return ""

        try:
            raw = history_path.read_text(encoding="utf-8")
            history = json.loads(raw) if raw.strip() else []
        except Exception as exc:
            if config.DEBUG_MODE:
                print(f"⚠️ 读取 history.json 失败: {exc}")
            return ""

        if not isinstance(history, list):
            return ""

        limit = max(1, getattr(config, "PROMPT_HISTORY_LIMIT", 2))
        max_chars = max(50, getattr(config, "PROMPT_HISTORY_MAX_CHARS", 300))

        recent_texts: List[str] = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            text = (entry.get("text") or "").strip()
            if not text:
                continue
            if len(text) > max_chars:
                text = text[: max_chars - 1].rstrip() + "…"
            recent_texts.append(text)

        if not recent_texts:
            return ""

        selected = recent_texts[-limit:]
        lines = [f"{idx}. {value}" for idx, value in enumerate(selected, start=1)]
        return "\n".join(lines)


def test_gemini_transcriber():
    """测试 Gemini 转录器"""
    print("🧪 测试 Gemini 转录器...")
    
    transcriber = GeminiTranscriber()
    
    if not transcriber.is_ready:
        print("❌ 转录器未准备就绪")
        return False
    
    # 打印模型信息
    info = transcriber.get_model_info()
    print(f"📋 模型信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print("✅ Gemini 转录器测试完成")
    return True


if __name__ == "__main__":
    test_gemini_transcriber()
