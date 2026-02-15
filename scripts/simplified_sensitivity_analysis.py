#!/usr/bin/env python3
"""
简化的参数敏感性分析
专注于α因子计算对参数的敏感性
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Tuple


def compute_alpha_sigmoid(distance: float, velocity: float,
                          distance_threshold: float, velocity_threshold: float,
                          sigmoid_k: float, weights: dict) -> float:
    """Sigmoid方法计算α"""
    # 距离项
    alpha_distance = 1.0 / (1.0 + np.exp(-sigmoid_k * (distance_threshold - distance)))

    # 速度项
    alpha_velocity = 1.0 / (1.0 + np.exp(-sigmoid_k * (velocity_threshold - velocity)))

    # 对齐项（简化为常数）
    alpha_alignment = 0.8

    # 加权融合
    alpha = (weights['distance'] * alpha_distance +
             weights['velocity'] * alpha_velocity +
             weights['alignment'] * alpha_alignment)

    return np.clip(alpha, 0.0, 1.0)


def compute_alpha_paper(distance: float, velocity: float,
                       sigma_d: float, beta_v: float,
                       weights: dict) -> float:
    """论文方法计算α"""
    # 距离项（指数衰减）
    alpha_distance = np.exp(-distance**2 / (2 * sigma_d**2))

    # 速度项（反比例）
    alpha_velocity = 1.0 / (1.0 + beta_v * velocity)

    # 对齐项（简化为常数）
    alpha_alignment = 0.8

    # 加权融合
    alpha = (weights['distance'] * alpha_distance +
             weights['velocity'] * alpha_velocity +
             weights['alignment'] * alpha_alignment)

    return np.clip(alpha, 0.0, 1.0)


def analyze_distance_threshold_sensitivity():
    """分析距离阈值敏感性"""
    print("\n" + "="*60)
    print("分析: 距离阈值敏感性")
    print("="*60)

    # 参数范围
    thresholds = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    distances = np.linspace(0, 0.4, 100)
    velocity = 0.05  # 固定速度
    sigmoid_k = 10.0
    weights = {'distance': 0.3, 'velocity': 0.3, 'alignment': 0.4}

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 左图：α vs 距离（不同阈值）
    ax = axes[0]
    for threshold in thresholds:
        alphas = [compute_alpha_sigmoid(d, velocity, threshold, 0.05, sigmoid_k, weights)
                 for d in distances]
        ax.plot(distances, alphas, label=f'threshold={threshold:.2f}m', linewidth=2)

    ax.set_xlabel('Distance to Target (m)', fontsize=12)
    ax.set_ylabel('Intent Factor α', fontsize=12)
    ax.set_title('α vs Distance for Different Thresholds', fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 右图：敏感性热图（α在特定距离下的变化）
    ax = axes[1]
    test_distances = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    sensitivity_matrix = np.zeros((len(test_distances), len(thresholds)))

    for i, test_dist in enumerate(test_distances):
        for j, threshold in enumerate(thresholds):
            alpha = compute_alpha_sigmoid(test_dist, velocity, threshold, 0.05, sigmoid_k, weights)
            sensitivity_matrix[i, j] = alpha

    im = ax.imshow(sensitivity_matrix, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=1)
    ax.set_xticks(range(len(thresholds)))
    ax.set_xticklabels([f'{t:.2f}' for t in thresholds])
    ax.set_yticks(range(len(test_distances)))
    ax.set_yticklabels([f'{d:.2f}' for d in test_distances])
    ax.set_xlabel('Distance Threshold (m)', fontsize=12)
    ax.set_ylabel('Actual Distance (m)', fontsize=12)
    ax.set_title('α Sensitivity Heatmap', fontsize=13)
    plt.colorbar(im, ax=ax, label='α value')

    plt.tight_layout()
    return fig


def analyze_sigmoid_k_sensitivity():
    """分析Sigmoid斜率敏感性"""
    print("\n" + "="*60)
    print("分析: Sigmoid斜率k敏感性")
    print("="*60)

    # 参数范围
    k_values = [5, 10, 15, 20, 25, 30]
    distances = np.linspace(0, 0.4, 100)
    velocity = 0.05
    distance_threshold = 0.15
    weights = {'distance': 0.3, 'velocity': 0.3, 'alignment': 0.4}

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 左图：α vs 距离（不同k值）
    ax = axes[0]
    for k in k_values:
        alphas = [compute_alpha_sigmoid(d, velocity, distance_threshold, 0.05, k, weights)
                 for d in distances]
        ax.plot(distances, alphas, label=f'k={k}', linewidth=2)

    ax.set_xlabel('Distance to Target (m)', fontsize=12)
    ax.set_ylabel('Intent Factor α', fontsize=12)
    ax.set_title('α vs Distance for Different k Values', fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])
    ax.axvline(x=distance_threshold, color='red', linestyle='--', alpha=0.5, label='Threshold')

    # 右图：转换陡峭度对比
    ax = axes[1]
    # 计算α从0.2到0.8的距离范围
    transition_widths = []
    for k in k_values:
        alphas = np.array([compute_alpha_sigmoid(d, velocity, distance_threshold, 0.05, k, weights)
                          for d in distances])
        # 找到α=0.2和α=0.8的距离
        idx_02 = np.argmin(np.abs(alphas - 0.2))
        idx_08 = np.argmin(np.abs(alphas - 0.8))
        width = abs(distances[idx_08] - distances[idx_02])
        transition_widths.append(width)

    ax.bar(range(len(k_values)), transition_widths, color='steelblue', alpha=0.7)
    ax.set_xticks(range(len(k_values)))
    ax.set_xticklabels([f'{k}' for k in k_values])
    ax.set_xlabel('Sigmoid k', fontsize=12)
    ax.set_ylabel('Transition Width (m)', fontsize=12)
    ax.set_title('Transition Width (α: 0.2→0.8)', fontsize=13)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    return fig


def analyze_weight_sensitivity():
    """分析权重敏感性"""
    print("\n" + "="*60)
    print("分析: 权重敏感性")
    print("="*60)

    # 参数范围
    distance_weights = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    distances = np.linspace(0, 0.4, 100)
    velocity = 0.05
    distance_threshold = 0.15
    sigmoid_k = 10.0

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 左图：α vs 距离（不同距离权重）
    ax = axes[0]
    for w_dist in distance_weights:
        w_vel = 0.3
        w_align = 1.0 - w_dist - w_vel
        if w_align < 0:
            w_align = 0.1
            w_vel = 1.0 - w_dist - w_align

        weights = {'distance': w_dist, 'velocity': w_vel, 'alignment': w_align}
        alphas = [compute_alpha_sigmoid(d, velocity, distance_threshold, 0.05, sigmoid_k, weights)
                 for d in distances]
        ax.plot(distances, alphas, label=f'w_dist={w_dist:.1f}', linewidth=2)

    ax.set_xlabel('Distance to Target (m)', fontsize=12)
    ax.set_ylabel('Intent Factor α', fontsize=12)
    ax.set_title('α vs Distance for Different Distance Weights', fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 右图：权重对α范围的影响
    ax = axes[1]
    alpha_ranges = []
    for w_dist in distance_weights:
        w_vel = 0.3
        w_align = 1.0 - w_dist - w_vel
        if w_align < 0:
            w_align = 0.1
            w_vel = 1.0 - w_dist - w_align

        weights = {'distance': w_dist, 'velocity': w_vel, 'alignment': w_align}
        alphas = [compute_alpha_sigmoid(d, velocity, distance_threshold, 0.05, sigmoid_k, weights)
                 for d in distances]
        alpha_range = max(alphas) - min(alphas)
        alpha_ranges.append(alpha_range)

    ax.bar(range(len(distance_weights)), alpha_ranges, color='coral', alpha=0.7)
    ax.set_xticks(range(len(distance_weights)))
    ax.set_xticklabels([f'{w:.1f}' for w in distance_weights])
    ax.set_xlabel('Distance Weight', fontsize=12)
    ax.set_ylabel('α Range (max - min)', fontsize=12)
    ax.set_title('Impact of Distance Weight on α Range', fontsize=13)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    return fig


def analyze_method_comparison():
    """对比Sigmoid和论文方法的参数敏感性"""
    print("\n" + "="*60)
    print("分析: 方法对比")
    print("="*60)

    distances = np.linspace(0, 0.4, 100)
    velocities = np.linspace(0, 0.15, 100)

    # Sigmoid参数
    distance_threshold = 0.15
    velocity_threshold = 0.05
    sigmoid_k = 10.0

    # 论文方法参数
    sigma_d = 0.1
    beta_v = 10.0

    weights = {'distance': 0.3, 'velocity': 0.3, 'alignment': 0.4}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. α vs 距离（固定速度）
    ax = axes[0, 0]
    velocity = 0.05
    alphas_sigmoid = [compute_alpha_sigmoid(d, velocity, distance_threshold, velocity_threshold,
                                           sigmoid_k, weights) for d in distances]
    alphas_paper = [compute_alpha_paper(d, velocity, sigma_d, beta_v, weights) for d in distances]

    ax.plot(distances, alphas_sigmoid, 'b-', label='Sigmoid', linewidth=2)
    ax.plot(distances, alphas_paper, 'r--', label='Paper', linewidth=2)
    ax.set_xlabel('Distance (m)', fontsize=12)
    ax.set_ylabel('α', fontsize=12)
    ax.set_title('α vs Distance (velocity=0.05 m/s)', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 2. α vs 速度（固定距离）
    ax = axes[0, 1]
    distance = 0.15
    alphas_sigmoid = [compute_alpha_sigmoid(distance, v, distance_threshold, velocity_threshold,
                                           sigmoid_k, weights) for v in velocities]
    alphas_paper = [compute_alpha_paper(distance, v, sigma_d, beta_v, weights) for v in velocities]

    ax.plot(velocities, alphas_sigmoid, 'b-', label='Sigmoid', linewidth=2)
    ax.plot(velocities, alphas_paper, 'r--', label='Paper', linewidth=2)
    ax.set_xlabel('Velocity (m/s)', fontsize=12)
    ax.set_ylabel('α', fontsize=12)
    ax.set_title('α vs Velocity (distance=0.15 m)', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 3. 2D热图：Sigmoid方法
    ax = axes[1, 0]
    D, V = np.meshgrid(distances, velocities)
    alphas_sigmoid_2d = np.zeros_like(D)
    for i in range(len(velocities)):
        for j in range(len(distances)):
            alphas_sigmoid_2d[i, j] = compute_alpha_sigmoid(
                D[i, j], V[i, j], distance_threshold, velocity_threshold, sigmoid_k, weights)

    im = ax.contourf(D, V, alphas_sigmoid_2d, levels=20, cmap='RdYlGn_r')
    ax.set_xlabel('Distance (m)', fontsize=12)
    ax.set_ylabel('Velocity (m/s)', fontsize=12)
    ax.set_title('Sigmoid Method: α(distance, velocity)', fontsize=13)
    plt.colorbar(im, ax=ax, label='α')

    # 4. 2D热图：论文方法
    ax = axes[1, 1]
    alphas_paper_2d = np.zeros_like(D)
    for i in range(len(velocities)):
        for j in range(len(distances)):
            alphas_paper_2d[i, j] = compute_alpha_paper(
                D[i, j], V[i, j], sigma_d, beta_v, weights)

    im = ax.contourf(D, V, alphas_paper_2d, levels=20, cmap='RdYlGn_r')
    ax.set_xlabel('Distance (m)', fontsize=12)
    ax.set_ylabel('Velocity (m/s)', fontsize=12)
    ax.set_title('Paper Method: α(distance, velocity)', fontsize=13)
    plt.colorbar(im, ax=ax, label='α')

    plt.tight_layout()
    return fig


def main():
    """主函数"""
    print("="*60)
    print("参数敏感性分析")
    print("="*60)

    output_dir = Path("logs/sensitivity_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 距离阈值敏感性
    fig1 = analyze_distance_threshold_sensitivity()
    fig1.savefig(output_dir / "sensitivity_distance_threshold.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'sensitivity_distance_threshold.png'}")
    plt.close(fig1)

    # 2. Sigmoid斜率敏感性
    fig2 = analyze_sigmoid_k_sensitivity()
    fig2.savefig(output_dir / "sensitivity_sigmoid_k.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'sensitivity_sigmoid_k.png'}")
    plt.close(fig2)

    # 3. 权重敏感性
    fig3 = analyze_weight_sensitivity()
    fig3.savefig(output_dir / "sensitivity_weights.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'sensitivity_weights.png'}")
    plt.close(fig3)

    # 4. 方法对比
    fig4 = analyze_method_comparison()
    fig4.savefig(output_dir / "method_comparison_2d.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'method_comparison_2d.png'}")
    plt.close(fig4)

    print("\n" + "="*60)
    print("✅ 参数敏感性分析完成!")
    print("="*60)
    print(f"\n查看结果:")
    print(f"  - 距离阈值敏感性: {output_dir / 'sensitivity_distance_threshold.png'}")
    print(f"  - Sigmoid斜率敏感性: {output_dir / 'sensitivity_sigmoid_k.png'}")
    print(f"  - 权重敏感性: {output_dir / 'sensitivity_weights.png'}")
    print(f"  - 方法对比2D: {output_dir / 'method_comparison_2d.png'}")


if __name__ == "__main__":
    main()
