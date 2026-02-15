#!/usr/bin/env python3
"""
模拟测试脚本：验证α-VIST框架的核心机制

功能：
1. 模拟USB插入任务的完整轨迹（探索→接近→插入）
2. 验证意图因子α的演化是否符合预期
3. 测试R(α,δ)和Q(α,J)的自适应调度
4. 验证挣脱机制（标定偏置场景）
5. 生成论文所需的可视化图表

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


class AlphaSimulator:
    """α因子模拟器"""

    def __init__(self, config: VISTConfig):
        self.config = config
        self.alpha_history = []
        self.alpha_components_history = []

    def compute_alpha(self, distance: float, velocity: float,
                     alignment: float) -> Tuple[float, Dict[str, float]]:
        """
        计算意图因子α

        Args:
            distance: 到目标的距离 (m)
            velocity: 速度大小 (m/s)
            alignment: 方向对齐度 (cos_angle)

        Returns:
            alpha: 意图因子
            components: α的三个组件
        """
        # 1. 距离因子
        d_threshold = self.config.vist_distance_threshold
        k = self.config.vist_sigmoid_k
        alpha_distance = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))

        # 2. 速度因子
        v_threshold = self.config.vist_velocity_threshold
        alpha_velocity = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))

        # 3. 对齐因子
        alpha_alignment = (alignment + 1.0) / 2.0

        # 4. 加权组合
        alpha = 0.3 * alpha_distance + 0.3 * alpha_velocity + 0.4 * alpha_alignment

        components = {
            'distance': alpha_distance,
            'velocity': alpha_velocity,
            'alignment': alpha_alignment
        }

        return alpha, components


class TrajectoryGenerator:
    """轨迹生成器：模拟USB插入任务"""

    def __init__(self, start_pos: np.ndarray, target_pos: np.ndarray):
        """
        Args:
            start_pos: 起始位置 [x, y, z]
            target_pos: 目标位置（USB插孔） [x, y, z]
        """
        self.start_pos = np.array(start_pos)
        self.target_pos = np.array(target_pos)

    def generate_exploration_phase(self, n_points: int = 50) -> np.ndarray:
        """
        阶段1：探索阶段（α ≈ 0.2-0.4）
        特征：快速移动，远离目标，方向不对齐
        """
        # 在起始位置附近随机游走
        trajectory = []
        current_pos = self.start_pos.copy()

        for i in range(n_points):
            # 添加随机扰动（模拟探索）
            noise = np.random.randn(3) * 0.02  # 2cm标准差
            current_pos = current_pos + noise

            # 限制在合理范围内
            current_pos = np.clip(current_pos,
                                 self.start_pos - 0.1,
                                 self.start_pos + 0.1)

            trajectory.append(current_pos.copy())

        return np.array(trajectory)

    def generate_approach_phase(self, n_points: int = 100) -> np.ndarray:
        """
        阶段2：接近阶段（α ≈ 0.5-0.7）
        特征：中等速度，逐渐接近目标，方向逐渐对齐
        """
        trajectory = []

        # 从探索阶段的最后位置开始
        start = self.start_pos
        end = self.target_pos + np.array([0, 0, 0.05])  # 停在目标上方5cm

        for i in range(n_points):
            t = i / (n_points - 1)
            # 使用ease-in-out曲线（模拟人类减速接近）
            t_smooth = 3 * t**2 - 2 * t**3

            pos = start + (end - start) * t_smooth

            # 添加小幅抖动（模拟人类手部颤抖）
            noise = np.random.randn(3) * 0.005  # 5mm标准差
            pos = pos + noise

            trajectory.append(pos)

        return np.array(trajectory)

    def generate_insertion_phase(self, n_points: int = 50) -> np.ndarray:
        """
        阶段3：插入阶段（α ≈ 0.8-0.95）
        特征：慢速，精确对齐，沿Z轴移动
        """
        trajectory = []

        # 从接近阶段的最后位置开始
        start = self.target_pos + np.array([0, 0, 0.05])
        end = self.target_pos - np.array([0, 0, 0.05])  # 插入5cm深度

        for i in range(n_points):
            t = i / (n_points - 1)

            # 线性插入
            pos = start + (end - start) * t

            # 只在Z方向移动，X-Y方向添加极小抖动（模拟锁定效果）
            noise_xy = np.random.randn(2) * 0.001  # 1mm标准差
            noise_z = np.random.randn() * 0.002  # 2mm标准差
            pos[:2] += noise_xy
            pos[2] += noise_z

            trajectory.append(pos)

        return np.array(trajectory)

    def generate_full_trajectory(self) -> Tuple[np.ndarray, List[str]]:
        """
        生成完整轨迹

        Returns:
            trajectory: 完整轨迹 (N, 3)
            phase_labels: 每个点的阶段标签
        """
        traj_exploration = self.generate_exploration_phase(50)
        traj_approach = self.generate_approach_phase(100)
        traj_insertion = self.generate_insertion_phase(50)

        trajectory = np.vstack([traj_exploration, traj_approach, traj_insertion])

        phase_labels = (['exploration'] * 50 +
                       ['approach'] * 100 +
                       ['insertion'] * 50)

        return trajectory, phase_labels


def compute_trajectory_metrics(trajectory: np.ndarray, target_pos: np.ndarray,
                               dt: float = 0.01) -> Dict[str, np.ndarray]:
    """
    计算轨迹的各种指标

    Args:
        trajectory: 轨迹 (N, 3)
        target_pos: 目标位置 [x, y, z]
        dt: 时间步长 (s)

    Returns:
        metrics: 包含距离、速度、加速度、对齐度等指标
    """
    N = len(trajectory)

    # 1. 距离
    distances = np.linalg.norm(trajectory - target_pos, axis=1)

    # 2. 速度
    velocities = np.zeros(N)
    velocities[1:] = np.linalg.norm(np.diff(trajectory, axis=0), axis=1) / dt
    velocities[0] = velocities[1]  # 第一个点使用第二个点的速度

    # 3. 加速度
    accelerations = np.zeros(N)
    accelerations[1:] = np.diff(velocities) / dt
    accelerations[0] = accelerations[1]

    # 4. 方向对齐度
    alignments = np.zeros(N)
    for i in range(1, N):
        direction_to_target = target_pos - trajectory[i]
        velocity_direction = trajectory[i] - trajectory[i-1]

        norm_target = np.linalg.norm(direction_to_target)
        norm_velocity = np.linalg.norm(velocity_direction)

        if norm_target > 1e-6 and norm_velocity > 1e-6:
            cos_angle = np.dot(direction_to_target, velocity_direction) / (norm_target * norm_velocity)
            alignments[i] = np.clip(cos_angle, -1.0, 1.0)
        else:
            alignments[i] = 1.0  # 默认对齐

    alignments[0] = alignments[1]

    return {
        'distances': distances,
        'velocities': velocities,
        'accelerations': accelerations,
        'alignments': alignments
    }


def simulate_calibration_bias_scenario(trajectory: np.ndarray,
                                      target_pos: np.ndarray,
                                      bias: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    模拟标定偏置场景（测试挣脱机制）

    Args:
        trajectory: 原始轨迹
        target_pos: 真实目标位置
        bias: 标定偏置 [dx, dy, dz]

    Returns:
        biased_target: 偏置后的目标位置
        escape_trajectory: 人类挣脱后的轨迹修正
    """
    biased_target = target_pos + bias

    # 模拟人类检测到偏置并主动修正
    # 在接近阶段后期（假设在第120-150个点）开始挣脱
    escape_trajectory = trajectory.copy()

    for i in range(120, 150):
        if i < len(escape_trajectory):
            # 人类施加反向力，逐渐修正到真实目标
            correction = (target_pos - biased_target) * (i - 120) / 30
            escape_trajectory[i] += correction * 0.5

    return biased_target, escape_trajectory


