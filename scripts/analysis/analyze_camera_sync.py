#!/usr/bin/env python3
"""
分析双相机 rosbag 数据的时间戳对齐情况
使用硬件时间戳 (msg.header.stamp) 进行分析
"""
import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import get_typestore, Stores


# ================= 配置区域 =================
# 默认数据路径（可通过命令行参数覆盖）
# 注意：应该传入包含 .db3 文件的目录，而不是 .db3 文件本身
DEFAULT_BAG_PATH = "/media/ilex/Cyan_data/data/one_euro_filter/oneeuro_0305_10group_round_3_data/experiment_20260305_174156_s"

# 相机话题配置（双 D435i 独立模式 + 全局时间戳）
CAMERA1_TOPIC = '/camera_global/camera_global/color/image_raw'  # D435i 全局相机（基准）
CAMERA2_TOPIC = '/camera_wrist/camera_wrist/color/image_raw'    # D435i 腕部相机（对比）

# 输出图片路径
OUTPUT_IMAGE = "timestamp_analysis.png"
# ============================================


def extract_timestamps(bag_path, topic_name):
    """
    从 rosbag 中提取指定话题的硬件时间戳

    Args:
        bag_path: rosbag 文件夹路径
        topic_name: 话题名称

    Returns:
        timestamps: numpy array of timestamps in seconds (float)
    """
    timestamps = []

    try:
        typestore = get_typestore(Stores.ROS2_HUMBLE)

        with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
            # 检查话题是否存在
            topics = [conn.topic for conn in reader.connections]
            if topic_name not in topics:
                print(f"警告: 话题 {topic_name} 不存在于 bag 中")
                return np.array([])

            # 找到对应话题的连接
            connections = [x for x in reader.connections if x.topic == topic_name]

            print(f"正在提取 {topic_name} 的时间戳...")

            # 遍历消息
            for connection, _, rawdata in reader.messages(connections=connections):
                msg = reader.deserialize(rawdata, connection.msgtype)

                # 提取硬件时间戳 (msg.header.stamp)
                if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
                    # ROS2 时间戳格式: sec + nanosec
                    stamp_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
                    timestamps.append(stamp_sec)

    except Exception as e:
        print(f"错误: 提取时间戳失败 - {e}")
        import traceback
        traceback.print_exc()
        return np.array([])

    return np.array(timestamps)


def find_nearest_neighbor_sync(timestamps1, timestamps2):
    """
    以 timestamps1 为基准，为每一帧在 timestamps2 中找最近邻

    Args:
        timestamps1: 基准相机的时间戳数组 (秒)
        timestamps2: 对比相机的时间戳数组 (秒)

    Returns:
        matched_pairs: list of tuples (t1, t2, delta_ms)
            t1: 基准相机时间戳
            t2: 匹配的对比相机时间戳
            delta_ms: 时间差 (毫秒), delta = t2 - t1
    """
    matched_pairs = []

    for t1 in timestamps1:
        # 找到与 t1 最接近的 t2
        idx = np.argmin(np.abs(timestamps2 - t1))
        t2 = timestamps2[idx]

        # 计算时间差 (转换为毫秒)
        delta_ms = (t2 - t1) * 1000.0

        matched_pairs.append((t1, t2, delta_ms))

    return matched_pairs


def compute_statistics(matched_pairs):
    """
    计算时间差的统计信息

    Args:
        matched_pairs: list of (t1, t2, delta_ms)

    Returns:
        stats: dict with keys: count, mean, max, std
    """
    if not matched_pairs:
        return None

    deltas = np.array([pair[2] for pair in matched_pairs])

    stats = {
        'count': len(deltas),
        'mean': np.mean(deltas),
        'max': np.max(np.abs(deltas)),
        'std': np.std(deltas),
        'min': np.min(deltas),
        'max_raw': np.max(deltas)
    }

    return stats


