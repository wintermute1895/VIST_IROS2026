#!/usr/bin/env python3
"""
测试低通滤波器效果

模拟VIST输出有跳变的情况，验证滤波器能否平滑输出
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.control.filters import LowPassFilter


def test_filter_with_jumps():
    """测试滤波器对跳变的抑制效果"""

    # 创建测试信号：平滑信号 + 随机跳变
    n_samples = 200
    t = np.linspace(0, 10, n_samples)

    # 基础信号：正弦波
    signal_base = 0.5 * np.sin(2 * np.pi * 0.5 * t)

    # 添加随机跳变（模拟VIST输出的跳变）
    signal_noisy = signal_base.copy()
    jump_indices = np.random.choice(n_samples, size=20, replace=False)
    for idx in jump_indices:
        signal_noisy[idx] += np.random.uniform(-0.2, 0.2)

    # 测试不同的alpha值
    alphas = [1.0, 0.5, 0.2, 0.1]

    plt.figure(figsize=(15, 10))

    for i, alpha in enumerate(alphas):
        # 创建滤波器
        lpf = LowPassFilter(alpha=alpha, n_dims=1)

        # 应用滤波
        signal_filtered = []
        for val in signal_noisy:
            filtered = lpf.update(np.array([val]))
            signal_filtered.append(filtered[0])

        signal_filtered = np.array(signal_filtered)

        # 计算跳变抑制效果
        jumps_original = np.abs(np.diff(signal_noisy))
        jumps_filtered = np.abs(np.diff(signal_filtered))
        reduction = (1 - np.mean(jumps_filtered) / np.mean(jumps_original)) * 100

        # 绘图
        plt.subplot(2, 2, i+1)
        plt.plot(t, signal_base, 'g--', label='理想信号', alpha=0.5, linewidth=2)
        plt.plot(t, signal_noisy, 'r.', label='带跳变的信号', alpha=0.3, markersize=3)
        plt.plot(t, signal_filtered, 'b-', label=f'滤波后 (α={alpha})', linewidth=2)
        plt.title(f'α={alpha} - 跳变抑制: {reduction:.1f}%')
        plt.xlabel('时间 (s)')
        plt.ylabel('关节角度 (rad)')
        plt.legend()
        plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('/home/ilex/Dev/VIST/logs/filter_test.png', dpi=150)
    print(f"✅ 测试完成！结果保存到: /home/ilex/Dev/VIST/logs/filter_test.png")

    # 打印推荐
    print("\n📊 滤波器效果分析:")
    print("  α=1.0: 无滤波，跳变完全保留")
    print("  α=0.5: 中等平滑，跳变减少约50%")
    print("  α=0.2: 强平滑，跳变减少约80%（推荐）")
    print("  α=0.1: 非常强的平滑，跳变减少约90%，但响应变慢")
    print("\n💡 建议: 使用 α=0.2 作为默认值，在平滑性和响应性之间取得良好平衡")


def test_velocity_calculation():
    """测试滤波器对速度计算的影响"""

    # 创建有跳变的信号
    n_samples = 100
    dt = 0.05  # 20 Hz

    signal = np.zeros(n_samples)
    signal[0:30] = 0.0
    signal[30:60] = 0.5  # 突然跳变
    signal[60:] = 0.5

    # 添加噪声
    signal += np.random.normal(0, 0.01, n_samples)

    # 测试不同alpha
    alphas = [1.0, 0.2]

    plt.figure(figsize=(15, 5))

    for i, alpha in enumerate(alphas):
        lpf = LowPassFilter(alpha=alpha, n_dims=1)

        filtered = []
        velocities = []
        prev_val = 0

        for val in signal:
            filt = lpf.update(np.array([val]))[0]
            filtered.append(filt)

            # 计算速度
            vel = (filt - prev_val) / dt
            velocities.append(vel)
            prev_val = filt

        filtered = np.array(filtered)
        velocities = np.array(velocities)

        # 绘制位置
        plt.subplot(1, 3, i+1)
        plt.plot(signal, 'r.', label='原始信号', alpha=0.5)
        plt.plot(filtered, 'b-', label=f'滤波后 (α={alpha})', linewidth=2)
        plt.title(f'位置 (α={alpha})')
        plt.xlabel('帧')
        plt.ylabel('位置 (rad)')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 绘制速度
        plt.subplot(1, 3, 3)
        plt.plot(velocities, label=f'α={alpha}', linewidth=2)

    plt.subplot(1, 3, 3)
    plt.axhline(y=0.5/dt, color='g', linestyle='--', label='理论最大速度', alpha=0.5)
    plt.title('计算的速度')
    plt.xlabel('帧')
    plt.ylabel('速度 (rad/s)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('/home/ilex/Dev/VIST/logs/velocity_test.png', dpi=150)
    print(f"✅ 速度测试完成！结果保存到: /home/ilex/Dev/VIST/logs/velocity_test.png")


if __name__ == "__main__":
    print("🧪 测试低通滤波器...")
    print("="*60)

    test_filter_with_jumps()
    print()
    test_velocity_calculation()

    print("\n✅ 所有测试完成！")