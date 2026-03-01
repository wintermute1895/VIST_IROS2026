#!/usr/bin/env python3
"""
频率监控测试脚本
用于验证频率监控功能是否正常工作
"""

import time
from collections import deque
import threading


class FrequencyMonitor:
    """频率监控器 - 用于实时监控话题频率"""

    def __init__(self, window_size: int = 100, name: str = "Unknown"):
        """
        初始化频率监控器

        Args:
            window_size: 滑动窗口大小（用于计算平均频率）
            name: 监控器名称
        """
        self.name = name
        self.window_size = window_size
        self.timestamps = deque(maxlen=window_size)
        self.count = 0
        self.last_print_time = time.time()
        self.lock = threading.Lock()

    def tick(self):
        """记录一次事件"""
        with self.lock:
            current_time = time.time()
            self.timestamps.append(current_time)
            self.count += 1

    def get_frequency(self) -> float:
        """
        计算当前频率

        Returns:
            频率 (Hz)
        """
        with self.lock:
            if len(self.timestamps) < 2:
                return 0.0

            time_span = self.timestamps[-1] - self.timestamps[0]
            if time_span <= 0:
                return 0.0

            return (len(self.timestamps) - 1) / time_span

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            freq = self.get_frequency()
            return {
                'name': self.name,
                'frequency': freq,
                'total_count': self.count,
                'window_size': len(self.timestamps)
            }

    def reset(self):
        """重置统计"""
        with self.lock:
            self.timestamps.clear()
            self.count = 0


def test_frequency_monitor():
    """测试频率监控器"""
    print("开始测试频率监控器...")

    # 创建监控器
    monitor = FrequencyMonitor(window_size=100, name="测试监控器")

    # 模拟 80 Hz 的事件
    target_freq = 80.0
    period = 1.0 / target_freq

    print(f"模拟 {target_freq} Hz 的事件流...")
    print("按 Ctrl+C 停止测试\n")

    try:
        start_time = time.time()
        while True:
            # 记录事件
            monitor.tick()

            # 每秒打印一次统计
            current_time = time.time()
            if current_time - monitor.last_print_time >= 1.0:
                stats = monitor.get_stats()
                elapsed = current_time - start_time

                print(f"[{elapsed:6.1f}s] {stats['name']}: "
                      f"{stats['frequency']:6.2f} Hz | "
                      f"总计: {stats['total_count']:5} | "
                      f"窗口: {stats['window_size']:3}")

                monitor.last_print_time = current_time

            # 等待下一个周期
            time.sleep(period)

    except KeyboardInterrupt:
        print("\n测试结束")
        final_stats = monitor.get_stats()
        print(f"\n最终统计:")
        print(f"  名称: {final_stats['name']}")
        print(f"  平均频率: {final_stats['frequency']:.2f} Hz")
        print(f"  总事件数: {final_stats['total_count']}")
        print(f"  窗口大小: {final_stats['window_size']}")


if __name__ == '__main__':
    test_frequency_monitor()
