#!/usr/bin/env python3
"""
计时工具模块
用于测量各个处理步骤的时间
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
from contextlib import contextmanager

@dataclass
class TimingResult:
    """计时结果数据类"""
    name: str
    start_time: float
    end_time: float
    duration_ms: float
    
    def __str__(self) -> str:
        return f"{self.name}: {self.duration_ms:.1f}ms ({self.duration_ms/1000:.2f}s)"

class Timer:
    """高精度计时器"""
    
    def __init__(self):
        """初始化计时器"""
        self.timings: Dict[str, TimingResult] = {}
        self.start_times: Dict[str, float] = {}
    
    def start(self, name: str) -> None:
        """开始计时"""
        self.start_times[name] = time.perf_counter()
    
    def stop(self, name: str) -> Optional[TimingResult]:
        """停止计时并返回结果"""
        if name not in self.start_times:
            print(f"⚠️  警告: 未找到计时器 '{name}' 的开始时间")
            return None
        
        end_time = time.perf_counter()
        start_time = self.start_times[name]
        duration_ms = (end_time - start_time) * 1000
        
        result = TimingResult(
            name=name,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms
        )
        
        self.timings[name] = result
        del self.start_times[name]
        
        return result
    
    @contextmanager
    def measure(self, name: str):
        """上下文管理器方式计时"""
        self.start(name)
        try:
            yield
        finally:
            result = self.stop(name)
            if result:
                print(f"⏱️  {result}")
    
    def get_timing(self, name: str) -> Optional[TimingResult]:
        """获取指定计时结果"""
        return self.timings.get(name)
    
    def get_all_timings(self) -> Dict[str, TimingResult]:
        """获取所有计时结果"""
        return self.timings.copy()
    
    def print_summary(self, title: str = "计时统计") -> None:
        """打印计时统计摘要"""
        if not self.timings:
            print(f"📊 {title}: 暂无数据")
            return
        
        print(f"\n📊 {title}")
        print("=" * 50)
        
        total_time = 0
        for timing in self.timings.values():
            print(f"  {timing}")
            total_time += timing.duration_ms
        
        print("-" * 50)
        print(f"  总耗时: {total_time:.1f}ms ({total_time/1000:.2f}s)")
        print("=" * 50)
    
    def reset(self) -> None:
        """重置所有计时数据"""
        self.timings.clear()
        self.start_times.clear()
    
    def format_duration(self, duration_ms: float) -> str:
        """格式化时间显示"""
        if duration_ms < 1000:
            return f"{duration_ms:.1f}ms"
        else:
            return f"{duration_ms/1000:.2f}s ({duration_ms:.1f}ms)"

# 全局计时器实例
global_timer = Timer()

# 便捷函数
def start_timer(name: str) -> None:
    """开始计时"""
    global_timer.start(name)

def stop_timer(name: str) -> Optional[TimingResult]:
    """停止计时"""
    return global_timer.stop(name)

def print_timer_summary(title: str = "处理时间统计") -> None:
    """打印计时摘要"""
    global_timer.print_summary(title)

def reset_timers() -> None:
    """重置所有计时器"""
    global_timer.reset()

# 测试代码
if __name__ == "__main__":
    # 测试计时功能
    timer = Timer()
    
    # 测试1: 基本计时
    timer.start("test_operation")
    time.sleep(0.1)
    result = timer.stop("test_operation")
    print(f"测试1结果: {result}")
    
    # 测试2: 上下文管理器
    with timer.measure("context_test"):
        time.sleep(0.05)
    
    # 测试3: 多个计时
    timer.start("step1")
    time.sleep(0.02)
    timer.stop("step1")
    
    timer.start("step2")
    time.sleep(0.03)
    timer.stop("step2")
    
    # 打印摘要
    timer.print_summary("测试计时统计")