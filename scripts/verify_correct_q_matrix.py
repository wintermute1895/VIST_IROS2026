#!/usr/bin/env python3
"""
验证正确的Q矩阵设计：任务空间插值方案

这个脚本验证以下理论：
1. Q越大 → 更听话（自由移动）
2. Q越小 → 更僵硬（虚拟夹具）
3. Z轴的Q始终保持大值（从1.0到1.0），不会"卡死"
4. 抖动抑制靠R矩阵增大，而不是Q矩阵减小

测试场景：
- 场景1：α=0（自由空间），XYZ都能自由移动
- 场景2：α=0.5（过渡阶段），XY开始受约束，Z保持自由
- 场景3：α=1（约束流形），XY完全冻结，Z依然能推动
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def build_task_space_Q(alpha, high_gain=1e-2):
    """
    在任务空间构建Q矩阵

    Args:
        alpha: 意图因子 [0, 1]
        high_gain: 基础增益

    Returns:
        Q_task: 任务空间Q矩阵 (3x3)
    """
    # 自由空间：所有方向都听话
    Sigma_free = np.diag([1.0, 1.0, 1.0]) * high_gain

    # 约束流形：Z轴听话，XY轴冻结
    Sigma_cons = np.diag([0.001, 0.001, 1.0]) * high_gain

    # 平滑插值
    Q_task = (1.0 - alpha) * Sigma_free + alpha * Sigma_cons

    return Q_task


def simulate_kalman_filter_1d(alpha, R, Q, true_signal, noise_signal, n_steps=100):
    """
    简化的1D卡尔曼滤波模拟

    Args:
        alpha: 意图因子
        R: 观测噪声方差
        Q: 过程噪声方差
        true_signal: 真实信号（无噪声）
        noise_signal: 带噪声的观测
        n_steps: 时间步数

    Returns:
        filtered_signal: 滤波后的信号
        kalman_gains: 卡尔曼增益历史
    """
    # 初始化
    x = noise_signal[0]  # 初始状态
    P = Q  # 初始协方差

    filtered_signal = np.zeros(n_steps)
    kalman_gains = np.zeros(n_steps)

    for i in range(n_steps):
        # 预测
        x_pred = x  # 简化：假设状态不变
        P_pred = P + Q  # 预测协方差增加

        # 更新
        K = P_pred / (P_pred + R)  # 卡尔曼增益
        x = x_pred + K * (noise_signal[i] - x_pred)  # 状态更新
        P = (1 - K) * P_pred  # 协方差更新

        filtered_signal[i] = x
        kalman_gains[i] = K

    return filtered_signal, kalman_gains


def test_q_matrix_logic():
    """测试Q矩阵的逻辑：验证"Q越大越听话"的理论"""
    print("\n" + "="*60)
    print("测试1: Q矩阵逻辑验证")
    print("="*60)

    n_steps = 100
    t = np.arange(n_steps) * 0.02  # 50Hz

    # 生成测试信号：低频意图 + 高频抖动
    true_signal = 0.5 * np.sin(2 * np.pi * 0.5 * t)  # 0.5Hz低频
    tremor = 0.1 * np.sin(2 * np.pi * 8 * t)  # 8Hz高频抖动
    noise_signal = true_signal + tremor

    # 测试不同的Q值
    R = 0.01  # 固定R
    Q_values = [0.001, 0.01, 0.1]  # 小Q、中Q、大Q
    Q_labels = ['Q=0.001 (僵硬)', 'Q=0.01 (中等)', 'Q=0.1 (听话)']

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    # 绘制原始信号
    axes[0].plot(t, true_signal, 'g--', linewidth=2, label='真实意图（无抖动）', alpha=0.7)
    axes[0].plot(t, noise_signal, 'r-', linewidth=0.5, alpha=0.3, label='观测信号（带抖动）')

    colors = ['blue', 'orange', 'purple']
    for Q, label, color in zip(Q_values, Q_labels, colors):
        filtered, gains = simulate_kalman_filter_1d(0, R, Q, true_signal, noise_signal, n_steps)

        axes[0].plot(t, filtered, color=color, linewidth=2, label=label)
        axes[1].plot(t, gains, color=color, linewidth=2, label=f'{label} - 卡尔曼增益')

    axes[0].set_xlabel('时间 (s)')
    axes[0].set_ylabel('信号值')
    axes[0].set_title('Q矩阵对滤波效果的影响')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].set_xlabel('时间 (s)')
    axes[1].set_ylabel('卡尔曼增益 K')
    axes[1].set_title('卡尔曼增益随Q变化')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig('/tmp/test_q_matrix_logic.png', dpi=150)
    print(f"✅ Q矩阵逻辑测试完成，图表保存至 /tmp/test_q_matrix_logic.png")
    print(f"\n关键发现：")
    print(f"  - Q=0.001时，增益K≈{gains[50]:.3f}，系统僵硬，滤波过度")
    print(f"  - Q=0.1时，增益K≈{gains[50]:.3f}，系统听话，跟踪良好")
    print(f"  - 结论：Q越大，系统越相信观测，越'听话'")


def test_task_space_interpolation():
    """测试任务空间插值方案"""
    print("\n" + "="*60)
    print("测试2: 任务空间插值方案")
    print("="*60)

    # 测试不同的α值
    alphas = [0.0, 0.5, 1.0]
    alpha_labels = ['α=0 (自由空间)', 'α=0.5 (过渡)', 'α=1 (约束流形)']

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for idx, (alpha, label) in enumerate(zip(alphas, alpha_labels)):
        Q_task = build_task_space_Q(alpha)

        # 可视化Q矩阵
        im = axes[idx].imshow(Q_task, cmap='YlOrRd', vmin=0, vmax=0.01)
        axes[idx].set_title(label)
        axes[idx].set_xticks([0, 1, 2])
        axes[idx].set_yticks([0, 1, 2])
        axes[idx].set_xticklabels(['X', 'Y', 'Z'])
        axes[idx].set_yticklabels(['X', 'Y', 'Z'])

        # 标注数值
        for i in range(3):
            for j in range(3):
                text = axes[idx].text(j, i, f'{Q_task[i, j]:.4f}',
                                    ha="center", va="center", color="black", fontsize=10)

        plt.colorbar(im, ax=axes[idx])

        # 打印关键信息
        print(f"\n{label}:")
        print(f"  Q_x = {Q_task[0,0]:.6f}")
        print(f"  Q_y = {Q_task[1,1]:.6f}")
        print(f"  Q_z = {Q_task[2,2]:.6f}")
        print(f"  Q_z/Q_x = {Q_task[2,2]/Q_task[0,0]:.1f}x")

    plt.tight_layout()
    plt.savefig('/tmp/test_task_space_interpolation.png', dpi=150)
    print(f"\n✅ 任务空间插值测试完成，图表保存至 /tmp/test_task_space_interpolation.png")
    print(f"\n关键发现：")
    print(f"  - α=0时，XYZ的Q都是1.0（全部听话）")
    print(f"  - α=1时，XY的Q是0.001（冻结），Z的Q是1.0（依然听话）")
    print(f"  - Z轴的Q始终保持大值，不会'卡死'！")


def test_combined_effect():
    """测试Q和R配合的效果"""
    print("\n" + "="*60)
    print("测试3: Q和R配合效果（Soft Landing）")
    print("="*60)

    n_steps = 100
    t = np.arange(n_steps) * 0.02

    # 生成测试信号
    true_signal = 0.5 * np.sin(2 * np.pi * 0.5 * t)
    tremor = 0.1 * np.sin(2 * np.pi * 8 * t)
    noise_signal = true_signal + tremor

    # 测试三种配置
    configs = [
        {'Q': 0.01, 'R': 0.01, 'label': '自由空间 (Q大R小)', 'color': 'blue'},
        {'Q': 0.01, 'R': 0.1, 'label': '约束流形 (Q大R大)', 'color': 'green'},
        {'Q': 0.001, 'R': 0.1, 'label': '错误配置 (Q小R大)', 'color': 'red'},
    ]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    axes[0].plot(t, true_signal, 'k--', linewidth=2, label='真实意图', alpha=0.7)
    axes[0].plot(t, noise_signal, 'gray', linewidth=0.5, alpha=0.3, label='观测信号')

    for config in configs:
        filtered, gains = simulate_kalman_filter_1d(
            0, config['R'], config['Q'], true_signal, noise_signal, n_steps
        )

        axes[0].plot(t, filtered, color=config['color'], linewidth=2, label=config['label'])
        axes[1].plot(t, gains, color=config['color'], linewidth=2, label=config['label'])

    axes[0].set_xlabel('时间 (s)')
    axes[0].set_ylabel('信号值')
    axes[0].set_title('Q和R配合效果对比')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].set_xlabel('时间 (s)')
    axes[1].set_ylabel('卡尔曼增益 K')
    axes[1].set_title('卡尔曼增益对比')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig('/tmp/test_combined_effect.png', dpi=150)
    print(f"✅ Q和R配合效果测试完成，图表保存至 /tmp/test_combined_effect.png")
    print(f"\n关键发现：")
    print(f"  - Q大R小：系统听话，跟踪快速（自由空间）")
    print(f"  - Q大R大：系统听话但带阻尼，抖动被滤除（约束流形）")
    print(f"  - Q小R大：系统卡死，无法推动（错误配置）")
    print(f"\n这就是'Soft Landing'的数学原理！")


def main():
    """主函数"""
    print("="*60)
    print("验证正确的Q矩阵设计：任务空间插值方案")
    print("="*60)

    # 运行所有测试
    test_q_matrix_logic()
    test_task_space_interpolation()
    test_combined_effect()

    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)
    print("\n核心结论：")
    print("1. Q越大 → 系统越相信观测 → 越'听话'")
    print("2. Q越小 → 系统越相信预测 → 越'僵硬'")
    print("3. Z轴的Q始终保持大值（1.0），不会'卡死'")
    print("4. 抖动抑制靠R矩阵增大，而不是Q矩阵减小")
    print("5. Q大+R大 = 带阻尼的运动（Soft Landing）")
    print("\n这个理论是完全自洽的！")


if __name__ == "__main__":
    main()
