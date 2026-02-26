#!/usr/bin/env python3
"""
分析外骨骼数据质量和滤波效果
对比无滤波数据和One-Euro滤波数据
"""

import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy import signal


def extract_joint_data_from_bag(bag_path, topic_name):
    """从rosbag中提取关节数据"""
    db_path = Path(bag_path) / f"{Path(bag_path).name}_0.db3"

    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return None, None

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 查询消息
    cursor.execute("""
        SELECT m.timestamp, m.data
        FROM messages m
        JOIN topics t ON m.topic_id = t.id
        WHERE t.name = ?
        ORDER BY m.timestamp
    """, (topic_name,))

    timestamps = []
    positions = []

    for timestamp, data in cursor.fetchall():
        # 解析ROS2消息（简化版，只提取position）
        # 这里需要根据实际的消息格式解析
        try:
            # sensor_msgs/JointState 的 position 字段通常在固定偏移位置
            # 这是一个简化的解析，实际可能需要更复杂的CDR解析
            import struct

            # 跳过header和name字段，找到position数组
            offset = 0
            # 跳过header (timestamp + frame_id)
            offset += 12 + 4  # timestamp (8 bytes) + sec/nanosec (4 bytes)

            # 读取name数组长度
            name_count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # 跳过name字符串
            for _ in range(name_count):
                str_len = struct.unpack_from('<I', data, offset)[0]
                offset += 4 + str_len + (4 - str_len % 4) % 4  # 对齐

            # 读取position数组
            pos_count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            if pos_count > 0:
                positions_data = struct.unpack_from(f'<{pos_count}d', data, offset)
                timestamps.append(timestamp / 1e9)  # 转换为秒
                positions.append(list(positions_data))
        except Exception as e:
            continue

    conn.close()

    if not positions:
        return None, None

    return np.array(timestamps), np.array(positions)


def calculate_metrics(timestamps, positions):
    """计算数据质量指标"""
    if timestamps is None or positions is None or len(timestamps) == 0:
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
        'duration': timestamps[-1] - timestamps[0],
        'num_samples': len(timestamps),
        'avg_frequency': len(timestamps) / (timestamps[-1] - timestamps[0]),
        'dt_mean': np.mean(dt),
        'dt_std': np.std(dt),
        'dt_min': np.min(dt),
        'dt_max': np.max(dt),

        # 位置统计
        'position_mean': np.mean(positions, axis=0),
        'position_std': np.std(positions, axis=0),
        'position_range': np.ptp(positions, axis=0),

        # 速度统计
        'velocity_mean': np.mean(np.abs(velocities), axis=0),
        'velocity_std': np.std(velocities, axis=0),
        'velocity_max': np.max(np.abs(velocities), axis=0),

        # 加速度统计
        'acceleration_mean': np.mean(np.abs(accelerations), axis=0),
        'acceleration_std': np.std(accelerations, axis=0),
        'acceleration_max': np.max(np.abs(accelerations), axis=0),

        # 抖动统计（平滑度指标）
        'jerk_mean': np.mean(np.abs(jerks), axis=0),
        'jerk_std': np.std(jerks, axis=0),
        'jerk_max': np.max(np.abs(jerks), axis=0),

        # 整体平滑度（所有关节的平均抖动）
        'overall_jerk_rms': np.sqrt(np.mean(jerks**2)),
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

    print("\n【平滑度对比】（越小越平滑）")
    print(f"  整体抖动RMS:")
    print(f"    - 无滤波: {raw_metrics['overall_jerk_rms']:.4f}")
    print(f"    - One-Euro: {filtered_metrics['overall_jerk_rms']:.4f}")
    print(f"    - 改善: {(1 - filtered_metrics['overall_jerk_rms']/raw_metrics['overall_jerk_rms'])*100:.1f}%")

    print("\n【各关节抖动对比】")
    for i in range(7):
        raw_jerk = raw_metrics['jerk_mean'][i]
        filtered_jerk = filtered_metrics['jerk_mean'][i]
        improvement = (1 - filtered_jerk/raw_jerk) * 100
        print(f"  关节{i}: {raw_jerk:.4f} → {filtered_jerk:.4f} (改善 {improvement:.1f}%)")

    print("\n【速度统计】")
    print(f"  平均速度 (rad/s):")
    for i in range(7):
        print(f"    关节{i}: {raw_metrics['velocity_mean'][i]:.4f} → {filtered_metrics['velocity_mean'][i]:.4f}")

    print("\n【加速度统计】")
    print(f"  平均加速度 (rad/s²):")
    for i in range(7):
        print(f"    关节{i}: {raw_metrics['acceleration_mean'][i]:.4f} → {filtered_metrics['acceleration_mean'][i]:.4f}")

    print("\n" + "=" * 80)


def main():
    # 数据路径
    raw_bag = Path("data/exo_raw_20260225_092520/exo_raw_data")
    filtered_bag = Path("data/exo_oneeuro_20260225_095136/exo_oneeuro_data")

    print("正在提取无滤波数据...")
    raw_timestamps, raw_positions = extract_joint_data_from_bag(
        raw_bag,
        "/right_arm_joint_control"
    )

    print("正在提取One-Euro滤波数据...")
    filtered_timestamps, filtered_positions = extract_joint_data_from_bag(
        filtered_bag,
        "/filtered_right_joint_control"
    )

    if raw_timestamps is None or filtered_timestamps is None:
        print("❌ 数据提取失败")
        return

    print(f"✅ 无滤波数据: {len(raw_timestamps)} 个样本")
    print(f"✅ 滤波数据: {len(filtered_timestamps)} 个样本")

    # 计算指标
    print("\n正在计算指标...")
    raw_metrics = calculate_metrics(raw_timestamps, raw_positions)
    filtered_metrics = calculate_metrics(filtered_timestamps, filtered_positions)

    if raw_metrics is None or filtered_metrics is None:
        print("❌ 指标计算失败")
        return

    # 打印对比
    print_comparison(raw_metrics, filtered_metrics)

    # 保存结果
    results = {
        'raw': {k: v.tolist() if isinstance(v, np.ndarray) else v
                for k, v in raw_metrics.items()},
        'filtered': {k: v.tolist() if isinstance(v, np.ndarray) else v
                     for k, v in filtered_metrics.items()}
    }

    output_file = Path("data/filter_comparison_metrics.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ 结果已保存到: {output_file}")


if __name__ == "__main__":
    main()