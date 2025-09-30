#!/usr/bin/env python3
"""
诊断脚本 - 检查为什么文本没有正确输出到目标应用
"""

import time
import subprocess
from text_input_manager import TextInputManager, InputRequest, InputMethod

def get_active_app():
    """获取当前活跃的应用程序"""
    try:
        script = '''
        tell application "System Events"
            set activeApp to name of first application process whose frontmost is true
            return activeApp
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"无法获取活跃应用: {e}")
    return "未知"

def test_with_app_focus():
    """测试文本输入到指定应用"""
    print("🔍 诊断文本输入问题...")
    
    # 检查当前活跃应用
    current_app = get_active_app()
    print(f"📱 当前活跃应用: {current_app}")
    
    # 创建文本输入管理器
    manager = TextInputManager()
    
    print("\n⚠️ 请切换到你希望输入文本的应用程序...")
    print("   建议使用: TextEdit, 备忘录, 或浏览器输入框")
    print("   切换后等待3秒...")
    
    time.sleep(3)
    
    # 检查切换后的应用
    target_app = get_active_app()
    print(f"🎯 目标应用: {target_app}")
    
    # 测试文本
    test_text = "🧪 这是一个测试文本 "
    
    print(f"\n🚀 开始输入: '{test_text}'")
    print("   输入方法: 直接键盘输入")
    print("   注意观察目标应用是否接收到文本...")
    
    # 创建输入请求
    request = InputRequest(
        text=test_text,
        method=InputMethod.DIRECT_TYPE,
        delay_before=0.2,  # 增加延迟确保应用准备好
        delay_after=0.2,
        backup_to_clipboard=True
    )
    
    # 执行输入
    start_time = time.time()
    result = manager.input_text(request)
    end_time = time.time()
    
    print(f"\n📊 输入完成:")
    print(f"   结果: {result}")
    print(f"   耗时: {(end_time - start_time)*1000:.1f}ms")
    print(f"   字符数: {len(test_text)}")
    
    if result.name == 'SUCCESS':
        print(f"\n✅ 系统认为输入成功")
        print(f"🔍 请检查 {target_app} 中是否出现了文本:")
        print(f"   '{test_text}'")
        
        # 再次检查活跃应用
        final_app = get_active_app()
        if final_app != target_app:
            print(f"⚠️ 警告: 应用焦点发生变化 {target_app} → {final_app}")
            print("   这可能是输入失败的原因")
    else:
        print(f"\n❌ 输入失败: {result.value}")
        
        # 诊断失败原因
        if result.name == 'PERMISSION_DENIED':
            print("🔐 权限问题 - 请检查系统偏好设置中的辅助功能权限")
        elif result.name == 'METHOD_UNAVAILABLE':
            print("🚫 输入方法不可用 - pynput 可能有问题")
        else:
            print("🤔 未知错误 - 请查看详细日志")

if __name__ == "__main__":
    test_with_app_focus()