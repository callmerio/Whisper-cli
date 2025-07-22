#!/usr/bin/env python3
"""
代理测试脚本
测试系统代理是否正常工作
"""

import os
import httpx
import requests
from dotenv import load_dotenv

load_dotenv()

def test_system_proxy():
    """测试系统代理"""
    print("🔍 检测系统代理设置...")
    
    # 检查环境变量
    http_proxy = os.getenv('HTTP_PROXY', os.getenv('http_proxy', ''))
    https_proxy = os.getenv('HTTPS_PROXY', os.getenv('https_proxy', ''))
    
    print(f"HTTP_PROXY: {http_proxy}")
    print(f"HTTPS_PROXY: {https_proxy}")
    
    if not http_proxy and not https_proxy:
        print("⚠️  未检测到系统代理设置")
        return False
    
    # 测试代理连接
    proxies = {}
    if http_proxy:
        proxies["http://"] = http_proxy
    if https_proxy:
        proxies["https://"] = https_proxy
    
    try:
        print(f"\n🌐 测试代理连接: {proxies}")
        
        # 使用 httpx 测试
        proxy_url = https_proxy if https_proxy else http_proxy
        mounts = {
            "https://": httpx.HTTPTransport(proxy=proxy_url),
            "http://": httpx.HTTPTransport(proxy=proxy_url),
        }
        with httpx.Client(mounts=mounts, timeout=10) as client:
            response = client.get("https://httpbin.org/ip")
            print(f"✅ httpx 代理测试成功")
            print(f"   外网IP: {response.json()}")
            
        # 使用 requests 测试  
        response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
        print(f"✅ requests 代理测试成功")
        print(f"   外网IP: {response.json()}")
        
        return True
        
    except Exception as e:
        print(f"❌ 代理测试失败: {e}")
        return False

def test_gemini_with_proxy():
    """测试Gemini API代理连接"""
    from gemini_corrector import GeminiCorrector
    
    print(f"\n🤖 测试Gemini API代理连接...")
    
    corrector = GeminiCorrector()
    if not corrector.is_ready:
        print("❌ Gemini纠错器未就绪")
        return False
    
    # 简单测试
    test_text = "测试代理连接"
    result = corrector.correct_transcript(test_text)
    
    if result and result != test_text:
        print(f"✅ Gemini代理连接成功")
        print(f"   原文: {test_text}")
        print(f"   结果: {result}")
        return True
    else:
        print(f"⚠️  Gemini代理连接可能有问题")
        return False

if __name__ == "__main__":
    print("🔧 代理连接测试工具")
    print("=" * 50)
    
    # 测试系统代理
    proxy_ok = test_system_proxy()
    
    if proxy_ok:
        # 测试Gemini代理
        test_gemini_with_proxy()
    else:
        print("\n💡 如需使用代理，请设置环境变量:")
        print("   export HTTP_PROXY='http://127.0.0.1:7890'")
        print("   export HTTPS_PROXY='http://127.0.0.1:7890'")
        print("或在 .env 文件中添加相应配置")