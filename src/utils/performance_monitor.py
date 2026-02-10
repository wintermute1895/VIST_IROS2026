"""
性能监控模块
用于测量遥操作系统的各项性能指标
"""

import time
import numpy as np
from collections import deque
from typing import Dict, Optional
import json
from pathlib import Path


class PerformanceMonitor:
    """
    性能监控器

    测量和统计系统各模块的延迟、吞吐量等性能指标

    Example:
        >>> monitor = PerformanceMonitor()
        >>> monitor.start_timer("process")
        >>> # ... 执行操作 ...
        >>> monitor.stop_timer("process")
        >>> stats = monitor.get_stats("process")
        >>> print(f"平均延迟: {stats['mean']*1000:.2f} ms")
    """

    def __init__(self, window_size: int = 1000):
        """
        初始化性能监控器

        Args:
            window_size: 滑动窗口大小（保留最近 N 次测量）
        """
        self.metrics = {}
        self.window_size = window_size

    def start_timer(self, name: str):
        """
        开始计时

        Args:
            name: 计时器名称
        """
        if name not in self.metrics:
            self.metrics[name] = {
                'times': deque(maxlen=self.window_size),
                'start_time': None,
                'count': 0
            }
        self.metrics[name]['start_time'] = time.perf_counter()

    def stop_timer(self, name: str):
        """
        停止计时并记录

        Args:
            name: 计时器名称
        """
        if name in self.metrics and self.metrics[name]['start_time'] is not None:
            elapsed = time.perf_counter() - self.metrics[name]['start_time']
            self.metrics[name]['times'].append(elapsed)
            self.metrics[name]['count'] += 1
            self.metrics[name]['start_time'] = None

    def record_value(self, name: str, value: float):
        """
        直接记录一个值（不使用计时器）

        Args:
            name: 指标名称
            value: 值
        """
        if name not in self.metrics:
            self.metrics[name] = {
                'times': deque(maxlen=self.window_size),
                'start_time': None,
                'count': 0
            }
        self.metrics[name]['times'].append(value)
        self.metrics[name]['count'] += 1

    def get_stats(self, name: str) -> Optional[Dict]:
        """
        获取统计信息

        Args:
            name: 指标名称

        Returns:
            统计字典，包含 mean, std, min, max, p50, p95, p99, frequency
            如果没有数据则返回 None
        """
        if name not in self.metrics or len(self.metrics[name]['times']) == 0:
            return None

        times = np.array(self.metrics[name]['times'])
        mean_time = times.mean()

        return {
            'count': self.metrics[name]['count'],
            'mean': mean_time,
            'std': times.std(),
            'min': times.min(),
            'max': times.max(),
            'p50': np.percentile(times, 50),
            'p95': np.percentile(times, 95),
            'p99': np.percentile(times, 99),
            'frequency': 1.0 / mean_time if mean_time > 0 else 0
        }

    def get_all_stats(self) -> Dict[str, Dict]:
        """
        获取所有指标的统计信息

        Returns:
            字典，键为指标名称，值为统计信息
        """
        all_stats = {}
        for name in self.metrics:
            stats = self.get_stats(name)
            if stats:
                all_stats[name] = stats
        return all_stats

    def print_summary(self, title: str = "性能监控摘要"):
        """
        打印性能摘要

        Args:
            title: 标题
        """
        print("\n" + "="*70)
        print(title)
        print("="*70)

        for name in sorted(self.metrics.keys()):
            stats = self.get_stats(name)
            if stats:
                print(f"\n📊 {name}:")
                print(f"  样本数: {stats['count']}")
                print(f"  平均: {stats['mean']*1000:.2f} ms")
                print(f"  标准差: {stats['std']*1000:.2f} ms")
                print(f"  最小: {stats['min']*1000:.2f} ms")
                print(f"  最大: {stats['max']*1000:.2f} ms")
                print(f"  中位数 (P50): {stats['p50']*1000:.2f} ms")
                print(f"  P95: {stats['p95']*1000:.2f} ms")
                print(f"  P99: {stats['p99']*1000:.2f} ms")
                print(f"  频率: {stats['frequency']:.1f} Hz")

        print("="*70 + "\n")

    def save_to_file(self, filename: str):
        """
        保存性能数据到 JSON 文件

        Args:
            filename: 文件名
        """
        # 确保目录存在
        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 收集所有统计信息
        data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'window_size': self.window_size,
            'metrics': self.get_all_stats()
        }

        # 保存到文件
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✅ 性能数据已保存到: {filename}")

    def reset(self):
        """重置所有统计信息"""
        self.metrics = {}

    def reset_metric(self, name: str):
        """
        重置特定指标

        Args:
            name: 指标名称
        """
        if name in self.metrics:
            self.metrics[name]['times'].clear()
            self.metrics[name]['count'] = 0


