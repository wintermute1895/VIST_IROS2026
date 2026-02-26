#!/usr/bin/env python3
"""
纯视觉遥操作性能评估脚本

功能:
1. 从rosbag中提取轨迹数据
2. 计算性能指标（平滑度、精度、延迟等）
3. 生成评估报告和可视化图表

作者: VIST Team
日期: 2026-02-24
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import yaml
import json
from typing import Dict, List, Tuple, Optional
from scipy import signal, interpolate
from scipy.fft import fft, fftfreq
from sklearn.decomposition import PCA

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 尝试导入可选依赖
try:
    from fastdtw import fastdtw
    FASTDTW_AVAILABLE = True
except ImportError:
    FASTDTW_AVAILABLE = False
    print("⚠️  fastdtw未安装，DTW距离计算将不可用")


class VisionPerformanceEvaluator:
    """视觉遥操作性能评估器"""

    def __init__(self, data_dir: str, eval_config_path: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.experiment_config = self.load_experiment_config()
        self.eval_config = self.load_eval_config(eval_config_path)
        self.metrics = {}
        self.trajectories = []  # 存储多条轨迹用于DTW计算

    def load_experiment_config(self) -> Dict:
        """加载实验配置"""
        config_file = self.data_dir / "experiment_config.yaml"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def load_eval_config(self, config_path: Optional[str] = None) -> Dict:
        """加载评估配置"""
        if config_path is None:
            config_path = project_root / "config" / "evaluation_config.yaml"
        else:
            config_path = Path(config_path)

        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)

        # 返回默认配置
        return {
            'metrics_enabled': {
                'smoothness': True,
                'accuracy': True,
                'efficiency': True,
                'normalized_jerk': True,
                'sparc': True,
                'psd_high_freq': True,
                'dtw_distance': True,
                'pca_task_axis': True,
                'success_rate': True
            },
            'metric_params': {
                'sparc': {'padlevel': 4, 'fc': 10.0, 'amp_th': 0.05},
                'psd': {'sampling_rate': 30, 'nperseg': 256, 'freq_threshold': 5.0},
                'dtw': {'radius': 10, 'min_trajectories': 2},
                'pca': {'n_components': 7, 'task_axes': [0, 1, 2]},
                'success_rate': {'position_threshold': 0.001, 'duration_threshold': 0.5, 'goal_position': None}
            }
        }

    def extract_trajectory_from_rosbag(self) -> Tuple[np.ndarray, np.ndarray]:
        """从rosbag中提取轨迹数据"""
        print("📦 从rosbag提取轨迹数据...")

        bag_dir = self.data_dir / "rosbag"
        if not bag_dir.exists():
            # 如果data_dir本身就是rosbag目录
            if (self.data_dir / "metadata.yaml").exists():
                bag_dir = self.data_dir
            else:
                print(f"❌ rosbag目录不存在: {bag_dir}")
                return None, None

        try:
            from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
            from rclpy.serialization import deserialize_message
            from sensor_msgs.msg import JointState
        except ImportError:
            print("❌ 无法导入rosbag2_py，请确保已source ROS2环境")
            return None, None

        # 配置rosbag读取器
        storage_options = StorageOptions(uri=str(bag_dir), storage_id='sqlite3')
        converter_options = ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr'
        )

        reader = SequentialReader()
        reader.open(storage_options, converter_options)

        timestamps = []
        joint_positions = []

        # 读取所有消息
        message_count = 0
        while reader.has_next():
            topic, data, timestamp = reader.read_next()

            # 反序列化消息
            msg = deserialize_message(data, JointState)

            # 提取时间戳（转换为秒）
            timestamps.append(timestamp / 1e9)

            # 提取关节角度（转换为弧度）
            positions = np.array(msg.position)
            # 如果是度，转换为弧度
            if len(positions) > 0 and np.max(np.abs(positions)) > 10:
                positions = np.deg2rad(positions)
            joint_positions.append(positions)

            message_count += 1

        print(f"✅ 提取了 {message_count} 条消息")

        if len(timestamps) == 0:
            print("❌ rosbag中没有数据")
            return None, None

        # 转换为numpy数组
        timestamps = np.array(timestamps)
        # 归一化时间戳（从0开始）
        timestamps = timestamps - timestamps[0]

        joint_positions = np.array(joint_positions)

        print(f"✅ 轨迹数据提取完成: {joint_positions.shape[0]} 个样本, {joint_positions.shape[1]} 个关节")
        return timestamps, joint_positions

    def compute_smoothness_metrics_legacy(self, trajectory: np.ndarray, dt: float) -> Dict:
        """计算平滑度指标（旧版本，保留兼容性）"""
        print("📊 计算平滑度指标...")

        metrics = {}

        # 1. 速度
        velocity = np.diff(trajectory, axis=0) / dt
        velocity_norm = np.linalg.norm(velocity, axis=1)
        metrics['mean_velocity'] = float(np.mean(velocity_norm))
        metrics['max_velocity'] = float(np.max(velocity_norm))
        metrics['std_velocity'] = float(np.std(velocity_norm))

        # 2. 加速度
        acceleration = np.diff(velocity, axis=0) / dt
        acceleration_norm = np.linalg.norm(acceleration, axis=1)
        metrics['mean_acceleration'] = float(np.mean(acceleration_norm))
        metrics['max_acceleration'] = float(np.max(acceleration_norm))
        metrics['std_acceleration'] = float(np.std(acceleration_norm))

        # 3. Jerk（加加速度）
        jerk = np.diff(acceleration, axis=0) / dt
        jerk_norm = np.linalg.norm(jerk, axis=1)
        metrics['mean_jerk'] = float(np.mean(jerk_norm))
        metrics['max_jerk'] = float(np.max(jerk_norm))
        metrics['std_jerk'] = float(np.std(jerk_norm))

        # 4. 平滑度指标（SPARC - Spectral Arc Length）
        # 将在compute_sparc_smoothness中单独计算
        metrics['sparc'] = None

        print("✅ 平滑度指标计算完成")
        return metrics

    def compute_normalized_jerk(self, trajectory: np.ndarray, dt: float) -> Optional[float]:
        """
        计算归一化Jerk (Normalized Jerk)

        公式: NJ = sqrt(0.5 * ∫(jerk²)dt) * duration^(5/2) / path_length

        参数:
            trajectory: 轨迹数据 [N, D]
            dt: 时间步长

        返回:
            归一化Jerk值，越小越平滑
        """
        try:
            # 计算速度
            velocity = np.diff(trajectory, axis=0) / dt

            # 计算加速度
            acceleration = np.diff(velocity, axis=0) / dt

            # 计算jerk
            jerk = np.diff(acceleration, axis=0) / dt

            # 计算jerk的范数
            jerk_norm = np.linalg.norm(jerk, axis=1)

            # 计算积分 ∫(jerk²)dt
            jerk_squared_integral = np.sum(jerk_norm ** 2) * dt

            # 计算任务持续时间
            duration = len(trajectory) * dt

            # 计算路径长度
            path_length = np.sum(np.linalg.norm(np.diff(trajectory, axis=0), axis=1))

            if path_length == 0:
                return None

            # 计算归一化Jerk
            normalized_jerk = np.sqrt(0.5 * jerk_squared_integral) * (duration ** 2.5) / path_length

            return float(normalized_jerk)

        except Exception as e:
            print(f"⚠️  归一化Jerk计算失败: {e}")
            return None

    def compute_sparc_smoothness(self, trajectory: np.ndarray, dt: float) -> Optional[float]:
        """
        计算SPARC平滑度 (Spectral Arc Length)

        SPARC通过测量速度频谱的弧长来量化运动平滑度
        值越接近0表示越平滑（范围通常在-10到0之间）

        参数:
            trajectory: 轨迹数据 [N, D]
            dt: 时间步长

        返回:
            SPARC值，越接近0越平滑
        """
        try:
            params = self.eval_config['metric_params']['sparc']
            padlevel = params.get('padlevel', 4)
            fc = params.get('fc', 10.0)
            amp_th = params.get('amp_th', 0.05)

            # 计算速度
            velocity = np.diff(trajectory, axis=0) / dt
            velocity_norm = np.linalg.norm(velocity, axis=1)

            # 零填充
            nfft = int(2 ** np.ceil(np.log2(len(velocity_norm))) * padlevel)

            # 计算傅里叶变换
            velocity_fft = np.fft.rfft(velocity_norm, n=nfft)
            velocity_mag = np.abs(velocity_fft)

            # 归一化
            velocity_mag = velocity_mag / np.max(velocity_mag)

            # 频率轴
            fs = 1.0 / dt
            freqs = np.fft.rfftfreq(nfft, d=dt)

            # 找到截止频率索引
            fc_idx = np.where(freqs <= fc)[0][-1] if fc < freqs[-1] else len(freqs) - 1

            # 找到幅度阈值索引
            amp_idx = np.where(velocity_mag[:fc_idx] >= amp_th)[0]

            if len(amp_idx) == 0:
                return None

            # 计算弧长
            freqs_selected = freqs[amp_idx]
            mag_selected = velocity_mag[amp_idx]

            # 归一化频率到[0, 1]
            freqs_norm = freqs_selected / freqs_selected[-1]

            # 计算弧长
            arc_length = 0.0
            for i in range(len(freqs_norm) - 1):
                df = freqs_norm[i + 1] - freqs_norm[i]
                dm = mag_selected[i + 1] - mag_selected[i]
                arc_length += np.sqrt(df ** 2 + dm ** 2)

            # SPARC = -arc_length
            sparc = -arc_length

            return float(sparc)

        except Exception as e:
            print(f"⚠️  SPARC计算失败: {e}")
            return None

    def compute_psd_high_freq_power(self, trajectory: np.ndarray, dt: float) -> Optional[float]:
        """
        计算PSD高频能量 (Power Spectral Density >5Hz)

        测量高频噪声能量，用于评估震颤抑制效果

        参数:
            trajectory: 轨迹数据 [N, D]
            dt: 时间步长

        返回:
            高频能量占比，越小表示震颤抑制越好
        """
        try:
            params = self.eval_config['metric_params']['psd']
            fs = params.get('sampling_rate', 1.0 / dt)
            nperseg = params.get('nperseg', 256)
            freq_threshold = params.get('freq_threshold', 5.0)

            # 计算每个关节的PSD
            high_freq_powers = []
            total_powers = []

            for joint_idx in range(trajectory.shape[1]):
                joint_data = trajectory[:, joint_idx]

                # 使用Welch方法计算PSD
                freqs, psd = signal.welch(joint_data, fs=fs, nperseg=min(nperseg, len(joint_data)))

                # 计算总能量
                total_power = np.trapz(psd, freqs)

                # 计算高频能量（>freq_threshold Hz）
                high_freq_idx = freqs > freq_threshold
                high_freq_power = np.trapz(psd[high_freq_idx], freqs[high_freq_idx])

                high_freq_powers.append(high_freq_power)
                total_powers.append(total_power)

            # 计算平均高频能量占比
            if sum(total_powers) == 0:
                return None

            high_freq_ratio = sum(high_freq_powers) / sum(total_powers)

            return float(high_freq_ratio)

        except Exception as e:
            print(f"⚠️  PSD高频能量计算失败: {e}")
            return None

    def compute_dtw_distance(self, trajectories: List[np.ndarray]) -> Optional[float]:
        """
        计算DTW距离 (Dynamic Time Warping Distance)

        测量多条轨迹之间的一致性，需要至少2条轨迹

        参数:
            trajectories: 轨迹列表，每条轨迹形状为 [N, D]

        返回:
            平均DTW距离，越小表示轨迹越一致
        """
        if not FASTDTW_AVAILABLE:
            print("⚠️  fastdtw未安装，无法计算DTW距离")
            return None

        try:
            params = self.eval_config['metric_params']['dtw']
            min_trajectories = params.get('min_trajectories', 2)
            radius = params.get('radius', 10)

            if len(trajectories) < min_trajectories:
                print(f"⚠️  轨迹数量不足（需要至少{min_trajectories}条）")
                return None

            # 计算所有轨迹对之间的DTW距离
            dtw_distances = []

            for i in range(len(trajectories)):
                for j in range(i + 1, len(trajectories)):
                    traj1 = trajectories[i]
                    traj2 = trajectories[j]

                    # 计算DTW距离
                    distance, _ = fastdtw(traj1, traj2, radius=radius)
                    dtw_distances.append(distance)

            # 返回平均DTW距离
            avg_dtw = np.mean(dtw_distances)

            return float(avg_dtw)

        except Exception as e:
            print(f"⚠️  DTW距离计算失败: {e}")
            return None

    def compute_pca_task_axis_ratio(self, trajectory: np.ndarray) -> Optional[float]:
        """
        计算PCA任务轴占比 (Task-Axis PCA Ratio)

        测量运动是否集中在任务相关的维度上

        参数:
            trajectory: 轨迹数据 [N, D]

        返回:
            任务轴能量占比（0-1），越接近1表示运动越集中在任务维度
        """
        try:
            params = self.eval_config['metric_params']['pca']
            n_components = params.get('n_components', min(7, trajectory.shape[1]))
            task_axes = params.get('task_axes', [0, 1, 2])

            # 中心化数据
            trajectory_centered = trajectory - np.mean(trajectory, axis=0)

            # PCA分析
            pca = PCA(n_components=n_components)
            pca.fit(trajectory_centered)

            # 获取解释方差比
            explained_variance_ratio = pca.explained_variance_ratio_

            # 计算任务轴的能量占比
            task_axis_ratio = np.sum(explained_variance_ratio[task_axes])

            return float(task_axis_ratio)

        except Exception as e:
            print(f"⚠️  PCA任务轴占比计算失败: {e}")
            return None

    def compute_success_rate(self, trajectory: np.ndarray,
                            end_effector_positions: Optional[np.ndarray] = None) -> Optional[float]:
        """
        计算成功率 (Success Rate)

        判断任务是否成功完成（末端位置是否达到目标并保持稳定）

        参数:
            trajectory: 轨迹数据 [N, D]
            end_effector_positions: 末端执行器位置 [N, 3]（如果为None则无法计算）

        返回:
            成功率（0或1），1表示成功，0表示失败
        """
        try:
            if end_effector_positions is None:
                print("⚠️  缺少末端位置数据，无法计算成功率")
                return None

            params = self.eval_config['metric_params']['success_rate']
            position_threshold = params.get('position_threshold', 0.001)  # 1mm
            duration_threshold = params.get('duration_threshold', 0.5)    # 0.5s
            goal_position = params.get('goal_position', None)

            # 如果没有指定目标位置，使用轨迹最后10%的平均位置作为目标
            if goal_position is None:
                last_10_percent = int(len(end_effector_positions) * 0.1)
                goal_position = np.mean(end_effector_positions[-last_10_percent:], axis=0)
            else:
                goal_position = np.array(goal_position)

            # 计算每个时刻到目标的距离
            distances = np.linalg.norm(end_effector_positions - goal_position, axis=1)

            # 找到距离小于阈值的时刻
            success_indices = np.where(distances < position_threshold)[0]

            if len(success_indices) == 0:
                return 0.0

            # 检查是否有连续的成功时刻（持续时间超过阈值）
            # 假设采样率为30Hz
            dt = 1.0 / 30.0
            required_frames = int(duration_threshold / dt)

            # 检查连续性
            consecutive_count = 1
            max_consecutive = 1

            for i in range(1, len(success_indices)):
                if success_indices[i] == success_indices[i-1] + 1:
                    consecutive_count += 1
                    max_consecutive = max(max_consecutive, consecutive_count)
                else:
                    consecutive_count = 1

            # 如果有足够长的连续成功时刻，认为任务成功
            if max_consecutive >= required_frames:
                return 1.0
            else:
                return 0.0

        except Exception as e:
            print(f"⚠️  成功率计算失败: {e}")
            return None

    def compute_accuracy_metrics(self, trajectory: np.ndarray, target: np.ndarray = None) -> Dict:
        """计算精度指标"""
        print("🎯 计算精度指标...")

        metrics = {}

        if target is not None:
            # 1. 均方根误差（RMSE）
            rmse = np.sqrt(np.mean((trajectory - target) ** 2))
            metrics['rmse'] = float(rmse)

            # 2. 最大误差
            max_error = np.max(np.abs(trajectory - target))
            metrics['max_error'] = float(max_error)

            # 3. 平均误差
            mean_error = np.mean(np.abs(trajectory - target))
            metrics['mean_error'] = float(mean_error)
        else:
            print("⚠️  未提供目标轨迹，跳过精度计算")

        print("✅ 精度指标计算完成")
        return metrics

    def compute_efficiency_metrics(self, trajectory: np.ndarray, timestamps: np.ndarray) -> Dict:
        """计算效率指标"""
        print("⚡ 计算效率指标...")

        metrics = {}

        # 1. 任务完成时间
        task_duration = timestamps[-1] - timestamps[0]
        metrics['task_duration'] = float(task_duration)

        # 2. 路径长度
        path_length = np.sum(np.linalg.norm(np.diff(trajectory, axis=0), axis=1))
        metrics['path_length'] = float(path_length)

        # 3. 平均速度
        avg_velocity = path_length / task_duration
        metrics['avg_velocity'] = float(avg_velocity)

        # 4. 运动效率（直线距离/实际路径长度）
        straight_distance = np.linalg.norm(trajectory[-1] - trajectory[0])
        if path_length > 0:
            efficiency = straight_distance / path_length
        else:
            efficiency = 0.0
        metrics['efficiency'] = float(efficiency)

        print("✅ 效率指标计算完成")
        return metrics

    def generate_report(self):
        """生成评估报告"""
        print("\n" + "=" * 80)
        print("📋 性能评估报告")
        print("=" * 80)

        # 实验信息
        print("\n实验信息:")
        print(f"  实验ID: {self.experiment_config.get('experiment_id', 'N/A')}")
        print(f"  受试者: {self.experiment_config.get('subject_id', 'N/A')}")
        print(f"  任务类型: {self.experiment_config.get('task_type', 'N/A')}")
        print(f"  滤波器: {self.experiment_config.get('filter_type', 'N/A')}")
        print(f"  时长: {self.experiment_config.get('duration', 'N/A')}秒")

        # 性能指标
        if self.metrics:
            print("\n性能指标:")
            for category, metrics in self.metrics.items():
                print(f"\n  {category}:")
                if isinstance(metrics, dict):
                    for key, value in metrics.items():
                        if value is None:
                            print(f"    {key}: None (数据不足)")
                        elif isinstance(value, float):
                            decimal_places = self.eval_config.get('report', {}).get('decimal_places', 4)
                            print(f"    {key}: {value:.{decimal_places}f}")
                        else:
                            print(f"    {key}: {value}")
                else:
                    if metrics is None:
                        print(f"    {category}: None (数据不足)")
                    else:
                        print(f"    {category}: {metrics}")

        # 保存报告
        report_file = self.data_dir / "performance_report.json"
        report_data = {
            'experiment_config': self.experiment_config,
            'evaluation_config': self.eval_config,
            'metrics': self.metrics
        }

        # 处理None值（JSON不支持None，转换为null）
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"\n✅ 报告已保存: {report_file}")
        print("=" * 80)

    def visualize_trajectory(self, trajectory: np.ndarray, timestamps: np.ndarray):
        """可视化轨迹"""
        print("📈 生成可视化图表...")

        viz_config = self.eval_config.get('visualization', {})
        plots_config = viz_config.get('plots', {})

        # 确定需要绘制的图表数量
        num_plots = sum([
            plots_config.get('joint_angles', True),
            plots_config.get('velocity_profile', True),
            plots_config.get('acceleration_profile', True),
            plots_config.get('jerk_profile', True),
            plots_config.get('psd_spectrum', True)
        ])

        if num_plots == 0:
            print("⚠️  所有图表都已禁用")
            return

        # 创建子图
        rows = (num_plots + 1) // 2
        cols = 2 if num_plots > 1 else 1

        figsize = viz_config.get('figsize', [15, 10])
        fig, axes = plt.subplots(rows, cols, figsize=figsize)
        if num_plots == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        fig.suptitle(f"轨迹分析 - {self.experiment_config.get('experiment_id', 'N/A')}", fontsize=16)

        plot_idx = 0
        dt = np.mean(np.diff(timestamps))

        # 1. 关节角度随时间变化
        if plots_config.get('joint_angles', True):
            ax = axes[plot_idx]
            for i in range(min(7, trajectory.shape[1])):
                ax.plot(timestamps, trajectory[:, i], label=f'Joint {i+1}')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Joint Angle (rad)')
            ax.set_title('Joint Angles over Time')
            ax.legend()
            ax.grid(True)
            plot_idx += 1

        # 2. 速度分析
        if plots_config.get('velocity_profile', True):
            ax = axes[plot_idx]
            velocity = np.diff(trajectory, axis=0) / dt
            velocity_norm = np.linalg.norm(velocity, axis=1)
            ax.plot(timestamps[1:], velocity_norm)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Velocity (rad/s)')
            ax.set_title('Velocity Profile')
            ax.grid(True)
            plot_idx += 1

        # 3. 加速度分析
        if plots_config.get('acceleration_profile', True):
            ax = axes[plot_idx]
            velocity = np.diff(trajectory, axis=0) / dt
            acceleration = np.diff(velocity, axis=0) / dt
            acceleration_norm = np.linalg.norm(acceleration, axis=1)
            ax.plot(timestamps[2:], acceleration_norm)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Acceleration (rad/s²)')
            ax.set_title('Acceleration Profile')
            ax.grid(True)
            plot_idx += 1

        # 4. Jerk分析
        if plots_config.get('jerk_profile', True):
            ax = axes[plot_idx]
            velocity = np.diff(trajectory, axis=0) / dt
            acceleration = np.diff(velocity, axis=0) / dt
            jerk = np.diff(acceleration, axis=0) / dt
            jerk_norm = np.linalg.norm(jerk, axis=1)
            ax.plot(timestamps[3:], jerk_norm)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Jerk (rad/s³)')
            ax.set_title('Jerk Profile')
            ax.grid(True)
            plot_idx += 1

        # 5. PSD频谱分析
        if plots_config.get('psd_spectrum', True) and plot_idx < len(axes):
            ax = axes[plot_idx]
            # 计算第一个关节的PSD作为示例
            fs = 1.0 / dt
            nperseg = min(256, len(trajectory))
            freqs, psd = signal.welch(trajectory[:, 0], fs=fs, nperseg=nperseg)

            ax.semilogy(freqs, psd)
            ax.axvline(x=5, color='r', linestyle='--', label='5Hz threshold')
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel('PSD')
            ax.set_title('Power Spectral Density (Joint 1)')
            ax.legend()
            ax.grid(True)
            plot_idx += 1

        # 隐藏多余的子图
        for i in range(plot_idx, len(axes)):
            axes[i].set_visible(False)

        plt.tight_layout()

        # 保存图表
        plot_file = self.data_dir / "trajectory_analysis.png"
        dpi = viz_config.get('dpi', 300)
        plt.savefig(plot_file, dpi=dpi, bbox_inches='tight')
        print(f"✅ 图表已保存: {plot_file}")

        plt.close()

        # 6. 生成3D轨迹图（如果启用）
        if plots_config.get('trajectory_3d', False):
            self.visualize_3d_trajectory(trajectory, timestamps)

    def visualize_3d_trajectory(self, trajectory: np.ndarray, timestamps: np.ndarray):
        """生成3D轨迹图"""
        print("📈 生成3D轨迹图...")

        try:
            # 尝试导入IK求解器
            from src.core.ik_solver import PinocchioIKSolver
            import pinocchio as pin

            # 加载URDF
            urdf_file = project_root / "config" / "urdf" / "lkls73_o2_dual_arm_description.urdf"
            if not urdf_file.exists():
                print(f"⚠️  URDF文件不存在: {urdf_file}")
                return

            ik_solver = PinocchioIKSolver(urdf_path=str(urdf_file))

            # 获取末端执行器frame ID
            ee_frame_id = ik_solver.ee_frame_id

            # 计算末端位置
            end_effector_positions = []
            for joint_angles in trajectory:
                # 创建完整的关节配置（包括所有关节）
                q = np.zeros(ik_solver.model.nq)
                # 只设置受控关节的值
                for i, joint_idx in enumerate(ik_solver.controlled_indices):
                    if i < len(joint_angles):
                        q[joint_idx] = joint_angles[i]

                # 正向运动学
                pin.framesForwardKinematics(ik_solver.model, ik_solver.data, q)
                ee_pose = ik_solver.data.oMf[ee_frame_id]
                ee_pos = ee_pose.translation
                end_effector_positions.append(ee_pos)

            end_effector_positions = np.array(end_effector_positions)

            # 创建3D图
            from mpl_toolkits.mplot3d import Axes3D
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111, projection='3d')

            # 绘制轨迹
            ax.plot(end_effector_positions[:, 0],
                   end_effector_positions[:, 1],
                   end_effector_positions[:, 2],
                   'b-', linewidth=2, label='Trajectory')

            # 标记起点和终点
            ax.scatter(end_effector_positions[0, 0],
                      end_effector_positions[0, 1],
                      end_effector_positions[0, 2],
                      c='g', s=100, marker='o', label='Start')
            ax.scatter(end_effector_positions[-1, 0],
                      end_effector_positions[-1, 1],
                      end_effector_positions[-1, 2],
                      c='r', s=100, marker='x', label='End')

            # 设置标签
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.set_zlabel('Z (m)')
            ax.set_title(f'3D Trajectory - {self.experiment_config.get("experiment_id", "N/A")}')
            ax.legend()
            ax.grid(True)

            # 设置相同的比例尺
            max_range = np.array([
                end_effector_positions[:, 0].max() - end_effector_positions[:, 0].min(),
                end_effector_positions[:, 1].max() - end_effector_positions[:, 1].min(),
                end_effector_positions[:, 2].max() - end_effector_positions[:, 2].min()
            ]).max() / 2.0

            mid_x = (end_effector_positions[:, 0].max() + end_effector_positions[:, 0].min()) * 0.5
            mid_y = (end_effector_positions[:, 1].max() + end_effector_positions[:, 1].min()) * 0.5
            mid_z = (end_effector_positions[:, 2].max() + end_effector_positions[:, 2].min()) * 0.5

            ax.set_xlim(mid_x - max_range, mid_x + max_range)
            ax.set_ylim(mid_y - max_range, mid_y + max_range)
            ax.set_zlim(mid_z - max_range, mid_z + max_range)

            # 保存图表
            plot_file = self.data_dir / "trajectory_3d.png"
            viz_config = self.eval_config.get('visualization', {})
            dpi = viz_config.get('dpi', 300)
            plt.savefig(plot_file, dpi=dpi, bbox_inches='tight')
            print(f"✅ 3D轨迹图已保存: {plot_file}")

            plt.close()

            # 清理IK求解器
            ik_solver.cleanup()

        except ImportError as e:
            print(f"⚠️  无法导入IK求解器: {e}")
            print("   3D轨迹图需要正向运动学计算，请确保IK求解器可用")
        except Exception as e:
            print(f"⚠️  3D轨迹图生成失败: {e}")
            import traceback
            traceback.print_exc()

    def evaluate(self):
        """执行完整评估"""
        print("\n🔍 开始性能评估...")
        print(f"数据目录: {self.data_dir}")

        # 1. 提取轨迹数据
        timestamps, trajectory = self.extract_trajectory_from_rosbag()

        if trajectory is None:
            print("⚠️  无法提取轨迹数据，使用模拟数据进行演示")
            # 生成模拟数据用于演示
            timestamps = np.linspace(0, 60, 1800)  # 60秒，30Hz
            trajectory = np.random.randn(1800, 7) * 0.1  # 7个关节

        # 2. 计算性能指标（根据配置）
        dt = np.mean(np.diff(timestamps))
        metrics_enabled = self.eval_config.get('metrics_enabled', {})

        # 基础指标
        if metrics_enabled.get('smoothness', True):
            print("\n📊 计算平滑度指标...")
            self.metrics['smoothness'] = self.compute_smoothness_metrics_legacy(trajectory, dt)

        if metrics_enabled.get('accuracy', True):
            self.metrics['accuracy'] = self.compute_accuracy_metrics(trajectory)

        if metrics_enabled.get('efficiency', True):
            self.metrics['efficiency'] = self.compute_efficiency_metrics(trajectory, timestamps)

        # 论文核心指标
        if metrics_enabled.get('normalized_jerk', True):
            print("\n📐 计算归一化Jerk...")
            normalized_jerk = self.compute_normalized_jerk(trajectory, dt)
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['normalized_jerk'] = normalized_jerk

        if metrics_enabled.get('sparc', True):
            print("\n🌊 计算SPARC平滑度...")
            sparc = self.compute_sparc_smoothness(trajectory, dt)
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['sparc'] = sparc

        if metrics_enabled.get('psd_high_freq', True):
            print("\n📡 计算PSD高频能量...")
            psd_high_freq = self.compute_psd_high_freq_power(trajectory, dt)
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['psd_high_freq_power'] = psd_high_freq

        if metrics_enabled.get('dtw_distance', True):
            print("\n🔄 计算DTW距离...")
            # DTW需要多条轨迹，如果只有一条则跳过
            if len(self.trajectories) >= 2:
                dtw_distance = self.compute_dtw_distance(self.trajectories)
            else:
                print("⚠️  只有一条轨迹，无法计算DTW距离")
                dtw_distance = None
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['dtw_distance'] = dtw_distance

        if metrics_enabled.get('pca_task_axis', True):
            print("\n🎯 计算PCA任务轴占比...")
            pca_ratio = self.compute_pca_task_axis_ratio(trajectory)
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['pca_task_axis_ratio'] = pca_ratio

        if metrics_enabled.get('success_rate', True):
            print("\n✅ 计算成功率...")
            # 成功率需要末端位置数据，这里暂时设为None
            success_rate = self.compute_success_rate(trajectory, end_effector_positions=None)
            if 'advanced_metrics' not in self.metrics:
                self.metrics['advanced_metrics'] = {}
            self.metrics['advanced_metrics']['success_rate'] = success_rate

        # 3. 生成报告
        self.generate_report()

        # 4. 可视化
        if self.eval_config.get('visualization', {}).get('enabled', True):
            self.visualize_trajectory(trajectory, timestamps)

        print("\n✅ 评估完成！")


def main():
    parser = argparse.ArgumentParser(description='评估纯视觉遥操作性能')
    parser.add_argument('data_dir', type=str, help='数据目录路径')
    parser.add_argument('--config', type=str, default=None, help='评估配置文件路径')
    parser.add_argument('--no-plot', action='store_true', help='不生成图表')

    args = parser.parse_args()

    # 检查数据目录
    if not os.path.exists(args.data_dir):
        print(f"❌ 数据目录不存在: {args.data_dir}")
        sys.exit(1)

    # 创建评估器并执行评估
    evaluator = VisionPerformanceEvaluator(args.data_dir, eval_config_path=args.config)

    # 如果指定了--no-plot，禁用可视化
    if args.no_plot:
        evaluator.eval_config['visualization']['enabled'] = False

    evaluator.evaluate()


if __name__ == '__main__':
    main()