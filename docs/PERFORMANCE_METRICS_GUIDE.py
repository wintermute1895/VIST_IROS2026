#!/usr/bin/env python3
"""
性能指标解读指南

帮助理解性能报告中的各项统计指标
"""

import numpy as np
import matplotlib.pyplot as plt

# 模拟一组耗时数据（单位：ms）
np.random.seed(42)
data = np.random.gamma(2, 1, 1000)  # 模拟真实的耗时分布

print("=" * 80)
print("📊 性能指标解读指南")
print("=" * 80)

print("\n假设我们测量了 1000 次操作的耗时，得到以下数据：")
print(f"数据范围: {data.min():.2f} ms ~ {data.max():.2f} ms")

print("\n" + "=" * 80)
print("1. 基础统计指标")
print("=" * 80)

mean = np.mean(data)
std = np.std(data)
min_val = np.min(data)
max_val = np.max(data)

print(f"\n平均值 (Mean): {mean:.2f} ms")
print("  含义: 所有测量值的算术平均")
print("  用途: 了解总体性能水平")
print("  注意: 容易受极端值影响")

print(f"\n标准差 (Std): {std:.2f} ms")
print("  含义: 数据的离散程度")
print("  用途: 判断性能是否稳定")
print("  解读:")
print(f"    - 小标准差 (< 平均值的20%): 性能稳定")
print(f"    - 大标准差 (> 平均值的50%): 性能波动大")
print(f"  当前: {std/mean*100:.1f}% (相对标准差)")

print(f"\n最小值 (Min): {min_val:.2f} ms")
print("  含义: 最快的一次操作")
print("  用途: 了解理想情况下的性能")

print(f"\n最大值 (Max): {max_val:.2f} ms")
print("  含义: 最慢的一次操作")
print("  用途: 发现性能异常")
print("  注意: 可能是偶发的极端情况")

print("\n" + "=" * 80)
print("2. 百分位数 (Percentiles)")
print("=" * 80)

p50 = np.percentile(data, 50)
p95 = np.percentile(data, 95)
p99 = np.percentile(data, 99)

print(f"\nP50 (中位数): {p50:.2f} ms")
print("  含义: 50% 的操作耗时 ≤ 这个值")
print("  用途: 比平均值更能代表'典型'性能")
print("  优点: 不受极端值影响")
print(f"  解读: 一半的操作在 {p50:.2f} ms 内完成")

print(f"\nP95 (95百分位): {p95:.2f} ms")
print("  含义: 95% 的操作耗时 ≤ 这个值")
print("  用途: 了解'大多数情况'的性能")
print(f"  解读: 只有 5% 的操作超过 {p95:.2f} ms")

print(f"\nP99 (99百分位): {p99:.2f} ms")
print("  含义: 99% 的操作耗时 ≤ 这个值")
print("  用途: 发现性能尾部问题")
print(f"  解读: 只有 1% 的操作超过 {p99:.2f} ms")

print("\n💡 为什么关注百分位数？")
print("  - 平均值会被极端值拉高")
print("  - P50 更能代表'正常'情况")
print("  - P95/P99 帮助发现偶发的性能问题")

print("\n" + "=" * 80)
print("3. 频率 (Frequency)")
print("=" * 80)

frequency = 1000 / mean  # Hz
print(f"\n频率: {frequency:.1f} Hz")
print("  含义: 每秒可以执行多少次操作")
print("  计算: 1000 ms / 平均耗时(ms)")
print(f"  解读: 理论上每秒可以执行 {frequency:.1f} 次")
print("\n⚠️  注意:")
print("  - 这是理论处理能力")
print("  - 实际频率可能受其他因素限制（如sleep、等待）")

print("\n" + "=" * 80)
print("4. 实际案例分析")
print("=" * 80)

print("\n以你的真机数据为例：")
print("\n📊 total_loop:")
print("  平均: 3.75 ms")
print("  P50: 3.64 ms")
print("  P95: 5.37 ms")
print("  频率: 266.5 Hz")
print("\n解读:")
print("  ✅ 平均和P50接近 (3.75 vs 3.64) → 性能稳定")
print("  ✅ P95不算太高 (5.37 ms) → 偶发延迟不严重")
print("  ✅ 理论处理能力 266 Hz → 远超当前10 Hz配置")
print("  💡 结论: 有大量性能余量，可以提高控制频率")

print("\n📊 vist_process:")
print("  平均: 2.10 ms")
print("  P50: 2.03 ms")
print("  P95: 3.32 ms")
print("\n解读:")
print("  ✅ 占总循环时间的 56% (2.10/3.75)")
print("  ✅ 这是最耗时的部分，但仍然很快")
print("  💡 VIST算法效率很高")

print("\n📊 send_command:")
print("  平均: 1.51 ms")
print("  最大: 4.89 ms")
print("\n解读:")
print("  ⚠️  最大值是平均值的3倍 → 偶尔有网络延迟")
print("  ✅ 但P95只有2.11 ms → 大多数情况正常")
print("  💡 TCP通信基本稳定")

print("\n" + "=" * 80)
print("5. 如何判断性能瓶颈")
print("=" * 80)

print("\n检查清单:")
print("  1. 哪个模块耗时最长？")
print("     → vist_process (2.10 ms) 是最耗时的")
print("\n  2. 总耗时 vs 控制周期")
print("     → 3.75 ms vs 100 ms (10 Hz)")
print("     → 浪费了 96 ms！")
print("\n  3. 标准差 / 平均值")
print("     → 0.91 / 3.75 = 24%")
print("     → 性能相对稳定")
print("\n  4. P95 vs 平均值")
print("     → 5.37 / 3.75 = 1.43x")
print("     → 偶发延迟不严重")

print("\n💡 结论:")
print("  - 没有明显的性能瓶颈")
print("  - 处理能力远超当前需求")
print("  - 可以安全地提高控制频率到 20-30 Hz")
print("  - 主要限制是人为设置的 sleep")

print("\n" + "=" * 80)
print("6. 优化建议")
print("=" * 80)

print("\n基于性能数据的建议:")
print("  1. 提高控制频率: 10 Hz → 20 Hz")
print("     理由: 处理只需3.75 ms，20 Hz (50 ms)完全可行")
print("\n  2. 放宽速度限制: 0.1 → 0.3 rad/s")
print("     理由: 51%的帧被速度限制，太严格")
print("\n  3. 监控电机温度")
print("     理由: 提高频率后需要确保不过热")
print("\n  4. 对比优化前后的性能数据")
print("     关注: P95延迟、安全限制触发率")

print("\n" + "=" * 80)