class TeleopMetrics:
    """
    遥操作专用性能指标

    测量遥操作系统的关键性能指标：
    - 端到端延迟
    - 控制频率
    - 跟踪误差
    - 成功率
    """

    def __init__(self):
        self.monitor = PerformanceMonitor()
        self.success_count = 0
        self.failure_count = 0
        self.tracking_errors = deque(maxlen=1000)

    def record_loop_time(self, elapsed: float):
        """记录控制循环时间"""
        self.monitor.record_value("control_loop", elapsed)

    def record_tracking_error(self, error: float):
        """
        记录跟踪误差

        Args:
            error: 误差（米）
        """
        self.tracking_errors.append(error)
        self.monitor.record_value("tracking_error", error)

    def record_success(self):
        """记录成功"""
        self.success_count += 1

    def record_failure(self):
        """记录失败"""
        self.failure_count += 1

    def get_success_rate(self) -> float:
        """
        获取成功率

        Returns:
            成功率 [0, 1]
        """
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def get_summary(self) -> Dict:
        """
        获取完整摘要

        Returns:
            包含所有性能指标的字典
        """
        stats = self.monitor.get_all_stats()

        # 添加遥操作特定指标
        if len(self.tracking_errors) > 0:
            errors = np.array(self.tracking_errors)
            stats['tracking_error_stats'] = {
                'mean_mm': errors.mean() * 1000,
                'std_mm': errors.std() * 1000,
                'max_mm': errors.max() * 1000
            }

        stats['success_rate'] = self.get_success_rate()
        stats['success_count'] = self.success_count
        stats['failure_count'] = self.failure_count

        return stats

    def print_summary(self):
        """打印遥操作性能摘要"""
        self.monitor.print_summary("遥操作性能摘要")

        # 打印额外指标
        print("📈 遥操作指标:")
        print(f"  成功率: {self.get_success_rate()*100:.1f}%")
        print(f"  成功次数: {self.success_count}")
        print(f"  失败次数: {self.failure_count}")

        if len(self.tracking_errors) > 0:
            errors = np.array(self.tracking_errors)
            print(f"\n🎯 跟踪误差:")
            print(f"  平均: {errors.mean()*1000:.2f} mm")
            print(f"  标准差: {errors.std()*1000:.2f} mm")
            print(f"  最大: {errors.max()*1000:.2f} mm")

        print("="*70 + "\n")


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试性能监控器...")

    # 测试 1: 基础计时
    print("\n测试 1: 基础计时")
    monitor = PerformanceMonitor(window_size=100)

    for i in range(100):
        monitor.start_timer("test_operation")
        time.sleep(0.001)  # 模拟 1ms 操作
        monitor.stop_timer("test_operation")

    stats = monitor.get_stats("test_operation")
    print(f"平均延迟: {stats['mean']*1000:.2f} ms")
    print(f"频率: {stats['frequency']:.1f} Hz")

    # 测试 2: 多个计时器
    print("\n测试 2: 多个计时器")
    for i in range(50):
        monitor.start_timer("operation_a")
        time.sleep(0.002)
        monitor.stop_timer("operation_a")

        monitor.start_timer("operation_b")
        time.sleep(0.001)
        monitor.stop_timer("operation_b")

    monitor.print_summary()

    # 测试 3: 遥操作指标
    print("\n测试 3: 遥操作指标")
    teleop_metrics = TeleopMetrics()

    for i in range(100):
        teleop_metrics.record_loop_time(0.02)  # 20ms
        teleop_metrics.record_tracking_error(0.001)  # 1mm

        if i % 10 == 0:
            teleop_metrics.record_failure()
        else:
            teleop_metrics.record_success()

    teleop_metrics.print_summary()

    # 测试 4: 保存到文件
    print("\n测试 4: 保存到文件")
    monitor.save_to_file("logs/performance_test.json")

    print("\n✅ 所有测试通过")
