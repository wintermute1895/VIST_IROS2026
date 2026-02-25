#!/usr/bin/env python3
"""
使用rosbag2_py正确提取和分析外骨骼数据
"""

import numpy as np
import json
from pathlib import Path
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState


def extract_joint_data(bag_path, topic_name):
    """使用rosbag2_py提取关节数据"""
    storage_options = StorageOptions(uri=str(bag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    timestamps = []
    positions = []

    while reader.has_next():
        topic, data, t = reader.read_next()

        if topic == topic_name:
            msg = deserialize_message(data, JointState)

            if msg.position and len(msg.position) > 0:
                timestamps.append(t / 1e9)  # 转换为秒
                positions.append(list(msg.position))

    return np.array(timestamps), np.array(positions)


def calculate_metrics(timestamps, positions):
    """计算数据质量指标"""
    if len(timestamps) == 0:
        return None

    # 时间间隔
    dt = np.diff(timestamps)

    # 速度（数值微分）
    velocities = np.diff(positions, axis=0) / dt[:, np.newaxis]

    # 加速度（二阶微分）
    accelerations = np.diff(velocities, axis=0) / dt[1:, np.newaxis]

    # 计算抖动（jerk，三阶微分）
    jerks = np.diff(accelerations, axis=0) / dt[2:, np.newaxis]

    metrics = {
        'duration': float(timestamps[-1] - timestamps[0]),
        'num_samples': int(len(timestamps)),
        'avg_frequency': float(len(timestamps) / (timestamps[-1] - timestamps[0])),
        'dt_mean': float(np.mean(dt)),
        'dt_std': float(np.std(dt)),
        'dt_min': float(np.min(dt)),
        'dt_max': float(np.max(dt)),

        # 位置统计
        'position_mean': np.mean(positions, axis=0).tolist(),
        'position_std': np.std(positions, axis=0).tolist(),
        'position_range': np.ptp(positions, axis=0).tolist(),

        # 速度统计
        'velocity_mean': np.mean(np.abs(velocities), axis=0).tolist(),
        'velocity_std': np.std(velocities, axis=0).tolist(),
        'velocity_max': np.max(np.abs(velocities), axis=0).tolist(),
        'velocity_rms': np.sqrt(np.mean(velocities**2, axis=0)).tolist(),

        # 加速度统计
        'acceleration_mean': np.mean(np.abs(accelerations), axis=0).tolist(),
        'acceleration_std': np.std(accelerations, axis=0).tolist(),
        'acceleration_max': np.max(np.abs(accelerations), axis=0).tolist(),
        'acceleration_rms': np.sqrt(np.mean(accelerations**2, axis=0)).tolist(),

        # 抖动统计（平滑度指标）
        'jerk_mean': np.mean(np.abs(jerks), axis=0).tolist(),
        'jerk_std': np.std(jerks, axis=0).tolist(),
        'jerk_max': np.max(np.abs(jerks), axis=0).tolist(),
        'jerk_rms': np.sqrt(np.mean(jerks**2, axis=0)).tolist(),

        # 整体平滑度（所有关节的平均抖动）
        'overall_jerk_rms': float(np.sqrt(np.mean(jerks**2))),
        'overall_velocity_rms': float(np.sqrt(np.mean(velocities**2))),
        'overall_acceleration_rms': float(np.sqrt(np.mean(accelerations**2))),
    }

    return metrics


def print_comparison(raw_metrics, filtered_metrics):
    """打印对比结果"""
    print("\n" + "=" * 80)
    print("数据质量对比分析")
    print("=" * 80)

    print("\n【基本信息】")
    print(f"  无滤波数据:")
    print(f"    - 时长: {raw_metrics['duration']:.2f}s")
    print(f"    - 采样数: {raw_metrics['num_samples']}")
    print(f"    - 平均频率: {raw_metrics['avg_frequency']:.1f} Hz")
    print(f"    - 时间间隔: {raw_metrics['dt_mean']*1000:.2f} ± {raw_metrics['dt_std']*1000:.2f} ms")

    print(f"\n  One-Euro滤波数据:")
    print(f"    - 时长: {filtered_metrics['duration']:.2f}s")
    print(f"    - 采样数: {filtered_metrics['num_samples']}")
    print(f"    - 平均频率: {filtered_metrics['avg_frequency']:.1f} Hz")
    print(f"    - 时间间隔: {filtered_metrics['dt_mean']*1000:.2f} ± {filtered_metrics['dt_std']*1000:.2f} ms")

    print("\n【整体平滑度对比】（越小越平滑）")
    print(f"  抖动RMS (rad/s³):")
    print(f"    - 无滤波: {raw_metrics['overall_jerk_rms']:.4f}")
    print(f"    - One-Euro: {filtered_metrics['overall_jerk_rms']:.4f}")
    improvement = (1 - filtered_metrics['overall_jerk_rms']/raw_metrics['overall_jerk_rms'])*100
    print(f"    - 改善: {improvement:.1f}%")

    print(f"\n  加速度RMS (rad/s²):")
    print(f"    - 无滤波: {raw_metrics['overall_acceleration_rms']:.4f}")
    print(f"    - One-Euro: {filtered_metrics['overall_acceleration_rms']:.4f}")
    improvement = (1 - filtered_metrics['overall_acceleration_rms']/raw_metrics['overall_acceleration_rms'])*100
    print(f"    - 改善: {improvement:.1f}%")

    print(f"\n  速度RMS (rad/s):")
    print(f"    - 无滤波: {raw_metrics['overall_velocity_rms']:.4f}")
    print(f"    - One-Euro: {filtered_metrics['overall_velocity_rms']:.4f}")
    improvement = (1 - filtered_metrics['overall_velocity_rms']/raw_metrics['overall_velocity_rms'])*100
    print(f"    - 改善: {improvement:.1f}%")

    print("\n【各关节抖动RMS对比】(rad/s³)")
    for i in range(min(7, len(raw_metrics['jerk_rms']))):
        raw_jerk = raw_metrics['jerk_rms'][i]
        filtered_jerk = filtered_metrics['jerk_rms'][i]
        improvement = (1 - filtered_jerk/raw_jerk) * 100 if raw_jerk > 0 else 0
        print(f"  关节{i}: {raw_jerk:.4f} → {filtered_jerk:.4f} (改善 {improvement:.1f}%)")

    print("\n【各关节速度RMS】(rad/s)")
    for i in range(min(7, len(raw_metrics['velocity_rms']))):
        print(f"  关节{i}: {raw_metrics['velocity_rms'][i]:.4f} → {filtered_metrics['velocity_rms'][i]:.4f}")

    print("\n" + "=" * 80)


def main():
    # 数据路径
    raw_bag = Path("data/exo_raw_20260225_092520/exo_raw_data")
    filtered_bag = Path("data/exo_oneeuro_20260225_095136/exo_oneeuro_data")

    print("正在提取无滤波数据...")
    raw_timestamps, raw_positions = extract_joint_data(
        raw_bag,
        "/right_arm_joint_control"
    )

    print("正在提取One-Euro滤波数据...")
    filtered_timestamps, filtered_positions = extract_joint_data(
        filtered_bag,
        "/filtered_right_joint_control"
    )

    print(f"✅ 无滤波数据: {len(raw_timestamps)} 个样本")
    print(f"✅ 滤波数据: {len(filtered_timestamps)} 个样本")

    # 计算指标
    print("\n正在计算指标...")
    raw_metrics = calculate_metrics(raw_timestamps, raw_positions)
    filtered_metrics = calculate_metrics(filtered_timestamps, filtered_positions)

    # 打印对比
    print_comparison(raw_metrics, filtered_metrics)

    # 保存结果
    results = {
        'raw': raw_metrics,
        'filtered': filtered_metrics
    }

    output_file = Path("data/filter_comparison_metrics.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ 结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
