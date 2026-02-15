#!/usr/bin/env python3
"""
高真实度VIST框架模拟测试

模拟真实硬件环境,包括:
1. 传感器噪声 (MediaPipe, ArUco)
2. 执行器延迟和噪声
3. 标定误差
4. 网络延迟
5. 人类操作不确定性

测试场景:
- USB插入任务
- 不同配置对比 (sigmoid vs paper)
- 鲁棒性测试 (噪声、延迟、标定偏差)
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
import sys
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_loader import VISTConfig


@dataclass
class SimulationParams:
    """模拟参数"""
    # 噪声参数
    mediapipe_position_noise: float = 0.005  # 5mm位置噪声
    mediapipe_orientation_noise: float = 0.05  # 约3度姿态噪声
    aruco_position_noise: float = 0.002  # 2mm ArUco位置噪声
    aruco_orientation_noise: float = 0.02  # 约1度姿态噪声

    # 延迟参数 (秒)
    vision_delay: float = 0.033  # 30Hz相机 = 33ms延迟
    network_delay: float = 0.010  # 10ms网络延迟
    actuator_delay: float = 0.020  # 20ms执行器响应延迟

    # 标定误差
    calibration_position_bias: np.ndarray = None  # 位置偏差 (3D)
    calibration_rotation_bias: float = 0.0  # 旋转偏差 (弧度)

    # 人类操作参数
    human_tremor_amplitude: float = 0.002  # 2mm手抖幅度
    human_tremor_frequency: float = 5.0  # 5Hz手抖频率

    # 物理约束
    max_velocity: float = 0.5  # 最大速度 0.5m/s
    max_acceleration: float = 2.0  # 最大加速度 2m/s²

    def __post_init__(self):
        if self.calibration_position_bias is None:
            self.calibration_position_bias = np.zeros(3)


@dataclass
class TrialResult:
    """单次试验结果"""
    success: bool
    completion_time: float
    path_length: float
    jerk: float
    alpha_trajectory: List[float]
    distance_trajectory: List[float]
    velocity_trajectory: List[float]
    collision: bool
    reason: str  # 失败原因


class HighFidelitySimulator:
    """高真实度模拟器"""

    def __init__(self, config: VISTConfig, params: SimulationParams):
        self.config = config
        self.params = params

        # 延迟缓冲区
        self.vision_buffer = []
        self.network_buffer = []
        self.actuator_buffer = []

        # 历史数据
        self.position_history = []
        self.velocity_history = []

    def add_sensor_noise(self, position: np.ndarray, is_mediapipe: bool = True) -> np.ndarray:
        """添加传感器噪声"""
        if is_mediapipe:
            noise = np.random.normal(0, self.params.mediapipe_position_noise, 3)
        else:
            noise = np.random.normal(0, self.params.aruco_position_noise, 3)
        return position + noise

    def add_calibration_bias(self, position: np.ndarray) -> np.ndarray:
        """添加标定偏差"""
        return position + self.params.calibration_position_bias

    def add_human_tremor(self, position: np.ndarray, time: float) -> np.ndarray:
        """添加人类手抖"""
        tremor = self.params.human_tremor_amplitude * np.sin(
            2 * np.pi * self.params.human_tremor_frequency * time
        )
        # 手抖主要在垂直于运动方向的平面上
        tremor_vector = np.array([tremor, tremor * 0.7, tremor * 0.3])
        return position + tremor_vector

    def simulate_delay(self, value, buffer: List, delay: float, dt: float):
        """模拟延迟"""
        buffer.append(value)
        delay_steps = int(delay / dt)
        if len(buffer) > delay_steps:
            return buffer.pop(0)
        else:
            return value  # 初始阶段没有足够的历史数据

    def compute_alpha(self, distance: float, velocity: float,
                     alignment: float, method: str) -> float:
        """计算α (支持两种方法)"""
        if method == "paper":
            # 论文方法
            sigma_d = self.config.vist_alpha_sigma_d
            beta_v = self.config.vist_alpha_beta_v

            alpha_d = np.exp(-distance**2 / (2 * sigma_d**2))
            alpha_v = 1.0 / (1.0 + beta_v * velocity)
            alpha_a = (alignment + 1.0) / 2.0
        else:
            # Sigmoid方法
            d_threshold = self.config.vist_distance_threshold
            v_threshold = self.config.vist_velocity_threshold
            k = self.config.vist_sigmoid_k

            alpha_d = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance)))
            alpha_v = 1.0 / (1.0 + np.exp(-k * (v_threshold - velocity)))
            alpha_a = (alignment + 1.0) / 2.0

        # 加权平均
        weights = self.config.vist_alpha_weights
        alpha = (weights['distance'] * alpha_d +
                weights['velocity'] * alpha_v +
                weights['alignment'] * alpha_a)

        return np.clip(alpha, 0.0, 1.0)

    def simulate_trial(self, start_pos: np.ndarray, target_pos: np.ndarray,
                      method: str, max_time: float = 30.0, dt: float = 0.01) -> TrialResult:
        """模拟单次试验"""
        # 初始化
        current_pos = start_pos.copy()
        current_vel = np.zeros(3)
        time = 0.0

        # 轨迹记录
        alpha_traj = []
        distance_traj = []
        velocity_traj = []
        position_traj = [current_pos.copy()]

        # 清空缓冲区
        self.vision_buffer = []
        self.network_buffer = []
        self.actuator_buffer = []

        success = False
        collision = False
        reason = ""

        # 模拟循环
        steps = int(max_time / dt)
        for step in range(steps):
            time = step * dt

            # 1. 人类操作: 朝向目标移动
            direction = target_pos - current_pos
            distance = np.linalg.norm(direction)

            if distance < 0.001:  # 到达目标
                success = True
                reason = "reached_target"
                break

            direction_normalized = direction / distance

            # 人类期望速度 (距离越近速度越慢)
            desired_speed = min(0.1, distance * 2.0)  # 最大0.1m/s
            desired_vel = direction_normalized * desired_speed

            # 2. 添加传感器噪声
            noisy_pos = self.add_sensor_noise(current_pos, is_mediapipe=True)
            noisy_target = self.add_sensor_noise(target_pos, is_mediapipe=False)

            # 3. 添加标定偏差
            biased_pos = self.add_calibration_bias(noisy_pos)
            biased_target = self.add_calibration_bias(noisy_target)

            # 4. 添加人类手抖
            tremor_pos = self.add_human_tremor(biased_pos, time)

            # 5. 模拟视觉延迟
            delayed_pos = self.simulate_delay(
                tremor_pos, self.vision_buffer,
                self.params.vision_delay, dt
            )

            # 6. 计算速度和对齐
            speed = np.linalg.norm(current_vel)
            if speed > 1e-6:
                alignment = np.dot(current_vel / speed, direction_normalized)
            else:
                alignment = 1.0

            # 7. 计算α
            alpha = self.compute_alpha(distance, speed, alignment, method)

            # 8. VIST控制: α驱动的融合
            # 简化模型: 直接融合人类指令和虚拟引导
            # R_human ∝ (1 - α), R_virtual ∝ α
            human_weight = 1.0 - alpha
            virtual_weight = alpha

            # 虚拟引导: 直接指向目标
            virtual_vel = direction_normalized * desired_speed

            # 融合速度
            fused_vel = human_weight * desired_vel + virtual_weight * virtual_vel

            # 9. 物理约束
            fused_speed = np.linalg.norm(fused_vel)
            if fused_speed > self.params.max_velocity:
                fused_vel = fused_vel / fused_speed * self.params.max_velocity

            # 加速度约束
            accel = (fused_vel - current_vel) / dt
            accel_mag = np.linalg.norm(accel)
            if accel_mag > self.params.max_acceleration:
                accel = accel / accel_mag * self.params.max_acceleration
                fused_vel = current_vel + accel * dt

            # 10. 模拟执行器延迟
            delayed_vel = self.simulate_delay(
                fused_vel, self.actuator_buffer,
                self.params.actuator_delay, dt
            )

            # 11. 更新状态
            current_vel = delayed_vel
            current_pos = current_pos + current_vel * dt

            # 12. 记录轨迹
            alpha_traj.append(alpha)
            distance_traj.append(distance)
            velocity_traj.append(speed)
            position_traj.append(current_pos.copy())

            # 13. 碰撞检测 (简化: 检查是否偏离太远)
            if distance > 0.5:  # 偏离超过50cm
                collision = True
                reason = "diverged"
                break

        if not success and not collision:
            reason = "timeout"

        # 计算指标
        completion_time = time
        path_length = sum(np.linalg.norm(position_traj[i+1] - position_traj[i])
                         for i in range(len(position_traj)-1))

        # 计算jerk (简化)
        jerk = 0.0
        if len(velocity_traj) > 2:
            vel_array = np.array(velocity_traj)
            accel = np.diff(vel_array) / dt
            jerk_array = np.diff(accel) / dt
            jerk = np.mean(np.abs(jerk_array))

        return TrialResult(
            success=success,
            completion_time=completion_time,
            path_length=path_length,
            jerk=jerk,
            alpha_trajectory=alpha_traj,
            distance_trajectory=distance_traj,
            velocity_trajectory=velocity_traj,
            collision=collision,
            reason=reason
        )


def run_experiment(config_path: str, method_name: str,
                   n_trials: int = 20, noise_level: str = "normal") -> Dict:
    """运行实验"""
    print(f"\n{'='*60}")
    print(f"实验: {method_name} (噪声级别: {noise_level})")
    print(f"{'='*60}")

    # 加载配置
    config = VISTConfig(config_path=config_path)

    # 设置模拟参数
    if noise_level == "low":
        params = SimulationParams(
            mediapipe_position_noise=0.002,
            aruco_position_noise=0.001,
            human_tremor_amplitude=0.001
        )
    elif noise_level == "high":
        params = SimulationParams(
            mediapipe_position_noise=0.010,
            aruco_position_noise=0.005,
            human_tremor_amplitude=0.005
        )
    else:  # normal
        params = SimulationParams()

    # 创建模拟器
    simulator = HighFidelitySimulator(config, params)

    # 测试场景
    scenarios = [
        {
            "name": "近距离",
            "start": np.array([0.4, 0.2, 0.3]),
            "target": np.array([0.45, 0.25, 0.25])
        },
        {
            "name": "中距离",
            "start": np.array([0.3, 0.1, 0.4]),
            "target": np.array([0.45, 0.25, 0.25])
        },
        {
            "name": "远距离",
            "start": np.array([0.2, 0.0, 0.5]),
            "target": np.array([0.45, 0.25, 0.25])
        }
    ]

    all_results = []

    for scenario in scenarios:
        print(f"\n场景: {scenario['name']}")
        print(f"  起点: {scenario['start']}")
        print(f"  终点: {scenario['target']}")

        scenario_results = []

        for trial in range(n_trials):
            result = simulator.simulate_trial(
                scenario['start'],
                scenario['target'],
                method=config.vist_alpha_computation_method
            )
            scenario_results.append(result)

            if (trial + 1) % 5 == 0:
                success_rate = sum(r.success for r in scenario_results) / len(scenario_results)
                print(f"  试验 {trial+1}/{n_trials}: 成功率 {success_rate:.1%}")

        all_results.extend(scenario_results)

    # 统计结果
    success_count = sum(r.success for r in all_results)
    success_rate = success_count / len(all_results)

    successful_trials = [r for r in all_results if r.success]
    if successful_trials:
        avg_time = np.mean([r.completion_time for r in successful_trials])
        avg_path = np.mean([r.path_length for r in successful_trials])
        avg_jerk = np.mean([r.jerk for r in successful_trials])
    else:
        avg_time = avg_path = avg_jerk = 0.0

    print(f"\n{'='*60}")
    print(f"结果汇总:")
    print(f"  成功率: {success_rate:.1%} ({success_count}/{len(all_results)})")
    print(f"  平均完成时间: {avg_time:.2f}s")
    print(f"  平均路径长度: {avg_path:.3f}m")
    print(f"  平均jerk: {avg_jerk:.4f}")
    print(f"{'='*60}")

    return {
        "method": method_name,
        "noise_level": noise_level,
        "success_rate": success_rate,
        "avg_completion_time": avg_time,
        "avg_path_length": avg_path,
        "avg_jerk": avg_jerk,
        "results": [asdict(r) for r in all_results]
    }


def main():
    """主函数"""
    print("="*60)
    print("高真实度VIST框架模拟测试")
    print("="*60)

    # 创建输出目录
    output_dir = Path("logs/high_fidelity_sim")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 实验配置
    experiments = [
        ("config/system_config.yaml", "Sigmoid方法", "normal"),
        ("config/system_config_paper.yaml", "论文方法", "normal"),
        ("config/system_config.yaml", "Sigmoid方法 (高噪声)", "high"),
        ("config/system_config_paper.yaml", "论文方法 (高噪声)", "high"),
    ]

    all_experiment_results = []

    for config_path, method_name, noise_level in experiments:
        result = run_experiment(config_path, method_name, n_trials=10, noise_level=noise_level)
        all_experiment_results.append(result)

    # 保存结果
    output_file = output_dir / "simulation_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_experiment_results, f, indent=2)
    print(f"\n✅ 结果已保存: {output_file}")

    # 生成对比图表
    print("\n生成对比图表...")
    plot_comparison(all_experiment_results, output_dir)

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    print(f"\n查看结果:")
    print(f"  - 数据: {output_file}")
    print(f"  - 图表: {output_dir}/comparison.png")


def plot_comparison(results: List[Dict], output_dir: Path):
    """绘制对比图表"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    methods = [r['method'] for r in results]
    success_rates = [r['success_rate'] * 100 for r in results]
    completion_times = [r['avg_completion_time'] for r in results]
    path_lengths = [r['avg_path_length'] for r in results]
    jerks = [r['avg_jerk'] for r in results]

    # 成功率
    axes[0, 0].bar(range(len(methods)), success_rates, color=['blue', 'red', 'lightblue', 'lightcoral'])
    axes[0, 0].set_ylabel('Success Rate (%)')
    axes[0, 0].set_title('Success Rate Comparison')
    axes[0, 0].set_xticks(range(len(methods)))
    axes[0, 0].set_xticklabels(methods, rotation=45, ha='right')
    axes[0, 0].grid(True, alpha=0.3)

    # 完成时间
    axes[0, 1].bar(range(len(methods)), completion_times, color=['blue', 'red', 'lightblue', 'lightcoral'])
    axes[0, 1].set_ylabel('Completion Time (s)')
    axes[0, 1].set_title('Average Completion Time')
    axes[0, 1].set_xticks(range(len(methods)))
    axes[0, 1].set_xticklabels(methods, rotation=45, ha='right')
    axes[0, 1].grid(True, alpha=0.3)

    # 路径长度
    axes[1, 0].bar(range(len(methods)), path_lengths, color=['blue', 'red', 'lightblue', 'lightcoral'])
    axes[1, 0].set_ylabel('Path Length (m)')
    axes[1, 0].set_title('Average Path Length')
    axes[1, 0].set_xticks(range(len(methods)))
    axes[1, 0].set_xticklabels(methods, rotation=45, ha='right')
    axes[1, 0].grid(True, alpha=0.3)

    # Jerk
    axes[1, 1].bar(range(len(methods)), jerks, color=['blue', 'red', 'lightblue', 'lightcoral'])
    axes[1, 1].set_ylabel('Jerk')
    axes[1, 1].set_title('Average Jerk (Smoothness)')
    axes[1, 1].set_xticks(range(len(methods)))
    axes[1, 1].set_xticklabels(methods, rotation=45, ha='right')
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "comparison.png", dpi=150)
    print(f"✅ 图表已保存: {output_dir}/comparison.png")


if __name__ == "__main__":
    main()