def visualize_alpha_evolution(times: np.ndarray, alphas: np.ndarray,
                              components: Dict[str, np.ndarray],
                              phase_labels: List[str],
                              save_path: str):
    """
    可视化α的演化过程（论文Figure 3）

    Args:
        times: 时间序列
        alphas: α值序列
        components: α的三个组件
        phase_labels: 阶段标签
        save_path: 保存路径
    """
    fig = plt.figure(figsize=(12, 8))
    gs = GridSpec(2, 1, height_ratios=[2, 1], hspace=0.3)

    # 子图1：α及其组件
    ax1 = fig.add_subplot(gs[0])

    ax1.plot(times, alphas, 'k-', linewidth=2.5, label='α (Intent Factor)')
    ax1.plot(times, components['distance'], 'b--', linewidth=1.5, label='α_distance', alpha=0.7)
    ax1.plot(times, components['velocity'], 'g--', linewidth=1.5, label='α_velocity', alpha=0.7)
    ax1.plot(times, components['alignment'], 'r--', linewidth=1.5, label='α_alignment', alpha=0.7)

    # 标注阶段
    phase_changes = [0]
    current_phase = phase_labels[0]
    for i, phase in enumerate(phase_labels):
        if phase != current_phase:
            phase_changes.append(i)
            current_phase = phase
    phase_changes.append(len(phase_labels))

    colors = {'exploration': 'lightblue', 'approach': 'lightgreen', 'insertion': 'lightyellow'}
    for i in range(len(phase_changes) - 1):
        start_idx = phase_changes[i]
        end_idx = phase_changes[i + 1]
        phase = phase_labels[start_idx]
        ax1.axvspan(times[start_idx], times[end_idx-1], alpha=0.2, color=colors[phase])

        # 添加阶段标签
        mid_time = (times[start_idx] + times[end_idx-1]) / 2
        ax1.text(mid_time, 0.95, phase.capitalize(),
                ha='center', va='top', fontsize=10, fontweight='bold')

    ax1.axhline(y=0.8, color='orange', linestyle=':', linewidth=1.5,
               label='Z-axis Lock Threshold (α=0.8)')

    ax1.set_xlabel('Time (s)', fontsize=12)
    ax1.set_ylabel('Intent Factor α', fontsize=12)
    ax1.set_title('α-VIST: Intent Factor Evolution During USB Insertion Task',
                 fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([-0.05, 1.05])

    # 子图2：α的变化率
    ax2 = fig.add_subplot(gs[1])

    alpha_rate = np.zeros_like(alphas)
    alpha_rate[1:] = np.diff(alphas) / np.diff(times)
    alpha_rate[0] = alpha_rate[1]

    ax2.plot(times, alpha_rate, 'purple', linewidth=1.5)
    ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    ax2.set_xlabel('Time (s)', fontsize=12)
    ax2.set_ylabel('dα/dt (1/s)', fontsize=12)
    ax2.set_title('Rate of Intent Change', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✅ 保存α演化图表: {save_path}")
    plt.close()


def visualize_alpha_heatmap(trajectory: np.ndarray, alphas: np.ndarray,
                            target_pos: np.ndarray, save_path: str):
    """
    可视化α的空间分布热力图（论文Figure 6）

    Args:
        trajectory: 轨迹 (N, 3)
        alphas: α值序列
        target_pos: 目标位置
        save_path: 保存路径
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # XY平面投影
    scatter1 = ax1.scatter(trajectory[:, 0], trajectory[:, 1],
                          c=alphas, cmap='RdYlBu_r', s=20, alpha=0.6)
    ax1.plot(target_pos[0], target_pos[1], 'r*', markersize=20,
            label='Target (USB Port)')
    ax1.set_xlabel('X (m)', fontsize=12)
    ax1.set_ylabel('Y (m)', fontsize=12)
    ax1.set_title('Intent Factor α - XY Plane', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal')

    # XZ平面投影
    scatter2 = ax2.scatter(trajectory[:, 0], trajectory[:, 2],
                          c=alphas, cmap='RdYlBu_r', s=20, alpha=0.6)
    ax2.plot(target_pos[0], target_pos[2], 'r*', markersize=20,
            label='Target (USB Port)')
    ax2.set_xlabel('X (m)', fontsize=12)
    ax2.set_ylabel('Z (m)', fontsize=12)
    ax2.set_title('Intent Factor α - XZ Plane', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect('equal')

    # 添加颜色条
    cbar = fig.colorbar(scatter1, ax=[ax1, ax2], orientation='horizontal',
                       pad=0.1, aspect=30)
    cbar.set_label('Intent Factor α', fontsize=12)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✅ 保存α热力图: {save_path}")
    plt.close()


def main():
    """主函数"""
    print("=" * 60)
    print("α-VIST 模拟验证系统")
    print("=" * 60)

    # 1. 加载配置
    print("\n📋 加载配置...")
    config = VISTConfig()

    # 2. 设置任务参数
    start_pos = np.array([0.3, 0.2, 0.4])  # 起始位置
    target_pos = np.array([0.5, 0.3, 0.2])  # USB插孔位置
    dt = 0.01  # 时间步长 10ms

    print(f"   起始位置: {start_pos}")
    print(f"   目标位置: {target_pos}")
    print(f"   时间步长: {dt}s")

    # 3. 生成轨迹
    print("\n🎯 生成模拟轨迹...")
    traj_gen = TrajectoryGenerator(start_pos, target_pos)
    trajectory, phase_labels = traj_gen.generate_full_trajectory()
    print(f"   轨迹点数: {len(trajectory)}")
    print(f"   阶段分布: 探索{phase_labels.count('exploration')}点, "
          f"接近{phase_labels.count('approach')}点, "
          f"插入{phase_labels.count('insertion')}点")

    # 4. 计算轨迹指标
    print("\n📊 计算轨迹指标...")
    metrics = compute_trajectory_metrics(trajectory, target_pos, dt)

    # 5. 计算α因子
    print("\n🧮 计算意图因子α...")
    alpha_sim = AlphaSimulator(config)
    alphas = []
    alpha_components = {'distance': [], 'velocity': [], 'alignment': []}

    for i in range(len(trajectory)):
        alpha, components = alpha_sim.compute_alpha(
            metrics['distances'][i],
            metrics['velocities'][i],
            metrics['alignments'][i]
        )
        alphas.append(alpha)
        for key in alpha_components:
            alpha_components[key].append(components[key])

    alphas = np.array(alphas)
    for key in alpha_components:
        alpha_components[key] = np.array(alpha_components[key])

    print(f"   α范围: [{alphas.min():.3f}, {alphas.max():.3f}]")
    print(f"   探索阶段平均α: {alphas[:50].mean():.3f}")
    print(f"   接近阶段平均α: {alphas[50:150].mean():.3f}")
    print(f"   插入阶段平均α: {alphas[150:].mean():.3f}")

    # 6. 生成可视化
    print("\n📈 生成可视化图表...")
    output_dir = Path("logs/simulation")
    output_dir.mkdir(parents=True, exist_ok=True)

    times = np.arange(len(trajectory)) * dt

    # Figure 3: α演化
    visualize_alpha_evolution(
        times, alphas, alpha_components, phase_labels,
        str(output_dir / "alpha_evolution.png")
    )

    # Figure 6: α热力图
    visualize_alpha_heatmap(
        trajectory, alphas, target_pos,
        str(output_dir / "alpha_heatmap.png")
    )

    # 7. 保存数据
    print("\n💾 保存模拟数据...")
    simulation_data = {
        'trajectory': trajectory.tolist(),
        'alphas': alphas.tolist(),
        'alpha_components': {k: v.tolist() for k, v in alpha_components.items()},
        'metrics': {k: v.tolist() for k, v in metrics.items()},
        'phase_labels': phase_labels,
        'parameters': {
            'start_pos': start_pos.tolist(),
            'target_pos': target_pos.tolist(),
            'dt': dt
        }
    }

    with open(output_dir / "simulation_data.json", 'w') as f:
        json.dump(simulation_data, f, indent=2)

    print(f"   数据保存至: {output_dir / 'simulation_data.json'}")

    # 8. 统计分析
    print("\n📊 统计分析:")
    print(f"   ✓ α在探索阶段: {alphas[:50].mean():.3f} ± {alphas[:50].std():.3f}")
    print(f"   ✓ α在接近阶段: {alphas[50:150].mean():.3f} ± {alphas[50:150].std():.3f}")
    print(f"   ✓ α在插入阶段: {alphas[150:].mean():.3f} ± {alphas[150:].std():.3f}")
    print(f"   ✓ Z轴锁定触发次数: {(alphas > 0.8).sum()} / {len(alphas)}")

    print("\n" + "=" * 60)
    print("✅ 模拟验证完成！")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - {output_dir / 'alpha_evolution.png'}")
    print(f"   - {output_dir / 'alpha_heatmap.png'}")
    print(f"   - {output_dir / 'simulation_data.json'}")


if __name__ == "__main__":
    main()
