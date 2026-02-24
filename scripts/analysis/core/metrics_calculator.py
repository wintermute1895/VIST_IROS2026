"""
MetricsCalculator - 性能指标计算模块

功能：
1. 计算速度、加速度、Jerk
2. 计算频率统计
3. 计算RMS、平均值、最大值等统计指标
4. 支持物理极限滤波
"""
import numpy as np
from typing import Dict, Optional, Tuple
from scipy.signal import savgol_filter


class MetricsCalculator:
    """性能指标计算器"""

    def __init__(self, physical_limits: Optional[Dict] = None):
        """
        初始化指标计算器

        Args:
            physical_limits: 物理极限参数，用于离群点检测
                {
                    'max_velocity': 3.14,
                    'max_acceleration': 15.0,
                    'max_jerk': 100.0
                }
        """
        self.physical_limits = physical_limits or {}

    def calculate_all_metrics(self, trajectory: np.ndarray, timestamps: np.ndarray) -> Dict:
        """
        计算所有性能指标

        Args:
            trajectory: (N, M) 数组，N是样本数，M是关节数
            timestamps: (N,) 数组，时间戳（秒）

        Returns:
            包含所有指标的字典
        """
        if trajectory is None or timestamps is None or len(trajectory) < 2:
            return {}

        # 计算频率
        frequency_metrics = self.calculate_frequency(timestamps)

        # 计算速度
        velocity, velocity_timestamps = self.calculate_velocity(trajectory, timestamps)
        velocity_metrics = self._calculate_statistics(velocity, 'velocity')

        # 计算加速度
        acceleration, accel_timestamps = self.calculate_acceleration(velocity, velocity_timestamps)
        acceleration_metrics = self._calculate_statistics(acceleration, 'acceleration')

        # 计算Jerk
        jerk, jerk_timestamps = self.calculate_jerk(acceleration, accel_timestamps)
        jerk_metrics = self._calculate_statistics(jerk, 'jerk')

        # 合并所有指标
        metrics = {
            **frequency_metrics,
            **velocity_metrics,
            **acceleration_metrics,
            **jerk_metrics,
            'num_samples': len(trajectory),
            'duration': timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0
        }

        return metrics

    def calculate_frequency(self, timestamps: np.ndarray) -> Dict:
        """
        计算频率统计

        Returns:
            {
                'frequency': 平均频率,
                'frequency_std': 频率标准差,
                'frequency_min': 最小频率,
                'frequency_max': 最大频率
            }
        """
        if len(timestamps) < 2:
            return {}

        time_diffs = np.diff(timestamps)
        frequencies = 1.0 / time_diffs

        return {
            'frequency': float(np.mean(frequencies)),
            'frequency_std': float(np.std(frequencies)),
            'frequency_min': float(np.min(frequencies)),
            'frequency_max': float(np.max(frequencies))
        }

    def calculate_velocity(self, trajectory: np.ndarray, timestamps: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算速度

        Args:
            trajectory: (N, M) 位置数组
            timestamps: (N,) 时间戳数组

        Returns:
            (velocity, timestamps) 元组
            - velocity: (N-1, M) 速度数组
            - timestamps: (N-1,) 时间戳数组（中点时间）
        """
        if len(trajectory) < 2:
            return np.array([]), np.array([])

        dt = np.diff(timestamps)
        dq = np.diff(trajectory, axis=0)

        # 避免除以零
        dt = np.maximum(dt, 1e-10)

        velocity = dq / dt[:, np.newaxis]

        # 使用中点时间
        velocity_timestamps = timestamps[:-1] + dt / 2

        return velocity, velocity_timestamps

    def calculate_acceleration(self, velocity: np.ndarray, timestamps: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算加速度

        Args:
            velocity: (N, M) 速度数组
            timestamps: (N,) 时间戳数组

        Returns:
            (acceleration, timestamps) 元组
        """
        if len(velocity) < 2:
            return np.array([]), np.array([])

        dt = np.diff(timestamps)
        dv = np.diff(velocity, axis=0)

        dt = np.maximum(dt, 1e-10)
        acceleration = dv / dt[:, np.newaxis]

        accel_timestamps = timestamps[:-1] + dt / 2

        return acceleration, accel_timestamps

    def calculate_jerk(self, acceleration: np.ndarray, timestamps: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算Jerk（加加速度）

        Args:
            acceleration: (N, M) 加速度数组
            timestamps: (N,) 时间戳数组

        Returns:
            (jerk, timestamps) 元组
        """
        if len(acceleration) < 2:
            return np.array([]), np.array([])

        dt = np.diff(timestamps)
        da = np.diff(acceleration, axis=0)

        dt = np.maximum(dt, 1e-10)
        jerk = da / dt[:, np.newaxis]

        jerk_timestamps = timestamps[:-1] + dt / 2

        return jerk, jerk_timestamps

    def _calculate_statistics(self, data: np.ndarray, prefix: str) -> Dict:
        """
        计算统计指标

        Args:
            data: (N, M) 数据数组
            prefix: 指标前缀（如 'velocity', 'acceleration', 'jerk'）

        Returns:
            统计指标字典
        """
        if len(data) == 0:
            return {}

        # 计算每个关节的范数
        norms = np.linalg.norm(data, axis=1)

        return {
            f'avg_{prefix}': float(np.mean(norms)),
            f'max_{prefix}': float(np.max(norms)),
            f'rms_{prefix}': float(np.sqrt(np.mean(norms ** 2))),
            f'std_{prefix}': float(np.std(norms)),
            f'median_{prefix}': float(np.median(norms)),
            f'p95_{prefix}': float(np.percentile(norms, 95)),
            f'p99_{prefix}': float(np.percentile(norms, 99))
        }

    def apply_physical_filter(self, trajectory: np.ndarray, timestamps: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        应用物理极限滤波，剔除不符合物理规律的离群点

        Args:
            trajectory: (N, M) 位置数组
            timestamps: (N,) 时间戳数组

        Returns:
            (filtered_trajectory, filtered_timestamps, outlier_mask) 元组
            - filtered_trajectory: 过滤后的轨迹
            - filtered_timestamps: 过滤后的时间戳
            - outlier_mask: 离群点掩码（True表示离群点）
        """
        if not self.physical_limits or len(trajectory) < 3:
            return trajectory, timestamps, np.zeros(len(trajectory), dtype=bool)

        # 计算速度
        velocity, _ = self.calculate_velocity(trajectory, timestamps)
        velocity_norms = np.linalg.norm(velocity, axis=1)

        # 检测速度离群点
        max_vel = self.physical_limits.get('max_velocity', np.inf)
        vel_threshold = max_vel * self.physical_limits.get('velocity_threshold_multiplier', 1.5)

        # 创建离群点掩码（需要扩展到原始长度）
        outlier_mask = np.zeros(len(trajectory), dtype=bool)
        outlier_mask[1:] = velocity_norms > vel_threshold

        # 过滤数据
        filtered_trajectory = trajectory[~outlier_mask]
        filtered_timestamps = timestamps[~outlier_mask]

        return filtered_trajectory, filtered_timestamps, outlier_mask

    def smooth_trajectory(self, trajectory: np.ndarray, window_length: int = 11, polyorder: int = 3) -> np.ndarray:
        """
        使用Savitzky-Golay滤波器平滑轨迹

        Args:
            trajectory: (N, M) 位置数组
            window_length: 窗口长度（必须是奇数）
            polyorder: 多项式阶数

        Returns:
            平滑后的轨迹
        """
        if len(trajectory) < window_length:
            return trajectory

        # 确保window_length是奇数
        if window_length % 2 == 0:
            window_length += 1

        smoothed = np.zeros_like(trajectory)
        for i in range(trajectory.shape[1]):
            smoothed[:, i] = savgol_filter(trajectory[:, i], window_length, polyorder)

        return smoothed


if __name__ == '__main__':
    # 测试代码
    import sys
    import os

    # 添加项目根目录到路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    sys.path.insert(0, project_root)

    from scripts.analysis.core.rosbag_reader import RosbagReader

    if len(sys.argv) < 3:
        print("用法: python metrics_calculator.py <rosbag_path> <topic_name>")
        sys.exit(1)

    rosbag_path = sys.argv[1]
    topic_name = sys.argv[2]

    # 读取数据
    reader = RosbagReader(rosbag_path)
    trajectory, timestamps = reader.read_topic(topic_name)

    if trajectory is None:
        print(f"错误: 无法读取话题 {topic_name}")
        sys.exit(1)

    # 计算指标
    calculator = MetricsCalculator()
    metrics = calculator.calculate_all_metrics(trajectory, timestamps)

    print("=" * 60)
    print(f"性能指标分析: {topic_name}")
    print("=" * 60)

    print(f"\n📊 基本信息:")
    print(f"  样本数: {metrics['num_samples']}")
    print(f"  时长: {metrics['duration']:.2f} 秒")

    print(f"\n⏱️  频率:")
    print(f"  平均: {metrics['frequency']:.2f} Hz")
    print(f"  标准差: {metrics['frequency_std']:.2f} Hz")
    print(f"  范围: {metrics['frequency_min']:.2f} - {metrics['frequency_max']:.2f} Hz")

    print(f"\n🚀 速度:")
    print(f"  平均: {metrics['avg_velocity']:.4f} rad/s")
    print(f"  最大: {metrics['max_velocity']:.4f} rad/s")
    print(f"  RMS: {metrics['rms_velocity']:.4f} rad/s")

    print(f"\n⚡ 加速度:")
    print(f"  平均: {metrics['avg_acceleration']:.4f} rad/s²")
    print(f"  最大: {metrics['max_acceleration']:.4f} rad/s²")
    print(f"  RMS: {metrics['rms_acceleration']:.4f} rad/s²")

    print(f"\n💥 Jerk:")
    print(f"  平均: {metrics['avg_jerk']:.4f} rad/s³")
    print(f"  最大: {metrics['max_jerk']:.4f} rad/s³")
    print(f"  RMS: {metrics['rms_jerk']:.4f} rad/s³")