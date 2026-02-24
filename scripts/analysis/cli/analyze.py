"""
统一的rosbag分析CLI工具

用法:
    python -m scripts.analysis.cli.analyze --rosbag <path> --topics <topic1> [topic2...] --output <dir>
"""
import argparse
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState
import numpy as np

try:
    from lbot_arm_interfaces.msg import FollowJoint
    HAS_FOLLOW_JOINT = True
except ImportError:
    HAS_FOLLOW_JOINT = False

from scripts.analysis.core.metrics_calculator import MetricsCalculator


def read_rosbag_topic(rosbag_path: str, topic_name: str):
    """读取rosbag话题数据"""
    storage_options = StorageOptions(uri=rosbag_path, storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    trajectories = []
    timestamps = []

    is_follow_joint = 'joint_follow' in topic_name

    while reader.has_next():
        topic, data, timestamp = reader.read_next()
        if topic == topic_name:
            try:
                if is_follow_joint and HAS_FOLLOW_JOINT:
                    msg = deserialize_message(data, FollowJoint)
                    if len(msg.joints) > 0:
                        trajectories.append(np.array(msg.joints))
                        timestamps.append(timestamp * 1e-9)
                else:
                    msg = deserialize_message(data, JointState)
                    if len(msg.position) > 0:
                        trajectories.append(np.array(msg.position))
                        timestamps.append(timestamp * 1e-9)
            except Exception:
                continue

    if not trajectories:
        return None, None

    return np.array(trajectories), np.array(timestamps)


def main():
    parser = argparse.ArgumentParser(description='统一的rosbag分析工具')
    parser.add_argument('--rosbag', required=True, help='rosbag目录路径')
    parser.add_argument('--topics', nargs='+', required=True, help='要分析的话题列表')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--config', help='配置文件（可选）')

    args = parser.parse_args()

    rosbag_path = Path(args.rosbag)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("VIST Rosbag分析工具")
    print("=" * 60)
    print(f"Rosbag: {rosbag_path}")
    print(f"话题: {', '.join(args.topics)}")
    print(f"输出: {output_dir}")
    print("")

    calculator = MetricsCalculator()
    all_results = {}

    for topic_name in args.topics:
        print(f"[{args.topics.index(topic_name) + 1}/{len(args.topics)}] 分析 {topic_name}...")

        # 读取数据
        trajectory, timestamps = read_rosbag_topic(str(rosbag_path), topic_name)

        if trajectory is None:
            print(f"  ⚠️  无法读取数据")
            continue

        # 计算指标
        metrics = calculator.calculate_all_metrics(trajectory, timestamps)

        # 保存结果
        topic_key = topic_name.replace('/', '_').strip('_')
        all_results[topic_key] = {
            'topic': topic_name,
            'metrics': metrics
        }

        # 打印摘要
        print(f"  ✓ 样本数: {metrics['num_samples']}")
        print(f"  ✓ 频率: {metrics['frequency']:.2f} Hz")
        print(f"  ✓ 平均Jerk: {metrics['avg_jerk']:.4f} rad/s³")
        print("")

    # 保存JSON结果
    json_file = output_dir / 'metrics.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"✓ 结果已保存: {json_file}")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())