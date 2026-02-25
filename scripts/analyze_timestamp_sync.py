#!/usr/bin/env python3
"""
时间戳同步分析工具
分析rosbag中不同话题的时间戳对齐情况
"""

import numpy as np
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState, Image
import sys

def extract_timestamps(bag_path, topic_name, msg_type):
    """提取话题的时间戳"""
    storage_options = StorageOptions(uri=bag_path, storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    timestamps = []

    while reader.has_next():
        topic, data, t = reader.read_next()

        if topic == topic_name:
            try:
                msg = deserialize_message(data, msg_type)
                # 使用消息头的时间戳（如果有）
                if hasattr(msg, 'header') and msg.header.stamp:
                    msg_time = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
                else:
                    # 使用rosbag记录时间
                    msg_time = t * 1e-9
                timestamps.append(msg_time)
            except Exception as e:
                continue

    return np.array(timestamps)


def analyze_sync(bag_path):
    """分析时间戳同步情况"""
    print("=" * 80)
    print("时间戳同步分析")
    print("=" * 80)

    # 提取各话题时间戳
    print("\n正在提取时间戳...")

    ts_joint = extract_timestamps(bag_path, '/right_arm_joint_control', JointState)
    ts_filtered = extract_timestamps(bag_path, '/filtered_right_joint_control', JointState)
    ts_camera = extract_timestamps(bag_path, '/camera/color/image_raw', Image)

    print(f"✅ 外骨骼数据: {len(ts_joint)} 条消息")
    print(f"✅ 滤波数据: {len(ts_filtered)} 条消息")
    print(f"✅ 相机数据: {len(ts_camera)} 条消息")

    # 计算频率
    print("\n" + "=" * 80)
    print("频率分析")
    print("=" * 80)

    if len(ts_joint) > 1:
        dt_joint = np.diff(ts_joint)
        freq_joint = 1.0 / np.mean(dt_joint)
        print(f"\n外骨骼数据:")
        print(f"  平均频率: {freq_joint:.2f} Hz")
        print(f"  时间间隔: {np.mean(dt_joint)*1000:.2f} ± {np.std(dt_joint)*1000:.2f} ms")
        print(f"  最小间隔: {np.min(dt_joint)*1000:.2f} ms")
        print(f"  最大间隔: {np.max(dt_joint)*1000:.2f} ms")

    if len(ts_camera) > 1:
        dt_camera = np.diff(ts_camera)
        freq_camera = 1.0 / np.mean(dt_camera)
        print(f"\n相机数据:")
        print(f"  平均频率: {freq_camera:.2f} Hz")
        print(f"  时间间隔: {np.mean(dt_camera)*1000:.2f} ± {np.std(dt_camera)*1000:.2f} ms")
        print(f"  最小间隔: {np.min(dt_camera)*1000:.2f} ms")
        print(f"  最大间隔: {np.max(dt_camera)*1000:.2f} ms")

    # 时间对齐分析
    print("\n" + "=" * 80)
    print("时间对齐分析")
    print("=" * 80)

    if len(ts_joint) > 0 and len(ts_camera) > 0:
        # 计算时间范围重叠
        joint_start, joint_end = ts_joint[0], ts_joint[-1]
        camera_start, camera_end = ts_camera[0], ts_camera[-1]

        print(f"\n外骨骼数据时间范围: {joint_start:.3f} - {joint_end:.3f} ({joint_end - joint_start:.2f}s)")
        print(f"相机数据时间范围: {camera_start:.3f} - {camera_end:.3f} ({camera_end - camera_start:.2f}s)")

        # 计算时间偏移
        time_offset = camera_start - joint_start
        print(f"\n时间偏移: {time_offset*1000:.2f} ms")
        if abs(time_offset) > 0.1:
            print(f"⚠️  警告: 时间偏移较大 (>{100}ms)")
        else:
            print(f"✅ 时间偏移在可接受范围内")

        # 对于每个相机帧，找到最近的外骨骼数据
        print("\n" + "=" * 80)
        print("数据对齐质量")
        print("=" * 80)

        max_samples = min(100, len(ts_camera))  # 只分析前100帧
        alignment_errors = []

        for cam_t in ts_camera[:max_samples]:
            # 找到最近的外骨骼时间戳
            idx = np.argmin(np.abs(ts_joint - cam_t))
            error = abs(ts_joint[idx] - cam_t)
            alignment_errors.append(error)

        alignment_errors = np.array(alignment_errors)

        print(f"\n对齐误差统计 (前{max_samples}帧):")
        print(f"  平均误差: {np.mean(alignment_errors)*1000:.2f} ms")
        print(f"  标准差: {np.std(alignment_errors)*1000:.2f} ms")
        print(f"  最大误差: {np.max(alignment_errors)*1000:.2f} ms")
        print(f"  最小误差: {np.min(alignment_errors)*1000:.2f} ms")

        # 评估同步质量
        print("\n" + "=" * 80)
        print("同步质量评估")
        print("=" * 80)

        avg_error_ms = np.mean(alignment_errors) * 1000

        if avg_error_ms < 5:
            print("\n✅ 优秀: 平均对齐误差 < 5ms")
        elif avg_error_ms < 10:
            print("\n✅ 良好: 平均对齐误差 < 10ms")
        elif avg_error_ms < 20:
            print("\n⚠️  一般: 平均对齐误差 < 20ms")
        else:
            print("\n❌ 较差: 平均对齐误差 > 20ms")

        print(f"\n建议:")
        if freq_camera < 30:
            print("  - 相机频率偏低，建议提高到30Hz")
        if avg_error_ms > 10:
            print("  - 考虑使用硬件时间戳同步")
            print("  - 或使用message_filters进行软件同步")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 analyze_timestamp_sync.py <rosbag_path>")
        sys.exit(1)

    bag_path = sys.argv[1]
    analyze_sync(bag_path)
