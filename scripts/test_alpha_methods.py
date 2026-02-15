#!/usr/bin/env python3
"""
测试不同配置的α计算效果

对比sigmoid方法和论文方法的α轨迹
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_loader import VISTConfig


def compute_alpha_sigmoid(distance, velocity, config):
    """Sigmoid方法计算α"""
    d_threshold = config.vist_distance_threshold
    v_threshold = config.vist_velocity_threshold
    k = config.vist_sigmoid_k

    # 距离项
    alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))

    # 速度项
    alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))

    # 简化：假设对齐项为1
    alpha_a = 1.0

    # 加权平均
    weights = config.vist_alpha_weights
    alpha = weights['distance'] * alpha_d + weights['velocity'] * alpha_v + weights['alignment'] * alpha_a

    return alpha, alpha_d, alpha_v, alpha_a


def compute_alpha_paper(distance, velocity, config):
    """论文方法计算α"""
    sigma_d = config.vist_alpha_sigma_d
    beta_v = config.vist_alpha_beta_v

    # 距离项：指数衰减
    alpha_d = np.exp(-distance**2 / (2 * sigma_d**2))

    # 速度项：反比例
    alpha_v = 1.0 / (1.0 + beta_v * velocity)

    # 简化：假设对齐项为1
    alpha_a = 1.0

    # 加权平均
    weights = config.vist_alpha_weights
    alpha = weights['distance'] * alpha_d + weights['velocity'] * alpha_v + weights['alignment'] * alpha_a

    return alpha, alpha_d, alpha_v, alpha_a


def test_alpha_comparison():
    """对比两种α计算方法"""
    print("=" * 60)
    print("α计算方法对比测试")
    print("=" * 60)

    # 加载两种配置
    print("\n📋 加载配置...")
    config_baseline = VISTConfig(config_path="config/system_config.yaml")
    config_paper = VISTConfig(config_path="config/system_config_paper.yaml")

    print(f"✅ Baseline配置: alpha_computation_method = {config_baseline.vist_alpha_computation_method}")
    print(f"✅ 论文配置: alpha_computation_method = {config_paper.vist_alpha_computation_method}")

    # 测试场景1: 距离变化,速度固定
    print("\n" + "=" * 60)
    print("场景1: 距离变化 (速度=0.01 m/s)")
    print("=" * 60)

    distances = np.linspace(0, 0.3, 100)
    velocity = 0.01

    alphas_sigmoid = []
    alphas_paper = []

    for d in distances:
        alpha_s, _, _, _ = compute_alpha_sigmoid(d, velocity, config_baseline)
        alpha_p, _, _, _ = compute_alpha_paper(d, velocity, config_paper)
        alphas_sigmoid.append(alpha_s)
        alphas_paper.append(alpha_p)

    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(distances, alphas_sigmoid, 'b-', label='Sigmoid方法', linewidth=2)
    plt.plot(distances, alphas_paper, 'r--', label='论文方法', linewidth=2)
    plt.xlabel('距离 (m)')
    plt.ylabel('α')
    plt.title('α vs 距离 (速度=0.01 m/s)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 测试场景2: 速度变化,距离固定
    print("\n场景2: 速度变化 (距离=0.05 m)")

    velocities = np.linspace(0, 0.1, 100)
    distance = 0.05

    alphas_sigmoid = []
    alphas_paper = []

    for v in velocities:
        alpha_s, _, _, _ = compute_alpha_sigmoid(distance, v, config_baseline)
        alpha_p, _, _, _ = compute_alpha_paper(distance, v, config_paper)
        alphas_sigmoid.append(alpha_s)
        alphas_paper.append(alpha_p)

    plt.subplot(1, 2, 2)
    plt.plot(velocities, alphas_sigmoid, 'b-', label='Sigmoid方法', linewidth=2)
    plt.plot(velocities, alphas_paper, 'r--', label='论文方法', linewidth=2)
    plt.xlabel('速度 (m/s)')
    plt.ylabel('α')
    plt.title('α vs 速度 (距离=0.05 m)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('logs/alpha_comparison.png', dpi=150)
    print(f"\n✅ 图表已保存: logs/alpha_comparison.png")

    # 测试场景3: 典型任务轨迹
    print("\n" + "=" * 60)
    print("场景3: 典型USB插入任务轨迹")
    print("=" * 60)

    # 模拟轨迹: 从远到近,速度从快到慢
    t = np.linspace(0, 10, 200)  # 10秒
    distances = 0.3 * np.exp(-0.3 * t)  # 指数接近
    velocities = 0.1 * np.exp(-0.5 * t)  # 速度递减

    alphas_sigmoid = []
    alphas_paper = []
    alpha_d_sigmoid = []
    alpha_v_sigmoid = []
    alpha_d_paper = []
    alpha_v_paper = []

    for d, v in zip(distances, velocities):
        alpha_s, ad_s, av_s, _ = compute_alpha_sigmoid(d, v, config_baseline)
        alpha_p, ad_p, av_p, _ = compute_alpha_paper(d, v, config_paper)
        alphas_sigmoid.append(alpha_s)
        alphas_paper.append(alpha_p)
        alpha_d_sigmoid.append(ad_s)
        alpha_v_sigmoid.append(av_s)
        alpha_d_paper.append(ad_p)
        alpha_v_paper.append(av_p)

    plt.figure(figsize=(15, 10))

    # 总α对比
    plt.subplot(3, 2, 1)
    plt.plot(t, alphas_sigmoid, 'b-', label='Sigmoid方法', linewidth=2)
    plt.plot(t, alphas_paper, 'r--', label='论文方法', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('α')
    plt.title('总α轨迹对比')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 距离轨迹
    plt.subplot(3, 2, 2)
    plt.plot(t, distances, 'g-', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('距离 (m)')
    plt.title('距离轨迹')
    plt.grid(True, alpha=0.3)

    # α_distance对比
    plt.subplot(3, 2, 3)
    plt.plot(t, alpha_d_sigmoid, 'b-', label='Sigmoid', linewidth=2)
    plt.plot(t, alpha_d_paper, 'r--', label='论文', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('α_distance')
    plt.title('距离项对比')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 速度轨迹
    plt.subplot(3, 2, 4)
    plt.plot(t, velocities, 'g-', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('速度 (m/s)')
    plt.title('速度轨迹')
    plt.grid(True, alpha=0.3)

    # α_velocity对比
    plt.subplot(3, 2, 5)
    plt.plot(t, alpha_v_sigmoid, 'b-', label='Sigmoid', linewidth=2)
    plt.plot(t, alpha_v_paper, 'r--', label='论文', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('α_velocity')
    plt.title('速度项对比')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # α差异
    plt.subplot(3, 2, 6)
    diff = np.array(alphas_sigmoid) - np.array(alphas_paper)
    plt.plot(t, diff, 'purple', linewidth=2)
    plt.xlabel('时间 (s)')
    plt.ylabel('α差异')
    plt.title('Sigmoid - 论文方法')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='k', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('logs/alpha_trajectory_comparison.png', dpi=150)
    print(f"✅ 轨迹图已保存: logs/alpha_trajectory_comparison.png")

    # 统计分析
    print("\n" + "=" * 60)
    print("统计分析")
    print("=" * 60)

    diff_mean = np.mean(np.abs(diff))
    diff_max = np.max(np.abs(diff))
    correlation = np.corrcoef(alphas_sigmoid, alphas_paper)[0, 1]

    print(f"平均绝对差异: {diff_mean:.4f}")
    print(f"最大绝对差异: {diff_max:.4f}")
    print(f"相关系数: {correlation:.4f}")

    if correlation > 0.95:
        print("✅ 两种方法高度相关,可以互换使用")
    elif correlation > 0.85:
        print("⚠️ 两种方法基本一致,但有一定差异")
    else:
        print("❌ 两种方法差异较大,需要进一步调整参数")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)

    # 运行测试
    test_alpha_comparison()

    print("\n💡 提示:")
    print("   1. 查看生成的图表: logs/alpha_comparison.png")
    print("   2. 查看轨迹对比: logs/alpha_trajectory_comparison.png")
    print("   3. 如果两种方法差异较大,可以调整论文方法的参数:")
    print("      - sigma_d: 控制距离敏感度")
    print("      - beta_v: 控制速度敏感度")
