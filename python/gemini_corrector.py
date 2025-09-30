#!/usr/bin/env python3
"""
Gemini纠错模块
使用Gemini 2.5 Flash对转录结果进行后处理纠错
"""

import hashlib
import os
from typing import Optional, List, Dict, Any

import httpx
from google import genai
from google.genai import types

import config

class GeminiCorrector:
    def __init__(self):
        """初始化Gemini纠错器"""
        self.api_key = config.GEMINI_API_KEY
        self.model = config.GEMINI_MODEL  # 使用配置文件中的模型设置
        self.is_ready = bool(self.api_key)
        
        if self.is_ready:
            try:
                # 配置代理 - 使用环境变量方式
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
                
                print(f"✅ Gemini纠错器已就绪 ({self.model})")
                if config.DEBUG_MODE and self.api_key:
                    digest = hashlib.sha256(self.api_key.encode()).hexdigest()[:12]
                    print(f"   API密钥指纹: {digest}")
                    
            except Exception as e:
                print(f"❌ Gemini客户端初始化失败: {e}")
                self.is_ready = False
        else:
            print("⚠️  Gemini API密钥未配置，将跳过后处理纠错")
            print(f"   请在.env文件中设置 GEMINI_API_KEY")
    
    def correct_transcript(self, transcript_text: str) -> Optional[str]:
        """
        使用Gemini对转录文本进行纠错
        
        Args:
            transcript_text: 原始转录文本
            
        Returns:
            纠错后的文本，如果失败返回None
        """
        if not self.is_ready or not transcript_text.strip():
            return transcript_text
        
        try:
            # 构建提示词
            prompt = self._build_correction_prompt(transcript_text)
            
            # 调用新的Gemini API
            corrected_text = self._call_gemini_api_new(prompt)
            
            if corrected_text and corrected_text.strip() != transcript_text.strip():
                if config.DEBUG_MODE:
                    print(f"原文: {transcript_text}")
                    print(f"纠错: {corrected_text}")
                return corrected_text
            else:
                return transcript_text
                
        except Exception as e:
            print(f"Gemini纠错失败: {e}")
            return transcript_text
    
    def _build_correction_prompt(self, text: str) -> str:
        """构建纠错提示词"""
        return config.GEMINI_CORRECTION_PROMPT.format(text=text)
    
    def _call_gemini_api_new(self, prompt: str) -> Optional[str]:
        """调用新的Gemini API"""
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=0,  # 无思考模式
                ),
                response_mime_type="text/plain",
                temperature=0.1,  # 低温度确保稳定输出
                max_output_tokens=1000,
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )
            
            if response and response.text:
                return response.text.strip()
            else:
                print("Gemini API返回空响应")
                return None
                
        except Exception as e:
            print(f"Gemini API调用失败: {e}")
            return None
    
    def test_connection(self) -> bool:
        """测试Gemini API连接"""
        if not self.is_ready:
            return False
        
        test_text = "测试文本"
        result = self.correct_transcript(test_text)
        return result is not None

# 测试代码
if __name__ == "__main__":
    corrector = GeminiCorrector()
    
    if corrector.is_ready:
        # 测试纠错功能
        test_cases = [
            "测试语音转录的效果不行不行差距太大了这个转录",
            "今天天气很好我们去公园玩吧",
            "请帮我预定明天上午九点的会议室"
        ]
        
        for test_text in test_cases:
            print(f"\n{'='*50}")
            print(f"原文: {test_text}")
            corrected = corrector.correct_transcript(test_text)
            print(f"纠错: {corrected}")
    else:
        print("请先配置GEMINI_API_KEY环境变量")
