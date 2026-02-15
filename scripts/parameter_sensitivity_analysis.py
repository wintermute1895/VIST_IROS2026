#!/usr/bin/env python3
"""
参数敏感性分析
测试关键参数对系统性能的影响
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import yaml
from dataclasses import dataclass
from typing import List, Dict, Tuple

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from src.config.config_loader import VISTConfig
from src.core.vist_kalman_filter import VISTKalmanFilter


@dataclass
class ParameterSweepResult:
    """参数扫描结果"""
    parameter_name: str
    parameter_values: List[float]
    success_rates: List[float]
    avg_completion_times: List[float]
    avg_path_lengths: List[float]
    avg_jerks: List[float]
    avg_alphas: List[float]


class ParameterSensitivityAnalyzer:
    """参数敏感性分析器"""

    def __init__(self, base_config_path: str = "config/system_config.yaml"):
        self.base_config_path = base_config_path
        self.base_config = VISTConfig(config_path=base_config_path)

    def create_modified_config(self, param_path: str, param_value: float) -> VISTConfig:
        """创建修改后的配置"""
        # 加载基础配置
        with open(self.base_config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        # 修改参数
        keys = param_path.split('.')
        current = config_dict
        for key in keys[:-1]:
            current = current[key]
        current[keys[-1]] = param_value

        # 保存临时配置
        temp_config_path = Path("config/temp_sensitivity_config.yaml")
        with open(temp_config_path, 'w') as f:
            yaml.dump(config_dict, f)

        # 加载修改后的配置
        return VISTConfig(config_path=str(temp_config_path))

    def simulate_trial(self, config: VISTConfig, start_pos: np.ndarray,
                      target_pos: np.ndarray, noise_std: float = 0.005) -> Dict:
        """模拟单次试验"""
        # 初始化滤波器
        kf = VISTKalmanFilter(config)

        # 初始化状态
        current_pos = start_pos.copy()
        current_vel = np.zeros(3)

        # 轨迹记录
        alpha_traj = []
        distance_traj = []
        velocity_traj = []
        positions = [current_pos.copy()]

        # 模拟参数
        dt = 0.02  # 50Hz
        max_steps = 500
        success_threshold = 0.01  # 1cm

        for step in range(max_steps):
            # 添加传感器噪声
            noisy_pos = current_pos + np.random.normal(0, noise_std, 3)

            # 计算意图因子
            distance = np.linalg.norm(target_pos - current_pos)
            speed = np.linalg.norm(current_vel)
            alpha = kf.detect_intent(target_pos, noisy_pos, current_vel)

            # 记录
            alpha_traj.append(alpha)
            distance_traj.append(distance)
            velocity_traj.append(speed)

            # 检查成功
            if distance < success_threshold:
                return {
                    'success': True,
                    'completion_time': step * dt,
                    'path_length': self._compute_path_length(positions),
                    'jerk': self._compute_jerk(positions, dt),
                    'avg_alpha': np.mean(alpha_traj),
                    'alpha_trajectory': alpha_traj,
                    'distance_trajectory': distance_traj,
                    'velocity_trajectory': velocity_traj
                }

            # 简单的运动模型：朝目标移动
            direction = (target_pos - current_pos) / (distance + 1e-6)
            # 速度与α成反比（α高时慢速精密操作）
            desired_speed = 0.1 * (1.0 - 0.5 * alpha)
            current_vel = direction * desired_speed
            current_pos += current_vel * dt

            positions.append(current_pos.copy())

        # 超时失败
        return {
            'success': False,
            'completion_time': max_steps * dt,
            'path_length': self._compute_path_length(positions),
            'jerk': self._compute_jerk(positions, dt),
            'avg_alpha': np.mean(alpha_traj) if alpha_traj else 0.0,
            'alpha_trajectory': alpha_traj,
            'distance_trajectory': distance_traj,
            'velocity_trajectory': velocity_traj
        }

    def _compute_path_length(self, positions: List[np.ndarray]) -> float:
        """计算路径长度"""
        length = 0.0
        for i in range(1, len(positions)):
            length += np.linalg.norm(positions[i] - positions[i-1])
        return length

    def _compute_jerk(self, positions: List[np.ndarray], dt: float) -> float:
        """计算jerk（加速度变化率）"""
        if len(positions) < 4:
            return 0.0

        # 计算加速度
        accelerations = []
        for i in range(2, len(positions)):
            vel1 = (positions[i-1] - positions[i-2]) / dt
            vel2 = (positions[i] - positions[i-1]) / dt
            acc = (vel2 - vel1) / dt
            accelerations.append(np.linalg.norm(acc))

        # 计算jerk
        jerks = []
        for i in range(1, len(accelerations)):
            jerk = abs(accelerations[i] - accelerations[i-1]) / dt
            jerks.append(jerk)

        return np.mean(jerks) if jerks else 0.0

    def sweep_parameter(self, param_path: str, param_values: List[float],
                       param_name: str, num_trials: int = 10) -> ParameterSweepResult:
        """扫描参数"""
        print(f"\n{'='*60}")
        print(f"参数扫描: {param_name}")
        print(f"参数路径: {param_path}")
        print(f"参数范围: {param_values}")
        print(f"{'='*60}")

        # 测试场景
        start_pos = np.array([0.3, 0.1, 0.4])
        target_pos = np.array([0.45, 0.25, 0.25])

        success_rates = []
        avg_completion_times = []
        avg_path_lengths = []
        avg_jerks = []
        avg_alphas = []

        for param_value in param_values:
            print(f"\n测试 {param_name} = {param_value}")

            # 创建修改后的配置
            config = self.create_modified_config(param_path, param_value)

            # 运行多次试验
            results = []
            for trial in range(num_trials):
                result = self.simulate_trial(config, start_pos, target_pos)
                results.append(result)

            # 统计结果
            success_rate = sum(r['success'] for r in results) / num_trials
            avg_time = np.mean([r['completion_time'] for r in results])
            avg_length = np.mean([r['path_length'] for r in results])
            avg_jerk = np.mean([r['jerk'] for r in results])
            avg_alpha = np.mean([r['avg_alpha'] for r in results])

            success_rates.append(success_rate)
            avg_completion_times.append(avg_time)
            avg_path_lengths.append(avg_length)
            avg_jerks.append(avg_jerk)
            avg_alphas.append(avg_alpha)

            print(f"  成功率: {success_rate*100:.1f}%")
            print(f"  平均完成时间: {avg_time:.2f}s")
            print(f"  平均α: {avg_alpha:.3f}")

        return ParameterSweepResult(
            parameter_name=param_name,
            parameter_values=param_values,
            success_rates=success_rates,
            avg_completion_times=avg_completion_times,
            avg_path_lengths=avg_path_lengths,
            avg_jerks=avg_jerks,
            avg_alphas=avg_alphas
        )


def plot_sensitivity_results(results: List[ParameterSweepResult], output_dir: Path):
    """可视化敏感性分析结果"""
    print("\n📊 生成敏感性分析图表...")

    n_params = len(results)
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Parameter Sensitivity Analysis', fontsize=16, y=0.995)

    colors = plt.cm.tab10(np.linspace(0, 1, n_params))

    # 1. 成功率 vs 参数
    ax = axes[0, 0]
    for i, result in enumerate(results):
        ax.plot(result.parameter_values, np.array(result.success_rates) * 100,
               'o-', label=result.parameter_name, color=colors[i], linewidth=2, markersize=6)
    ax.set_xlabel('Parameter Value', fontsize=11)
    ax.set_ylabel('Success Rate (%)', fontsize=11)
    ax.set_title('Success Rate vs Parameter', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 105])

    # 2. 完成时间 vs 参数
    ax = axes[0, 1]
    for i, result in enumerate(results):
        ax.plot(result.parameter_values, result.avg_completion_times,
               'o-', label=result.parameter_name, color=colors[i], linewidth=2, markersize=6)
    ax.set_xlabel('Parameter Value', fontsize=11)
    ax.set_ylabel('Completion Time (s)', fontsize=11)
    ax.set_title('Completion Time vs Parameter', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 3. 路径长度 vs 参数
    ax = axes[0, 2]
    for i, result in enumerate(results):
        ax.plot(result.parameter_values, result.avg_path_lengths,
               'o-', label=result.parameter_name, color=colors[i], linewidth=2, markersize=6)
    ax.set_xlabel('Parameter Value', fontsize=11)
    ax.set_ylabel('Path Length (m)', fontsize=11)
    ax.set_title('Path Length vs Parameter', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. Jerk vs 参数
    ax = axes[1, 0]
    for i, result in enumerate(results):
        ax.plot(result.parameter_values, result.avg_jerks,
               'o-', label=result.parameter_name, color=colors[i], linewidth=2, markersize=6)
    ax.set_xlabel('Parameter Value', fontsize=11)
    ax.set_ylabel('Average Jerk', fontsize=11)
    ax.set_title('Smoothness vs Parameter', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 5. 平均α vs 参数
    ax = axes[1, 1]
    for i, result in enumerate(results):
        ax.plot(result.parameter_values, result.avg_alphas,
               'o-', label=result.parameter_name, color=colors[i], linewidth=2, markersize=6)
    ax.set_xlabel('Parameter Value', fontsize=11)
    ax.set_ylabel('Average α', fontsize=11)
    ax.set_title('Intent Factor vs Parameter', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 6. 敏感性热图
    ax = axes[1, 2]
    # 计算每个参数对成功率的影响（标准差）
    sensitivities = []
    param_names = []
    for result in results:
        sensitivity = np.std(result.success_rates)
        sensitivities.append(sensitivity)
        param_names.append(result.parameter_name)

    bars = ax.barh(range(len(param_names)), sensitivities, color=colors[:len(param_names)])
    ax.set_yticks(range(len(param_names)))
    ax.set_yticklabels(param_names, fontsize=10)
    ax.set_xlabel('Success Rate Std Dev', fontsize=11)
    ax.set_title('Parameter Sensitivity Ranking', fontsize=12)
    ax.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    plt.savefig(output_dir / "parameter_sensitivity.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'parameter_sensitivity.png'}")
    plt.close()


def main():
    """主函数"""
    print("=" * 60)
    print("参数敏感性分析")
    print("=" * 60)

    output_dir = Path("logs/sensitivity_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    analyzer = ParameterSensitivityAnalyzer()

    # 定义要测试的参数
    parameter_sweeps = [
        {
            'path': 'vist_kalman.intent_detection.distance_threshold',
            'name': 'Distance Threshold',
            'values': [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
        },
        {
            'path': 'vist_kalman.intent_detection.sigmoid_k',
            'name': 'Sigmoid k',
            'values': [5, 10, 15, 20, 25, 30]
        },
        {
            'path': 'vist_kalman.intent_detection.alpha_weights.distance',
            'name': 'Distance Weight',
            'values': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        },
    ]

    # 执行参数扫描
    results = []
    for sweep_config in parameter_sweeps:
        result = analyzer.sweep_parameter(
            param_path=sweep_config['path'],
            param_values=sweep_config['values'],
            param_name=sweep_config['name'],
            num_trials=10
        )
        results.append(result)

    # 可视化结果
    plot_sensitivity_results(results, output_dir)

    print("\n" + "=" * 60)
    print("✅ 参数敏感性分析完成!")
    print("=" * 60)
    print(f"\n查看结果: {output_dir / 'parameter_sensitivity.png'}")

    # 清理临时配置
    temp_config = Path("config/temp_sensitivity_config.yaml")
    if temp_config.exists():
        temp_config.unlink()


if __name__ == "__main__":
    main()
