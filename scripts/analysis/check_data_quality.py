#!/usr/bin/env python3
"""
检查数据质量，查找跳变和异常点
"""

import argparse
import numpy as np
from pathlib import Path

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
            except Exception as e:
                continue

    if not trajectories:
        return None, None

    return np.array(trajectories), np.array(timestamps)


def analyze_data_quality(trajectory, timestamps, topic_name):
    """分析数据质量"""
    print(f"\n{'='*60}")
    print(f"数据质量分析: {topic_name}")
    print(f"{'='*60}\n")

    # 基本信息
    print(f"样本数: {len(trajectory)}")
    print(f"时长: {timestamps[-1] - timestamps[0]:.2f}秒")
    print(f"频率: {len(trajectory) / (timestamps[-1] - timestamps[0]):.2f} Hz")
    print(f"关节数: {trajectory.shape[1]}")

    # 计算时间间隔
    dt = np.diff(timestamps)
    print(f"\n时间间隔统计:")
    print(f"  平均: {np.mean(dt)*1000:.2f} ms")
    print(f"  最小: {np.min(dt)*1000:.2f} ms")
    print(f"  最大: {np.max(dt)*1000:.2f} ms")
    print(f"  标准差: {np.std(dt)*1000:.2f} ms")

    # 对每个关节分析
    for joint_idx in range(trajectory.shape[1]):
        joint_data = trajectory[:, joint_idx]

        # 计算位置变化
        position_diff = np.diff(joint_data)

        # 计算速度（rad/s）
        velocity = position_diff / dt

        # 找出异常大的速度
        velocity_threshold = 10.0  # rad/s
        large_velocity_indices = np.where(np.abs(velocity) > velocity_threshold)[0]

        if len(large_velocity_indices) > 0:
            print(f"\n关节 {joint_idx+1} 异常速度点:")
            print(f"  总数: {len(large_velocity_indices)}")
            print(f"  最大速度: {np.max(np.abs(velocity)):.2f} rad/s")

            # 显示前5个异常点的详细信息
            for i in range(min(5, len(large_velocity_indices))):
                idx = large_velocity_indices[i]
                print(f"  [{idx}] 位置变化: {position_diff[idx]:.6f} rad, "
                      f"时间间隔: {dt[idx]*1000:.2f} ms, "
                      f"速度: {velocity[idx]:.2f} rad/s")


def main():
    parser = argparse.ArgumentParser(description='检查数据质量')
    parser.add_argument('--rosbag', required=True, help='rosbag目录路径')
    parser.add_argument('--topic', required=True, help='话题名称')

    args = parser.parse_args()

    trajectory, timestamps = extract_trajectory(args.rosbag, args.topic)

    if trajectory is None:
        print("❌ 没有数据")
        return

    analyze_data_quality(trajectory, timestamps, args.topic)


if __name__ == '__main__':
    main()