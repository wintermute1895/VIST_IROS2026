#!/usr/bin/env python3
"""
演示开环 vs 闭环控制的区别

模拟场景：机器人有10%的跟踪延迟（只能达到命令的90%）
"""

import numpy as np
import matplotlib.pyplot as plt


def simulate_open_loop(commands, tracking_ratio=0.9):
    """开环控制：假设命令完美执行"""
    assumed_positions = []
    actual_positions = []
    errors = []

    q_assumed = 0.0  # 假设的位置
    q_actual = 0.0   # 真实的位置

    for cmd in commands:
        # 发送命令
        q_assumed = cmd  # 假设到达命令位置

        # 实际上只能达到90%
        q_actual = q_actual + (cmd - q_actual) * tracking_ratio

        assumed_positions.append(q_assumed)
        actual_positions.append(q_actual)
        errors.append(abs(q_assumed - q_actual))

    return assumed_positions, actual_positions, errors


def simulate_closed_loop(commands, tracking_ratio=0.9):
    """闭环控制：读取实际位置"""
    commanded_positions = []
    actual_positions = []
    errors = []

    q_actual = 0.0  # 真实的位置

    for cmd in commands:
        # 发送命令
        commanded_positions.append(cmd)

        # 实际上只能达到90%
        q_actual = q_actual + (cmd - q_actual) * tracking_ratio

        # 读取实际位置（闭环反馈）
        actual_positions.append(q_actual)
        errors.append(abs(cmd - q_actual))

    return commanded_positions, actual_positions, errors


# 生成测试命令：阶跃 + 正弦波
t = np.linspace(0, 10, 200)
commands = np.zeros_like(t)
commands[50:] = 1.0  # 阶跃
commands += 0.3 * np.sin(2 * np.pi * 0.5 * t)  # 正弦波

# 模拟开环和闭环
open_assumed, open_actual, open_errors = simulate_open_loop(commands)
closed_cmd, closed_actual, closed_errors = simulate_closed_loop(commands)

# 绘图对比
fig, axes = plt.subplots(3, 1, figsize=(12, 10))

# 1. 开环控制
ax1 = axes[0]
ax1.plot(t, commands, 'b--', label='命令位置', linewidth=2)
ax1.plot(t, open_assumed, 'g-', label='假设位置（控制器认为的）', linewidth=2)
ax1.plot(t, open_actual, 'r-', label='实际位置', linewidth=2, alpha=0.7)
ax1.set_ylabel('位置 (rad)')
ax1.set_title('开环控制：控制器不知道真实位置，基于假设计算')
ax1.legend()
ax1.grid(True)

# 2. 闭环控制
ax2 = axes[1]
ax2.plot(t, closed_cmd, 'b--', label='命令位置', linewidth=2)
ax2.plot(t, closed_actual, 'r-', label='实际位置（控制器知道的）', linewidth=2)
ax2.set_ylabel('位置 (rad)')
ax2.set_title('闭环控制：控制器读取真实位置，基于实际计算')
ax2.legend()
ax2.grid(True)

# 3. 误差对比
ax3 = axes[2]
ax3.plot(t, open_errors, 'g-', label='开环误差（累积）', linewidth=2)
ax3.plot(t, closed_errors, 'r-', label='闭环误差（稳定）', linewidth=2)
ax3.set_xlabel('时间 (s)')
ax3.set_ylabel('跟踪误差 (rad)')
ax3.set_title('误差对比：开环误差累积，闭环误差稳定')
ax3.legend()
ax3.grid(True)

plt.tight_layout()
plt.savefig('open_vs_closed_loop.png', dpi=150)
print("✅ 图表已保存: open_vs_closed_loop.png")

# 统计
print(f"\n统计对比:")
print(f"开环平均误差: {np.mean(open_errors):.4f} rad")
print(f"闭环平均误差: {np.mean(closed_errors):.4f} rad")
print(f"开环最大误差: {np.max(open_errors):.4f} rad")
print(f"闭环最大误差: {np.max(closed_errors):.4f} rad")
print(f"\n关键区别:")
print(f"- 开环：控制器基于假设位置计算，误差累积")
print(f"- 闭环：控制器基于真实位置计算，误差稳定")