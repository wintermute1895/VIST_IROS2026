"""
频率监控工具
用于实时监控 VIST 系统各个线程的实际运行频率

创建日期：2026-02-18
"""

import time
from collections import deque
from typing import Dict


class RateTracker:
    """
    简单的频率计

    用法：
        tracker = RateTracker()
        while True:
            freq = tracker.tick()
            print(f"Frequency: {freq:.1f} Hz")
    """

    def __init__(self):
        self.last_time = time.time()

    def tick(self) -> float:
        """
        记录一次执行，返回当前频率

        Returns:
            频率（Hz）
        """
        now = time.time()
        dt = now - self.last_time
        freq = 1.0 / dt if dt > 0 else 0
        self.last_time = now
        return freq

    def reset(self):
        """重置计时器"""
        self.last_time = time.time()


class SmoothRateTracker:
    """
    平滑频率计（使用滑动窗口）

    用法：
        tracker = SmoothRateTracker(window_size=10)
        while True:
            freq = tracker.tick()
            print(f"Frequency: {freq:.1f} Hz (smoothed)")
    """

    def __init__(self, window_size: int = 10):
        """
        初始化平滑频率计

        Args:
            window_size: 滑动窗口大小（样本数）
        """
        self.window_size = window_size
        self.timestamps = deque(maxlen=window_size)

    def tick(self) -> float:
        """
        记录一次执行，返回平滑后的频率

        Returns:
            平滑后的频率（Hz）
        """
        now = time.time()
        self.timestamps.append(now)

        if len(self.timestamps) < 2:
            return 0.0

        # 计算平均频率
        time_span = self.timestamps[-1] - self.timestamps[0]
        if time_span > 0:
            freq = (len(self.timestamps) - 1) / time_span
        else:
            freq = 0.0

        return freq

    def reset(self):
        """重置计时器"""
        self.timestamps.clear()


class MultiRateMonitor:
    """
    多速率系统监控器

    监控多个线程/组件的频率，并提供统计信息

    用法：
        monitor = MultiRateMonitor()

        # 在不同线程中
        monitor.tick('vision')
        monitor.tick('control')
        monitor.tick('visualization')

        # 获取统计
        stats = monitor.get_stats()
        print(stats)
    """

    def __init__(self, window_size: int = 30):
        """
        初始化多速率监控器

        Args:
            window_size: 每个组件的滑动窗口大小
        """
        self.window_size = window_size
        self.trackers: Dict[str, SmoothRateTracker] = {}
        self.counts: Dict[str, int] = {}
        self.start_time = time.time()

    def tick(self, component: str):
        """
        记录某个组件的一次执行

        Args:
            component: 组件名称（如 'vision', 'control'）
        """
        if component not in self.trackers:
            self.trackers[component] = SmoothRateTracker(self.window_size)
            self.counts[component] = 0

        self.trackers[component].tick()
        self.counts[component] += 1

    def get_frequency(self, component: str) -> float:
        """
        获取某个组件的当前频率

        Args:
            component: 组件名称

        Returns:
            频率（Hz），如果组件不存在返回 0
        """
        if component not in self.trackers:
            return 0.0

        return self.trackers[component].tick()

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        获取所有组件的统计信息

        Returns:
            统计信息字典
        """
        elapsed = time.time() - self.start_time
        stats = {}

        for component, tracker in self.trackers.items():
            # 获取当前频率（不调用 tick，避免影响计数）
            if len(tracker.timestamps) >= 2:
                time_span = tracker.timestamps[-1] - tracker.timestamps[0]
                current_freq = (len(tracker.timestamps) - 1) / time_span if time_span > 0 else 0
            else:
                current_freq = 0

            # 计算平均频率
            avg_freq = self.counts[component] / elapsed if elapsed > 0 else 0

            stats[component] = {
                'current_hz': current_freq,
                'average_hz': avg_freq,
                'total_count': self.counts[component],
                'elapsed_time': elapsed
            }

        return stats

    def print_stats(self, title: str = "频率统计"):
        """
        打印统计信息

        Args:
            title: 标题
        """
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")

        stats = self.get_stats()

        for component, data in sorted(stats.items()):
            print(f"{component:20s}: {data['current_hz']:6.1f} Hz "
                  f"(avg: {data['average_hz']:6.1f} Hz, "
                  f"count: {data['total_count']:6d})")

        print(f"{'='*60}\n")

    def reset(self):
        """重置所有统计"""
        for tracker in self.trackers.values():
            tracker.reset()
        self.counts = {k: 0 for k in self.counts}
        self.start_time = time.time()


# 使用示例
if __name__ == '__main__':
    import random

    print("=" * 60)
    print("频率监控工具测试")
    print("=" * 60)

    # 测试 1: 简单频率计
    print("\n测试 1: 简单频率计")
    tracker = RateTracker()

    for i in range(10):
        time.sleep(0.01)  # 模拟 100 Hz
        freq = tracker.tick()
        print(f"  迭代 {i+1}: {freq:.1f} Hz")

    # 测试 2: 平滑频率计
    print("\n测试 2: 平滑频率计")
    smooth_tracker = SmoothRateTracker(window_size=5)

    for i in range(10):
        time.sleep(0.01 + random.uniform(-0.002, 0.002))  # 模拟抖动
        freq = smooth_tracker.tick()
        print(f"  迭代 {i+1}: {freq:.1f} Hz (smoothed)")

    # 测试 3: 多速率监控器
    print("\n测试 3: 多速率监控器（模拟多线程）")
    monitor = MultiRateMonitor()

    # 模拟 3 秒的运行
    start = time.time()
    vision_period = 1.0 / 30  # 30 Hz
    control_period = 1.0 / 100  # 100 Hz
    viz_period = 1.0 / 10  # 10 Hz

    last_vision = start
    last_control = start
    last_viz = start

    while time.time() - start < 3.0:
        now = time.time()

        # 模拟 Vision Thread (30 Hz)
        if now - last_vision >= vision_period:
            monitor.tick('vision')
            last_vision = now

        # 模拟 Control Thread (100 Hz)
        if now - last_control >= control_period:
            monitor.tick('control')
            last_control = now

        # 模拟 Visualization Thread (10 Hz)
        if now - last_viz >= viz_period:
            monitor.tick('visualization')
            last_viz = now

        time.sleep(0.001)  # 避免 CPU 100%

    # 打印统计
    monitor.print_stats("模拟运行 3 秒后的统计")

    print("\n✅ 测试完成！")
    print("\n预期结果:")
    print("  - Vision: ~30 Hz")
    print("  - Control: ~100 Hz")
    print("  - Visualization: ~10 Hz")