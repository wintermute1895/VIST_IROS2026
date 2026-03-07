#!/usr/bin/env python3
"""
分析 rosbag 中的灵巧手状态数据
检查 /cb_left_hand_state 话题的数据质量
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState


def analyze_hand_state(bag_path: str):
    """分析灵巧手状态数据"""

    print(f"正在分析 rosbag: {bag_path}")
    print("=" * 80)

    # 打开 rosbag
    storage_options = StorageOptions(uri=bag_path, storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    # 存储数据
    timestamps = []
    positions = []
    velocities = []
    efforts = []
    joint_names = None

    # 读取所有消息
    topic = '/cb_left_hand_state'
    message_count = 0

    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name == topic:
            try:
                msg = deserialize_message(data, JointState)

                # 保存关节名称（只需要一次）
                if joint_names is None:
                    joint_names = msg.name
                    print(f"\n关节名称: {joint_names}")
                    print(f"关节数量: {len(joint_names)}")

                # 保存数据
                timestamps.append(timestamp * 1e-9)  # 转换为秒
                positions.append(list(msg.position))
                velocities.append(list(msg.velocity))
                efforts.append(list(msg.effort))

                message_count += 1

            except Exception as e:
                print(f"解析消息失败: {e}")
                continue

    if message_count == 0:
        print(f"\n❌ 未找到 {topic} 话题的数据！")
        return

    print(f"\n✓ 成功读取 {message_count} 条消息")

    # 转换为 numpy 数组
    timestamps = np.array(timestamps)
    positions = np.array(positions)  # shape: (N, 10)
    velocities = np.array(velocities)
    efforts = np.array(efforts)

    # 归零时间戳
    timestamps = timestamps - timestamps[0]

    # 统计信息
    print("\n" + "=" * 80)
    print("数据统计")
    print("=" * 80)
    print(f"录制时长: {timestamps[-1]:.2f} 秒")
    print(f"消息数量: {message_count}")
    print(f"平均频率: {message_count / timestamps[-1]:.2f} Hz")

    # 计算时间间隔
    dt = np.diff(timestamps)
    print(f"\n时间间隔统计:")
    print(f"  平均: {np.mean(dt)*1000:.2f} ms")
    print(f"  标准差: {np.std(dt)*1000:.2f} ms")
    print(f"  最小: {np.min(dt)*1000:.2f} ms")
    print(f"  最大: {np.max(dt)*1000:.2f} ms")

    # 关节角度统计
    print(f"\n关节角度统计 (position):")
    for i, name in enumerate(joint_names):
        pos = positions[:, i]
        print(f"  {name:20s}: min={np.min(pos):7.2f}, max={np.max(pos):7.2f}, "
              f"mean={np.mean(pos):7.2f}, std={np.std(pos):7.2f}")

    # 检查数据质量
    print(f"\n数据质量检查:")

    # 检查是否有 NaN 或 Inf
    has_nan = np.any(np.isnan(positions))
    has_inf = np.any(np.isinf(positions))
    print(f"  包含 NaN: {'❌ 是' if has_nan else '✓ 否'}")
    print(f"  包含 Inf: {'❌ 是' if has_inf else '✓ 否'}")

    # 检查是否有数据变化
    pos_range = np.max(positions, axis=0) - np.min(positions, axis=0)
    static_joints = np.where(pos_range < 1.0)[0]  # 变化小于1度的关节
    if len(static_joints) > 0:
        print(f"  ⚠ 静止关节 (变化<1°): {[joint_names[i] for i in static_joints]}")
    else:
        print(f"  ✓ 所有关节都有运动")

    # 检查速度数据
    vel_nonzero = np.any(velocities != 0)
    print(f"  速度数据非零: {'✓ 是' if vel_nonzero else '⚠ 否 (可能未启用速度反馈)'}")

    # 检查力矩数据
    eff_nonzero = np.any(efforts != 0)
    print(f"  力矩数据非零: {'✓ 是' if eff_nonzero else '⚠ 否 (可能未启用力矩反馈)'}")

    # 生成可视化
    print(f"\n生成可视化...")

    fig, axes = plt.subplots(3, 1, figsize=(15, 12))

    # 绘制关节角度
    ax = axes[0]
    for i, name in enumerate(joint_names):
        ax.plot(timestamps, positions[:, i], label=name, alpha=0.7, linewidth=1)
    ax.set_ylabel('Position (degrees)')
    ax.set_title(f'Dexterous Hand Joint Positions - {message_count} samples @ {message_count/timestamps[-1]:.1f} Hz')
    ax.legend(loc='upper right', ncol=2, fontsize=8)
    ax.grid(True, alpha=0.3)

    # 绘制关节速度（如果有数据）
    ax = axes[1]
    if vel_nonzero:
        for i, name in enumerate(joint_names):
            ax.plot(timestamps, velocities[:, i], label=name, alpha=0.7, linewidth=1)
        ax.set_ylabel('Velocity (deg/s)')
        ax.set_title('Joint Velocities')
        ax.legend(loc='upper right', ncol=2, fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No velocity data', ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='gray')
        ax.set_ylabel('Velocity (deg/s)')
        ax.set_title('Joint Velocities (No Data)')
    ax.grid(True, alpha=0.3)

    # 绘制时间间隔分布
    ax = axes[2]
    ax.plot(timestamps[1:], dt * 1000, 'b-', linewidth=1, alpha=0.7)
    ax.axhline(y=np.mean(dt)*1000, color='r', linestyle='--',
               label=f'Mean: {np.mean(dt)*1000:.2f} ms')
    ax.set_ylabel('Time Interval (ms)')
    ax.set_xlabel('Time (s)')
    ax.set_title('Message Time Intervals')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    # 保存图像
    output_file = Path(bag_path) / 'hand_state_analysis.png'
    plt.savefig(output_file, dpi=300)
    print(f"✓ 可视化已保存: {output_file}")

    # 保存数据摘要
    summary_file = Path(bag_path) / 'hand_state_summary.txt'
    with open(summary_file, 'w') as f:
        f.write(f"灵巧手状态数据分析报告\n")
        f.write(f"=" * 80 + "\n\n")
        f.write(f"Rosbag: {bag_path}\n")
        f.write(f"话题: {topic}\n")
        f.write(f"消息类型: sensor_msgs/JointState\n\n")
        f.write(f"录制时长: {timestamps[-1]:.2f} 秒\n")
        f.write(f"消息数量: {message_count}\n")
        f.write(f"平均频率: {message_count / timestamps[-1]:.2f} Hz\n\n")
        f.write(f"关节名称: {joint_names}\n\n")
        f.write(f"时间间隔统计:\n")
        f.write(f"  平均: {np.mean(dt)*1000:.2f} ms\n")
        f.write(f"  标准差: {np.std(dt)*1000:.2f} ms\n")
        f.write(f"  最小: {np.min(dt)*1000:.2f} ms\n")
        f.write(f"  最大: {np.max(dt)*1000:.2f} ms\n\n")
        f.write(f"关节角度范围:\n")
        for i, name in enumerate(joint_names):
            pos = positions[:, i]
            f.write(f"  {name}: [{np.min(pos):.2f}, {np.max(pos):.2f}]\n")

    print(f"✓ 数据摘要已保存: {summary_file}")

    print("\n" + "=" * 80)
    print("分析完成！")
    print("=" * 80)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 analyze_hand_state.py <rosbag_path>")
        print("示例: python3 analyze_hand_state.py /path/to/experiment_dir")
        sys.exit(1)

    bag_path = sys.argv[1]
    analyze_hand_state(bag_path)
