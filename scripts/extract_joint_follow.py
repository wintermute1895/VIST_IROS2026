#!/usr/bin/env python3
"""
提取joint_follow话题的数据
使用正确的消息类型 lbot_arm_interfaces/msg/FollowJoint
"""

import argparse
import numpy as np
from pathlib import Path

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from lbot_arm_interfaces.msg import FollowJoint


def extract_joint_follow(rosbag_path, topic):
    """从rosbag中提取FollowJoint话题的数据"""
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
                msg = deserialize_message(data, FollowJoint)
                if len(msg.joints) > 0:
                    positions.append(np.array(msg.joints))
                    timestamps.append(timestamp * 1e-9)
            except Exception as e:
                print(f"警告：反序列化消息失败: {e}")
                continue

    if not positions:
        return None, None

    return np.array(positions), np.array(timestamps)


def main():
    parser = argparse.ArgumentParser(description='提取joint_follow话题数据')
    parser.add_argument('--rosbag', required=True, help='rosbag目录路径')
    parser.add_argument('--topic', default='/robot1/right_arm/joint_follow', help='话题名称')
    parser.add_argument('--output', default='joint_follow_data.npz', help='输出文件')

    args = parser.parse_args()

    print(f"提取话题: {args.topic}")
    positions, timestamps = extract_joint_follow(args.rosbag, args.topic)

    if positions is None:
        print("❌ 没有数据")
        return

    print(f"✓ 提取了 {len(positions)} 个样本")
    print(f"  时长: {timestamps[-1] - timestamps[0]:.2f}秒")
    print(f"  频率: {len(positions) / (timestamps[-1] - timestamps[0]):.2f} Hz")
    print(f"  关节数: {positions.shape[1]}")

    # 显示前几个样本
    print("\n前5个样本:")
    for i in range(min(5, len(positions))):
        print(f"  [{i}] {positions[i]}")

    # 保存数据
    np.savez(args.output, positions=positions, timestamps=timestamps)
    print(f"\n✓ 数据保存到: {args.output}")


if __name__ == '__main__':
    main()