def plot_analysis(matched_pairs, output_path):
    """
    绘制时间差分析图

    Args:
        matched_pairs: list of (t1, t2, delta_ms)
        output_path: 输出图片路径
    """
    if not matched_pairs:
        print("警告: 没有匹配数据，无法绘图")
        return

    # 提取数据
    t1_array = np.array([pair[0] for pair in matched_pairs])
    deltas = np.array([pair[2] for pair in matched_pairs])

    # 将时间戳转换为相对时间（从0开始，单位：秒）
    t1_relative = t1_array - t1_array[0]

    # 创建图形
    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # 图1: 时间差随时间变化的折线图
    ax1.plot(t1_relative, deltas, linewidth=0.8, alpha=0.7)
    ax1.axhline(y=0, color='r', linestyle='--', linewidth=1, alpha=0.5, label='Zero offset')
    ax1.set_xlabel('Time (s)', fontsize=12)
    ax1.set_ylabel('Time Offset (ms)', fontsize=12)
    ax1.set_title('Camera Timestamp Synchronization: Offset over Time', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 图2: 时间差分布直方图
    ax2.hist(deltas, bins=50, edgecolor='black', alpha=0.7)
    ax2.axvline(x=0, color='r', linestyle='--', linewidth=1, alpha=0.5, label='Zero offset')
    ax2.set_xlabel('Time Offset (ms)', fontsize=12)
    ax2.set_ylabel('Frequency', fontsize=12)
    ax2.set_title('Camera Timestamp Offset Distribution', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ 分析图已保存至: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='分析双相机 rosbag 数据的时间戳对齐情况',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python3 analyze_camera_sync.py
  python3 analyze_camera_sync.py --bag /path/to/rosbag_data
  python3 analyze_camera_sync.py --bag /path/to/rosbag_data --output sync_result.png
        """
    )

    parser.add_argument(
        '--bag',
        type=str,
        default=DEFAULT_BAG_PATH,
        help=f'rosbag 文件夹路径 (默认: {DEFAULT_BAG_PATH})'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=OUTPUT_IMAGE,
        help=f'输出图片路径 (默认: {OUTPUT_IMAGE})'
    )

    args = parser.parse_args()

    bag_path = args.bag
    output_path = args.output

    # 检查路径是否存在
    if not os.path.exists(bag_path):
        print(f"错误: 路径不存在: {bag_path}")
        sys.exit(1)

    print("="*70)
    print("双相机时间戳同步分析")
    print("="*70)
    print(f"Bag 路径: {bag_path}")
    print(f"基准相机: {CAMERA1_TOPIC}")
    print(f"对比相机: {CAMERA2_TOPIC}")
    print("="*70)

    # 1. 提取两个相机的时间戳
    print("\n[步骤 1/4] 提取时间戳...")
    timestamps1 = extract_timestamps(bag_path, CAMERA1_TOPIC)
    timestamps2 = extract_timestamps(bag_path, CAMERA2_TOPIC)

    if len(timestamps1) == 0 or len(timestamps2) == 0:
        print("错误: 无法提取时间戳，请检查话题名称和 bag 文件")
        sys.exit(1)

    print(f"  ✓ {CAMERA1_TOPIC}: {len(timestamps1)} 帧")
    print(f"  ✓ {CAMERA2_TOPIC}: {len(timestamps2)} 帧")

    # 2. 最近邻匹配
    print("\n[步骤 2/4] 执行最近邻时间戳匹配...")
    matched_pairs = find_nearest_neighbor_sync(timestamps1, timestamps2)
    print(f"  ✓ 匹配完成: {len(matched_pairs)} 对")

    # 3. 计算统计信息
    print("\n[步骤 3/4] 计算统计信息...")
    stats = compute_statistics(matched_pairs)

    if stats:
        print("\n" + "="*70)
        print("时间戳对齐统计结果")
        print("="*70)
        print(f"匹配帧对数:        {stats['count']}")
        print(f"平均时间差:        {stats['mean']:.3f} ms")
        print(f"最大时间差:        {stats['max']:.3f} ms")
        print(f"标准差:            {stats['std']:.3f} ms")
        print(f"时间差范围:        [{stats['min']:.3f}, {stats['max_raw']:.3f}] ms")
        print("="*70)

        # 评估同步质量
        if stats['max'] < 5.0:
            quality = "优秀 (< 5ms)"
        elif stats['max'] < 10.0:
            quality = "良好 (< 10ms)"
        elif stats['max'] < 20.0:
            quality = "可接受 (< 20ms)"
        else:
            quality = "较差 (>= 20ms)"

        print(f"\n同步质量评估: {quality}")
        print("="*70)

    # 4. 绘制分析图
    print("\n[步骤 4/4] 生成可视化图表...")
    plot_analysis(matched_pairs, output_path)

    print("\n✓ 分析完成！")


if __name__ == '__main__':
    main()
