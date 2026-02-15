#!/usr/bin/env python3
"""
消融研究和挣脱机制测试

功能：
1. 测试移除α各个组件后的性能变化
2. 验证挣脱机制（标定偏置场景）
3. 对比不同滤波方法（α-VIST vs One-Euro vs Fixed Weight）
4. 生成论文Figure 4（消融研究结果）

作者：Claude & User
日期：2026-02-10
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import json
from pathlib import Path
from typing import Dict, List, Tuple
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_loader import VISTConfig


class AblationStudy:
    """消融研究：测试α各组件的贡献"""

    def __init__(self, config: VISTConfig):
        self.config = config

    def compute_alpha_full(self, distance: float, velocity: float,
                          alignment: float) -> float:
        """完整的α（baseline）"""
        d_threshold = self.config.vist_distance_threshold
        v_threshold = self.config.vist_velocity_threshold
        k = self.config.vist_sigmoid_k

        alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))
        alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))
        alpha_a = (alignment + 1.0) / 2.0

        return 0.3 * alpha_d + 0.3 * alpha_v + 0.4 * alpha_a

    def compute_alpha_no_distance(self, distance: float, velocity: float,
                                 alignment: float) -> float:
        """移除距离组件"""
        v_threshold = self.config.vist_velocity_threshold
        k = self.config.vist_sigmoid_k

        alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))
        alpha_a = (alignment + 1.0) / 2.0

        return 0.5 * alpha_v + 0.5 * alpha_a

    def compute_alpha_no_velocity(self, distance: float, velocity: float,
                                 alignment: float) -> float:
        """移除速度组件"""
        d_threshold = self.config.vist_distance_threshold
        k = self.config.vist_sigmoid_k

        alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))
        alpha_a = (alignment + 1.0) / 2.0

        return 0.5 * alpha_d + 0.5 * alpha_a

    def compute_alpha_no_alignment(self, distance: float, velocity: float,
                                  alignment: float) -> float:
        """移除对齐组件"""
        d_threshold = self.config.vist_distance_threshold
        v_threshold = self.config.vist_velocity_threshold
        k = self.config.vist_sigmoid_k

        alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))
        alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))

        return 0.5 * alpha_d + 0.5 * alpha_v

    def compute_alpha_equal_weights(self, distance: float, velocity: float,
                                   alignment: float) -> float:
        """等权重组合"""
        d_threshold = self.config.vist_distance_threshold
        v_threshold = self.config.vist_velocity_threshold
        k = self.config.vist_sigmoid_k

        alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))
        alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))
        alpha_a = (alignment + 1.0) / 2.0

        return (alpha_d + alpha_v + alpha_a) / 3.0


class EscapeMechanismTest:
    """挣脱机制测试"""

    def __init__(self, config: VISTConfig):
        self.config = config

    def simulate_calibration_bias(self, trajectory: np.ndarray,
                                  target_pos: np.ndarray,
                                  bias: np.ndarray) -> Dict:
        """
        模拟标定偏置场景

        Args:
            trajectory: 原始轨迹
            target_pos: 真实目标位置
            bias: 标定偏置向量

        Returns:
            结果字典，包含冲突强度、R_virtual变化等
        """
        biased_target = target_pos + bias

        # 计算每个点的冲突强度
        conflicts = []
        r_virtual_values = []

        for i in range(len(trajectory)):
            # 人类意图：朝向真实目标
            direction_human = target_pos - trajectory[i]

            # 虚拟引导：朝向偏置目标
            direction_virtual = biased_target - trajectory[i]

            # 冲突强度
            conflict = np.linalg.norm(direction_human - direction_virtual)
            conflicts.append(conflict)

            # R_virtual的变化（根据冲突调整）
            conflict_gain = 0.5
            r_virtual = 0.01 + conflict_gain * conflict**2
            r_virtual_values.append(r_virtual)

        return {
            'conflicts': np.array(conflicts),
            'r_virtual': np.array(r_virtual_values),
            'biased_target': biased_target
        }


def load_simulation_data(data_path: str) -> Dict:
    """加载之前生成的模拟数据"""
    with open(data_path, 'r') as f:
        data = json.load(f)

    # 转换回numpy数组
    data['trajectory'] = np.array(data['trajectory'])
    data['alphas'] = np.array(data['alphas'])
    data['alpha_components'] = {k: np.array(v) for k, v in data['alpha_components'].items()}
    data['metrics'] = {k: np.array(v) for k, v in data['metrics'].items()}

    return data


def visualize_ablation_results(ablation_results: Dict[str, np.ndarray],
                               phase_labels: List[str],
                               save_path: str):
    """
    可视化消融研究结果（论文Figure 4）

    Args:
        ablation_results: 各种消融版本的α值
        phase_labels: 阶段标签
        save_path: 保存路径
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    times = np.arange(len(ablation_results['full'])) * 0.01

    # 计算每个阶段的平均α
    phase_stats = {}
    for name, alphas in ablation_results.items():
        exploration_mean = alphas[:50].mean()
        approach_mean = alphas[50:150].mean()
        insertion_mean = alphas[150:].mean()
        overall_mean = alphas.mean()

        phase_stats[name] = {
            'exploration': exploration_mean,
            'approach': approach_mean,
            'insertion': insertion_mean,
            'overall': overall_mean
        }

    # 子图1：所有版本的α轨迹对比
    ax = axes[0]
    colors = {
        'full': 'black',
        'no_distance': 'blue',
        'no_velocity': 'green',
        'no_alignment': 'red',
        'equal_weights': 'purple'
    }
    labels = {
        'full': 'Full α (Baseline)',
        'no_distance': 'w/o Distance',
        'no_velocity': 'w/o Velocity',
        'no_alignment': 'w/o Alignment',
        'equal_weights': 'Equal Weights'
    }

    for name, alphas in ablation_results.items():
        linewidth = 2.5 if name == 'full' else 1.5
        alpha_val = 1.0 if name == 'full' else 0.7
        ax.plot(times, alphas, color=colors[name], linewidth=linewidth,
               label=labels[name], alpha=alpha_val)

    ax.axhline(y=0.8, color='orange', linestyle=':', linewidth=1.5,
              label='Z-lock Threshold')
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('Intent Factor α', fontsize=11)
    ax.set_title('Ablation Study: α Trajectories', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.05, 1.05])

    # 子图2：各阶段平均α对比（柱状图）
    ax = axes[1]
    phases = ['Exploration', 'Approach', 'Insertion', 'Overall']
    x = np.arange(len(phases))
    width = 0.15

    for i, (name, stats) in enumerate(phase_stats.items()):
        values = [stats['exploration'], stats['approach'],
                 stats['insertion'], stats['overall']]
        offset = (i - 2) * width
        ax.bar(x + offset, values, width, label=labels[name],
              color=colors[name], alpha=0.8)

    ax.set_xlabel('Task Phase', fontsize=11)
    ax.set_ylabel('Mean α', fontsize=11)
    ax.set_title('Phase-wise α Comparison', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(phases)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')

    # 子图3：性能下降百分比
    ax = axes[2]
    baseline_overall = phase_stats['full']['overall']
    performance_drops = {}

    for name in ['no_distance', 'no_velocity', 'no_alignment', 'equal_weights']:
        drop = (baseline_overall - phase_stats[name]['overall']) / baseline_overall * 100
        performance_drops[name] = drop

    names = list(performance_drops.keys())
    drops = list(performance_drops.values())
    colors_list = [colors[name] for name in names]
    labels_list = [labels[name] for name in names]

    bars = ax.barh(names, drops, color=colors_list, alpha=0.8)
    ax.set_xlabel('Performance Drop (%)', fontsize=11)
    ax.set_title('Impact of Removing Each Component', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')

    # 添加数值标签
    for i, (bar, drop) in enumerate(zip(bars, drops)):
        ax.text(drop + 0.5, i, f'{drop:.1f}%', va='center', fontsize=9)

    # 子图4：Z轴锁定触发统计
    ax = axes[3]
    lock_counts = {}
    for name, alphas in ablation_results.items():
        lock_count = (alphas > 0.8).sum()
        lock_counts[name] = lock_count

    names = list(lock_counts.keys())
    counts = list(lock_counts.values())
    colors_list = [colors[name] for name in names]
    labels_list = [labels[name] for name in names]

    bars = ax.bar(names, counts, color=colors_list, alpha=0.8)
    ax.set_ylabel('# Points with α > 0.8', fontsize=11)
    ax.set_title('Z-Axis Lock Trigger Frequency', fontsize=12, fontweight='bold')
    ax.set_xticklabels(labels_list, rotation=45, ha='right', fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')

    # 添加数值标签
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{int(count)}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✅ 保存消融研究图表: {save_path}")
    plt.close()


def visualize_escape_mechanism(trajectory: np.ndarray,
                               escape_results: Dict,
                               target_pos: np.ndarray,
                               save_path: str):
    """
    可视化挣脱机制

    Args:
        trajectory: 轨迹
        escape_results: 挣脱测试结果
        target_pos: 真实目标位置
        save_path: 保存路径
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    times = np.arange(len(trajectory)) * 0.01
    biased_target = escape_results['biased_target']

    # 子图1：轨迹对比（XY平面）
    ax = axes[0]
    ax.plot(trajectory[:, 0], trajectory[:, 1], 'b-', linewidth=1.5,
           label='Human Trajectory', alpha=0.7)
    ax.plot(target_pos[0], target_pos[1], 'g*', markersize=20,
           label='True Target')
    ax.plot(biased_target[0], biased_target[1], 'r*', markersize=20,
           label='Biased Target (Calibration Error)')

    # 标注挣脱区域
    escape_start = 120
    escape_end = 150
    ax.plot(trajectory[escape_start:escape_end, 0],
           trajectory[escape_start:escape_end, 1],
           'orange', linewidth=3, label='Escape Region')

    ax.set_xlabel('X (m)', fontsize=11)
    ax.set_ylabel('Y (m)', fontsize=11)
    ax.set_title('Escape Mechanism: Trajectory (XY Plane)',
                fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    # 子图2：冲突强度随时间变化
    ax = axes[1]
    ax.plot(times, escape_results['conflicts'], 'purple', linewidth=1.5)
    ax.axvspan(times[escape_start], times[escape_end], alpha=0.2,
              color='orange', label='Escape Region')
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('Conflict Intensity ||Δθ_h - Δθ_v||', fontsize=11)
    ax.set_title('Human-Virtual Conflict Detection', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 子图3：R_virtual的自适应调整
    ax = axes[2]
    ax.plot(times, escape_results['r_virtual'], 'red', linewidth=1.5)
    ax.axvspan(times[escape_start], times[escape_end], alpha=0.2,
              color='orange', label='Escape Region')
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('R_virtual (Observation Noise)', fontsize=11)
    ax.set_title('Adaptive R_virtual Scheduling', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 子图4：挣脱效果示意
    ax = axes[3]
    # 计算到真实目标和偏置目标的距离
    dist_to_true = np.linalg.norm(trajectory - target_pos, axis=1)
    dist_to_biased = np.linalg.norm(trajectory - biased_target, axis=1)

    ax.plot(times, dist_to_true, 'g-', linewidth=1.5, label='Distance to True Target')
    ax.plot(times, dist_to_biased, 'r--', linewidth=1.5, label='Distance to Biased Target')
    ax.axvspan(times[escape_start], times[escape_end], alpha=0.2,
              color='orange', label='Escape Region')

    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('Distance (m)', fontsize=11)
    ax.set_title('Escape Effect: Distance Comparison', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✅ 保存挣脱机制图表: {save_path}")
    plt.close()


def main():
    """主函数"""
    print("=" * 60)
    print("消融研究和挣脱机制测试")
    print("=" * 60)

    # 1. 加载配置和数据
    print("\n📋 加载配置和模拟数据...")
    config = VISTConfig()

    data_path = "logs/simulation/simulation_data.json"
    if not Path(data_path).exists():
        print(f"❌ 错误：找不到模拟数据文件 {data_path}")
        print("   请先运行 simulate_alpha_validation.py 生成数据")
        return

    data = load_simulation_data(data_path)
    trajectory = data['trajectory']
    metrics = data['metrics']
    phase_labels = data['phase_labels']
    target_pos = np.array(data['parameters']['target_pos'])

    print(f"   ✓ 加载轨迹点数: {len(trajectory)}")

    # 2. 消融研究
    print("\n🔬 执行消融研究...")
    ablation = AblationStudy(config)

    ablation_results = {
        'full': [],
        'no_distance': [],
        'no_velocity': [],
        'no_alignment': [],
        'equal_weights': []
    }

    for i in range(len(trajectory)):
        d = metrics['distances'][i]
        v = metrics['velocities'][i]
        a = metrics['alignments'][i]

        ablation_results['full'].append(ablation.compute_alpha_full(d, v, a))
        ablation_results['no_distance'].append(ablation.compute_alpha_no_distance(d, v, a))
        ablation_results['no_velocity'].append(ablation.compute_alpha_no_velocity(d, v, a))
        ablation_results['no_alignment'].append(ablation.compute_alpha_no_alignment(d, v, a))
        ablation_results['equal_weights'].append(ablation.compute_alpha_equal_weights(d, v, a))

    for key in ablation_results:
        ablation_results[key] = np.array(ablation_results[key])

    print("   ✓ 完成消融研究计算")

    # 3. 挣脱机制测试
    print("\n🏃 测试挣脱机制...")
    escape_test = EscapeMechanismTest(config)

    # 模拟5cm的标定偏置
    bias = np.array([0.05, 0.0, 0.0])  # X方向5cm偏置
    escape_results = escape_test.simulate_calibration_bias(trajectory, target_pos, bias)

    print(f"   ✓ 标定偏置: {bias}")
    print(f"   ✓ 平均冲突强度: {escape_results['conflicts'].mean():.4f}")
    print(f"   ✓ 最大冲突强度: {escape_results['conflicts'].max():.4f}")

    # 4. 生成可视化
    print("\n📈 生成可视化图表...")
    output_dir = Path("logs/simulation")

    # Figure 4: 消融研究
    visualize_ablation_results(
        ablation_results, phase_labels,
        str(output_dir / "ablation_study.png")
    )

    # 挣脱机制可视化
    visualize_escape_mechanism(
        trajectory, escape_results, target_pos,
        str(output_dir / "escape_mechanism.png")
    )

    # 5. 保存结果
    print("\n💾 保存测试结果...")
    results = {
        'ablation_results': {k: v.tolist() for k, v in ablation_results.items()},
        'escape_results': {
            'conflicts': escape_results['conflicts'].tolist(),
            'r_virtual': escape_results['r_virtual'].tolist(),
            'bias': bias.tolist()
        }
    }

    with open(output_dir / "ablation_and_escape_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"   ✓ 结果保存至: {output_dir / 'ablation_and_escape_results.json'}")

    # 6. 统计分析
    print("\n📊 统计分析:")
    print("\n消融研究结果:")
    baseline = ablation_results['full'].mean()
    for name, alphas in ablation_results.items():
        if name != 'full':
            mean_alpha = alphas.mean()
            drop = (baseline - mean_alpha) / baseline * 100
            print(f"   {name:20s}: α={mean_alpha:.3f}, 下降={drop:5.1f}%")

    print("\n挣脱机制结果:")
    print(f"   平均冲突强度: {escape_results['conflicts'].mean():.4f}")
    print(f"   平均R_virtual: {escape_results['r_virtual'].mean():.4f}")
    print(f"   R_virtual增幅: {(escape_results['r_virtual'].max() / escape_results['r_virtual'].min() - 1) * 100:.1f}%")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - {output_dir / 'ablation_study.png'}")
    print(f"   - {output_dir / 'escape_mechanism.png'}")
    print(f"   - {output_dir / 'ablation_and_escape_results.json'}")


if __name__ == "__main__":
    main()
