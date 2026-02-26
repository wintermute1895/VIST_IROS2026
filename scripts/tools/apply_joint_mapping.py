#!/usr/bin/env python3
"""
应用关节方向映射到录制的数据
用于修正关节方向反向的问题
"""

import argparse
import numpy as np
import yaml
from pathlib import Path

from rosbag2_py import SequentialReader, SequentialWriter, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message, serialize_message
from sensor_msgs.msg import JointState


def apply_joint_mapping(rosbag_path, config_path, output_path):
    """应用关节方向映射"""

    # 读取配置
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    joint_mapping = config.get('joint_mapping', {})
    if not joint_mapping.get('enabled', False):
        print("关节方向映射未启用")
        return

    right_arm_direction = np.array(joint_mapping.get('right_arm_direction', [1]*7))
    left_arm_direction = np.array(joint_mapping.get('left_arm_direction', [1]*7))

    print(f"\n应用关节方向映射:")
    print(f"  右臂方向: {right_arm_direction}")
    print(f"  左臂方向: {left_arm_direction}")
    print()

    # 打开输入rosbag
    storage_options_in = StorageOptions(uri=str(rosbag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options_in, converter_options)

    # 创建输出rosbag
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    storage_options_out = StorageOptions(uri=str(output_path), storage_id='sqlite3')
    writer = SequentialWriter()
    writer.open(storage_options_out, converter_options)

    # 获取话题信息
    topic_types = reader.get_all_topics_and_types()
    for topic_metadata in topic_types:
        writer.create_topic(topic_metadata)

    # 处理消息
    processed_count = 0
    mapped_count = 0

    while reader.has_next():
        topic, data, timestamp = reader.read_next()

        # 检查是否是需要映射的话题
        if 'joint' in topic.lower() and ('control' in topic.lower() or 'follow' in topic.lower() or 'state' in topic.lower()):
            try:
                msg = deserialize_message(data, JointState)

                # 应用方向映射
                if len(msg.position) >= 7:
                    # 判断是左臂还是右臂
                    if 'right' in topic.lower():
                        direction = right_arm_direction
                    elif 'left' in topic.lower():
                        direction = left_arm_direction
                    else:
                        direction = right_arm_direction  # 默认右臂

                    # 应用映射
                    original_position = np.array(msg.position[:7])
                    mapped_position = original_position * direction
                    msg.position = list(mapped_position) + list(msg.position[7:])

                    # 如果有速度，也应用映射
                    if len(msg.velocity) >= 7:
                        original_velocity = np.array(msg.velocity[:7])
                        mapped_velocity = original_velocity * direction
                        msg.velocity = list(mapped_velocity) + list(msg.velocity[7:])

                    mapped_count += 1

                # 重新序列化
                data = serialize_message(msg)
            except Exception as e:
                print(f"警告：处理消息失败: {e}")

        # 写入输出
        writer.write(topic, data, timestamp)
        processed_count += 1

        if processed_count % 1000 == 0:
            print(f"已处理 {processed_count} 条消息，映射 {mapped_count} 条")

    print(f"\n完成！")
    print(f"  总消息数: {processed_count}")
    print(f"  映射消息数: {mapped_count}")
    print(f"  输出路径: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='应用关节方向映射')
    parser.add_argument('--rosbag', required=True, help='输入rosbag路径')
    parser.add_argument('--config', required=True, help='配置文件路径')
    parser.add_argument('--output', required=True, help='输出rosbag路径')

    args = parser.parse_args()

    apply_joint_mapping(args.rosbag, args.config, args.output)


if __name__ == '__main__':
    main()