#!/usr/bin/env python3
"""
性能数据分析脚本

读取CSV文件并生成统计报告和图表
"""

import csv
import sys
import statistics
from pathlib import Path


def analyze_performance(csv_file):
    """分析性能数据"""
    if not Path(csv_file).exists():
        print(f"错误: 文件不存在: {csv_file}")
        return

    # 读取数据
    timestamps = []
    frequencies = []
    latencies = []

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamps.append(float(row['timestamp']))
            if float(row['frequency_hz']) > 0:
                frequencies.append(float(row['frequency_hz']))
            if float(row['latency_ms']) > 0:
                latencies.append(float(row['latency_ms']))

    if not frequencies:
        print("错误: 没有有效的数据")
        return

    # 计算统计指标
    print("=" * 60)
    print("性能分析报告")
    print("=" * 60)
    print(f"数据文件: {csv_file}")
    print(f"数据点数: {len(frequencies)}")
    print(f"时间范围: {timestamps[-1] - timestamps[0]:.2f} 秒")
    print()

    print("频率统计:")
    print(f"  平均值: {statistics.mean(frequencies):.2f} Hz")
    print(f"  标准差: {statistics.stdev(frequencies):.2f} Hz")
    print(f"  最小值: {min(frequencies):.2f} Hz")
    print(f"  最大值: {max(frequencies):.2f} Hz")
    print(f"  中位数: {statistics.median(frequencies):.2f} Hz")
    print()

    if latencies:
        print("延迟统计:")
        print(f"  平均值: {statistics.mean(latencies):.2f} ms")
        print(f"  标准差: {statistics.stdev(latencies):.2f} ms")
        print(f"  最小值: {min(latencies):.2f} ms")
        print(f"  最大值: {max(latencies):.2f} ms")
        print(f"  中位数: {statistics.median(latencies):.2f} ms")
        print()

        # 计算百分位数
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        print(f"  P50: {p50:.2f} ms")
        print(f"  P95: {p95:.2f} ms")
        print(f"  P99: {p99:.2f} ms")

    print("=" * 60)

    # 尝试生成图表（如果有matplotlib）
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # 频率图
        time_axis = [(t - timestamps[0]) for t in timestamps[:len(frequencies)]]
        axes[0].plot(time_axis, frequencies, 'b-', alpha=0.7, linewidth=0.5)
        axes[0].axhline(y=statistics.mean(frequencies), color='r', linestyle='--',
                       label=f'平均值: {statistics.mean(frequencies):.2f} Hz')
        axes[0].set_xlabel('时间 (秒)')
        axes[0].set_ylabel('频率 (Hz)')
        axes[0].set_title('控制频率')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # 延迟图
        if latencies:
            time_axis_lat = [(t - timestamps[0]) for t in timestamps[:len(latencies)]]
            axes[1].plot(time_axis_lat, latencies, 'g-', alpha=0.7, linewidth=0.5)
            axes[1].axhline(y=statistics.mean(latencies), color='r', linestyle='--',
                           label=f'平均值: {statistics.mean(latencies):.2f} ms')
            axes[1].set_xlabel('时间 (秒)')
            axes[1].set_ylabel('延迟 (ms)')
            axes[1].set_title('端到端延迟')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        output_file = csv_file.replace('.csv', '_plot.png')
        plt.savefig(output_file, dpi=150)
        print(f"\n图表已保存到: {output_file}")

    except ImportError:
        print("\n提示: 安装matplotlib可以生成图表")
        print("  pip install matplotlib")


def main():
    if len(sys.argv) < 2:
        print("用法: analyze_performance <csv_file>")
        print("示例: analyze_performance performance_log.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    analyze_performance(csv_file)


if __name__ == '__main__':
    main()
