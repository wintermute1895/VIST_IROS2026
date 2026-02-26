#!/usr/bin/env python3
"""
检查原始数据的数值范围
"""

import argparse
import numpy as np
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState


def check_raw_values(rosbag_path, topic):
    """检查原始数据的数值范围"""
    storage_options = StorageOptions(uri=str(rosbag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    positions = []
    timestamps = []

    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name == topic:
            try:
                msg = deserialize_message(data, JointState)
                if len(msg.position) > 0:
                    positions.append(np.array(msg.position))
                    timestamps.append(timestamp * 1e-9)
            except:
                continue

    if not positions:
        print("❌ 没有数据")
        return

    positions = np.array(positions)
    timestamps = np.array(timestamps)

    print(f"\n话题: {topic}")
    print(f"样本数: {len(positions)}")
    print(f"关节数: {positions.shape[1]}")
    print(f"\n前10个样本:")
    for i in range(min(10, len(positions))):
        print(f"  [{i}] {positions[i]}")

    print(f"\n数值范围统计:")
    for j in range(positions.shape[1]):
        joint_data = positions[:, j]
        print(f"  关节{j+1}: min={np.min(joint_data):.4f}, max={np.max(joint_data):.4f}, "
              f"mean={np.mean(joint_data):.4f}, std={np.std(joint_data):.4f}")

    # 计算简单的速度（用于判断单位）
    dt = np.diff(timestamps)
    velocities = []
    for j in range(positions.shape[1]):
        vel = np.diff(positions[:, j]) / dt
        velocities.append(vel)

    velocities = np.array(velocities).T

    print(f"\n简单差分速度统计（用于判断单位）:")
    for j in range(velocities.shape[1]):
        vel_data = velocities[:, j]
        print(f"  关节{j+1}: max_abs_vel={np.max(np.abs(vel_data)):.4f}, "
              f"99%_abs_vel={np.percentile(np.abs(vel_data), 99):.4f}")


def main():
    parser = argparse.ArgumentParser(description='检查原始数据值')
    parser.add_argument('--rosbag', required=True, help='rosbag目录')
    parser.add_argument('--topic', required=True, help='话题名称')

    args = parser.parse_args()
    check_raw_values(args.rosbag, args.topic)


if __name__ == '__main__':
    main()