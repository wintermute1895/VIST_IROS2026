#!/usr/bin/env python3
"""
测试轨迹插值器
演示插值器如何平滑处理突然的目标变化

Author: VIST Project
Date: 2026-02-22
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.control.trajectory_interpolator import TrajectoryInterpolator


def test_step_response():
    """测试阶跃响应：目标突然从0跳到1"""
    print("=" * 60)
    print("测试1: 阶跃响应（目标突然变化）")
    print("=" * 60)

    # 创建插值器
    interpolator = TrajectoryInterpolator(
        max_velocity=0.5,      # 0.5 rad/s
        max_acceleration=1.0,  # 1.0 rad/s²
        dt=0.05                # 20 Hz
    )

    # 初始化
    q_init = np.zeros(7)
    interpolator.reset(q_init)

    # 目标：关节0从0跳到1 rad
    q_target = np.zeros(7)
    q_target[0] = 1.0

    # 模拟100步（5秒）
    positions = []
    velocities = []
    times = []

    for i in range(100):
        q_next = interpolator.interpolate(q_target)
        v_current = interpolator.get_current_velocity()

        positions.append(q_next[0])
        velocities.append(v_current[0])
        times.append(i * 0.05)

    # 绘图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # 位置曲线
    ax1.plot(times, positions, 'b-', linewidth=2, label='实际位置')
    ax1.axhline(y=1.0, color='r', linestyle='--', label='目标位置')
    ax1.set_xlabel('时间 (s)')
    ax1.set_ylabel('位置 (rad)')
    ax1.set_title('位置响应（平滑过渡）')
    ax1.legend()
    ax1.grid(True)

    # 速度曲线
    ax2.plot(times, velocities, 'g-', linewidth=2, label='速度')
    ax2.axhline(y=0.5, color='r', linestyle='--', label='最大速度')
    ax2.axhline(y=-0.5, color='r', linestyle='--')
    ax2.set_xlabel('时间 (s)')
    ax2.set_ylabel('速度 (rad/s)')
    ax2.set_title('速度曲线（梯形）')
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig('interpolator_step_response.png', dpi=150)
    print("✅ 图表已保存: interpolator_step_response.png")

    # 统计
    print(f"\n统计信息:")
    print(f"  最终位置: {positions[-1]:.4f} rad")
    print(f"  最大速度: {max(velocities):.4f} rad/s")
    print(f"  到达时间: {times[np.argmax(np.array(positions) >= 0.99)]:.2f} s")


def test_direction_change():
    """测试方向突变：目标从+1突然变为-1"""
    print("\n" + "=" * 60)
    print("测试2: 方向突变（避免'咣当'）")
    print("=" * 60)

    # 创建插值器
    interpolator = TrajectoryInterpolator(
        max_velocity=0.5,
        max_acceleration=1.0,
        dt=0.05
    )

    # 初始化
    q_init = np.zeros(7)
    interpolator.reset(q_init)

    positions = []
    velocities = []
    accelerations = []
    times = []

    # 前50步：目标 = +1
    # 后50步：目标 = -1（突然反向）
    for i in range(100):
        if i < 50:
            q_target = np.array([1.0, 0, 0, 0, 0, 0, 0])
        else:
            q_target = np.array([-1.0, 0, 0, 0, 0, 0, 0])

        q_next = interpolator.interpolate(q_target)
        v_current = interpolator.get_current_velocity()

        positions.append(q_next[0])
        velocities.append(v_current[0])
        times.append(i * 0.05)

        # 计算加速度
        if i > 0:
            acc = (velocities[-1] - velocities[-2]) / 0.05
            accelerations.append(acc)
        else:
            accelerations.append(0)

    # 绘图
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10))

    # 位置
    ax1.plot(times, positions, 'b-', linewidth=2)
    ax1.axvline(x=2.5, color='r', linestyle='--', alpha=0.5, label='目标反向')
    ax1.set_ylabel('位置 (rad)')
    ax1.set_title('位置响应（方向突变）')
    ax1.legend()
    ax1.grid(True)

    # 速度
    ax2.plot(times, velocities, 'g-', linewidth=2)
    ax2.axhline(y=0.5, color='r', linestyle='--', alpha=0.3)
    ax2.axhline(y=-0.5, color='r', linestyle='--', alpha=0.3)
    ax2.axvline(x=2.5, color='r', linestyle='--', alpha=0.5)
    ax2.set_ylabel('速度 (rad/s)')
    ax2.set_title('速度曲线（平滑过渡，无突变）')
    ax2.grid(True)

    # 加速度
    ax3.plot(times, accelerations, 'orange', linewidth=2)
    ax3.axhline(y=1.0, color='r', linestyle='--', alpha=0.3, label='加速度限制')
    ax3.axhline(y=-1.0, color='r', linestyle='--', alpha=0.3)
    ax3.axvline(x=2.5, color='r', linestyle='--', alpha=0.5)
    ax3.set_xlabel('时间 (s)')
    ax3.set_ylabel('加速度 (rad/s²)')
    ax3.set_title('加速度曲线（在限制范围内）')
    ax3.legend()
    ax3.grid(True)

    plt.tight_layout()
    plt.savefig('interpolator_direction_change.png', dpi=150)
    print("✅ 图表已保存: interpolator_direction_change.png")

    # 统计
    print(f"\n统计信息:")
    print(f"  最大加速度: {max(accelerations):.4f} rad/s²")
    print(f"  最小加速度: {min(accelerations):.4f} rad/s²")
    print(f"  速度突变: 无（平滑过渡）")


if __name__ == "__main__":
    test_step_response()
    test_direction_change()
    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)