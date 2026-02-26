#!/usr/bin/env python3
"""
评估跟踪性能：计算真机跟随遥操臂的误差
这种方法不受底层数据质量影响，专注于评估控制算法性能
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState


def extract_trajectory(rosbag_path, topic):
    """从rosbag中提取轨迹"""
    storage_options = StorageOptions(uri=str(rosbag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    trajectories = []
    timestamps = []

    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name == topic:
            try:
                msg = deserialize_message(data, JointState)
                if len(msg.position) > 0:
                    trajectories.append(np.array(msg.position))
                    timestamps.append(timestamp * 1e-9)
            except:
                continue

    if not trajectories:
        return None, None

    trajectory = np.array(trajectories)

    # 单位转换
    if 'joint_control' in topic and 'robot' not in topic:
        trajectory = np.deg2rad(trajectory)

    return trajectory, np.array(timestamps)


def align_trajectories(traj1, time1, traj2, time2):
    """
    将两个轨迹对齐到相同的时间轴
    使用插值将两者对齐到较低频率的时间轴
    """
    # 使用较低频率的时间轴作为基准
    if len(time1) < len(time2):
        base_time = time1
        base_traj = traj1
        interp_time = time2
        interp_traj = traj2
        swap = False
    else:
        base_time = time2
        base_traj = traj2
        interp_time = time1
        interp_traj = traj1
        swap = True

    # 找到时间重叠区域
    start_time = max(base_time[0], interp_time[0])
    end_time = min(base_time[-1], interp_time[-1])

    # 在重叠区域内生成均匀时间轴
    mask = (base_time >= start_time) & (base_time <= end_time)
    aligned_time = base_time[mask]
    aligned_base = base_traj[mask]

    # 插值另一个轨迹
    aligned_interp = np.zeros((len(aligned_time), interp_traj.shape[1]))
    for joint_idx in range(interp_traj.shape[1]):
        interpolator = interp1d(
            interp_time,
            interp_traj[:, joint_idx],
            kind='cubic',
            fill_value='extrapolate'
        )
        aligned_interp[:, joint_idx] = interpolator(aligned_time)

    if swap:
        return aligned_interp, aligned_base, aligned_time
    else:
        return aligned_base, aligned_interp, aligned_time


def compute_tracking_metrics(reference_traj, actual_traj, timestamps):
    """
    计算跟踪性能指标

    reference_traj: 参考轨迹（遥操臂）
    actual_traj: 实际轨迹（真机）
    """
    # 1. 位置误差
    position_error = actual_traj - reference_traj
    position_error_norm = np.linalg.norm(position_error, axis=1)

    # 2. 统计指标（使用鲁棒统计量）
    metrics = {
        # 位置误差
        'mean_position_error': np.mean(position_error_norm),
        'median_position_error': np.median(position_error_norm),
        'rms_position_error': np.sqrt(np.mean(position_error_norm ** 2)),
        'max_position_error': np.percentile(position_error_norm, 95),  # 95%而非100%

        # 每个关节的误差
        'per_joint_mean_error': np.mean(np.abs(position_error), axis=0).tolist(),
        'per_joint_rms_error': np.sqrt(np.mean(position_error ** 2, axis=0)).tolist(),

        # 相关性（越接近1越好）
        'correlation': np.corrcoef(
            reference_traj.flatten(),
            actual_traj.flatten()
        )[0, 1],

        # 数据质量
        'num_samples': len(timestamps),
        'duration': timestamps[-1] - timestamps[0]
    }

    # 3. 时间延迟估计（使用互相关）
    delays = []
    for joint_idx in range(reference_traj.shape[1]):
        ref = reference_traj[:, joint_idx]
        act = actual_traj[:, joint_idx]

        # 计算互相关
        correlation = np.correlate(ref - np.mean(ref), act - np.mean(act), mode='full')
        lag = np.argmax(correlation) - (len(ref) - 1)

        # 转换为时间
        dt = np.mean(np.diff(timestamps))
        delay = lag * dt
        delays.append(delay)

    metrics['mean_delay'] = np.mean(delays)
    metrics['per_joint_delay'] = delays

    return metrics, position_error


def evaluate_tracking(rosbag_path, reference_topic, actual_topic, output_dir):
    """评估跟踪性能"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"跟踪性能评估")
    print(f"{'='*60}\n")

    # 提取轨迹
    print(f"提取参考轨迹: {reference_topic}")
    ref_traj, ref_time = extract_trajectory(rosbag_path, reference_topic)
    if ref_traj is None:
        print("❌ 无法提取参考轨迹")
        return

    print(f"  ✓ 提取了 {len(ref_traj)} 个样本")

    print(f"\n提取实际轨迹: {actual_topic}")
    act_traj, act_time = extract_trajectory(rosbag_path, actual_topic)
    if act_traj is None:
        print("❌ 无法提取实际轨迹")
        return

    print(f"  ✓ 提取了 {len(act_traj)} 个样本")

    # 对齐轨迹
    print(f"\n对齐轨迹到相同时间轴...")
    ref_aligned, act_aligned, aligned_time = align_trajectories(
        ref_traj, ref_time, act_traj, act_time
    )
    print(f"  ✓ 对齐后样本数: {len(aligned_time)}")

    # 计算跟踪指标
    print(f"\n计算跟踪性能指标...")
    metrics, position_error = compute_tracking_metrics(
        ref_aligned, act_aligned, aligned_time
    )

    # 打印结果
    print(f"\n{'='*60}")
    print(f"跟踪性能指标")
    print(f"{'='*60}\n")
    print(f"位置误差（整体）:")
    print(f"  平均误差: {metrics['mean_position_error']:.4f} rad ({metrics['mean_position_error']*57.3:.2f}°)")
    print(f"  中位误差: {metrics['median_position_error']:.4f} rad ({metrics['median_position_error']*57.3:.2f}°)")
    print(f"  RMS误差: {metrics['rms_position_error']:.4f} rad ({metrics['rms_position_error']*57.3:.2f}°)")
    print(f"  95%误差: {metrics['max_position_error']:.4f} rad ({metrics['max_position_error']*57.3:.2f}°)")

    print(f"\n每个关节的RMS误差:")
    for i, error in enumerate(metrics['per_joint_rms_error']):
        print(f"  关节{i+1}: {error:.4f} rad ({error*57.3:.2f}°)")

    print(f"\n时间延迟:")
    print(f"  平均延迟: {metrics['mean_delay']*1000:.1f} ms")

    print(f"\n相关性:")
    print(f"  轨迹相关系数: {metrics['correlation']:.4f}")

    # 保存结果
    with open(output_dir / 'tracking_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"\n✓ 结果保存到: {output_dir / 'tracking_metrics.json'}")

    # 生成可视化
    generate_tracking_plots(
        ref_aligned, act_aligned, aligned_time, position_error, metrics, output_dir
    )

    print(f"✓ 可视化保存到: {output_dir}")


def generate_tracking_plots(ref_traj, act_traj, timestamps, error, metrics, output_dir):
    """生成跟踪性能可视化"""
    timestamps = timestamps - timestamps[0]  # 从0开始

    # 1. 轨迹对比（第一个关节）
    fig, axes = plt.subplots(3, 1, figsize=(15, 10))

    # 位置对比
    axes[0].plot(timestamps, ref_traj[:, 0], label='Reference (Exo)', alpha=0.7)
    axes[0].plot(timestamps, act_traj[:, 0], label='Actual (Robot)', alpha=0.7)
    axes[0].set_ylabel('Position (rad)')
    axes[0].set_title('Joint 1: Position Tracking')
    axes[0].legend()
    axes[0].grid(True)

    # 误差
    axes[1].plot(timestamps, error[:, 0], color='red', alpha=0.7)
    axes[1].axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    axes[1].set_ylabel('Error (rad)')
    axes[1].set_title('Joint 1: Tracking Error')
    axes[1].grid(True)

    # 误差范数
    error_norm = np.linalg.norm(error, axis=1)
    axes[2].plot(timestamps, error_norm, color='purple', alpha=0.7)
    axes[2].axhline(y=metrics['mean_position_error'], color='green',
                    linestyle='--', label=f"Mean: {metrics['mean_position_error']:.3f} rad")
    axes[2].set_xlabel('Time (s)')
    axes[2].set_ylabel('Error Norm (rad)')
    axes[2].set_title('Overall Tracking Error')
    axes[2].legend()
    axes[2].grid(True)

    plt.tight_layout()
    plt.savefig(output_dir / 'tracking_performance.png', dpi=150)
    plt.close()

    print(f"  ✓ 生成跟踪性能图: tracking_performance.png")


def main():
    parser = argparse.ArgumentParser(description='评估跟踪性能')
    parser.add_argument('--rosbag', required=True, help='rosbag目录')
    parser.add_argument('--reference', required=True, help='参考轨迹话题（遥操臂）')
    parser.add_argument('--actual', required=True, help='实际轨迹话题（真机）')
    parser.add_argument('--output', default='tracking_evaluation', help='输出目录')

    args = parser.parse_args()

    evaluate_tracking(args.rosbag, args.reference, args.actual, args.output)


if __name__ == '__main__':
    main()