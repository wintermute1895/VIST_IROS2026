#!/usr/bin/env python3
"""
分析视觉控制数据的性能指标
"""
import sys
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def analyze_rosbag(rosbag_path, output_dir=None):
    """分析rosbag中的视觉控制数据"""

    # 连接到数据库
    db_files = sorted(Path(rosbag_path).glob("*.db3"))
    if not db_files:
        print(f"错误: 在 {rosbag_path} 中未找到数据库文件")
        return

    print(f"分析 {len(db_files)} 个数据库文件...")

    # 收集所有数据
    all_timestamps = []
    all_positions = []

    for db_file in db_files:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # 获取话题ID
        cursor.execute("SELECT id FROM topics WHERE name = '/vision_control/joint_follow'")
        result = cursor.fetchone()
        if not result:
            conn.close()
            continue

        topic_id = result[0]

        # 获取消息
        cursor.execute("""
            SELECT timestamp, data
            FROM messages
            WHERE topic_id = ?
            ORDER BY timestamp
        """, (topic_id,))

        for timestamp, data in cursor.fetchall():
            all_timestamps.append(timestamp / 1e9)  # 转换为秒
            # 简单解析：假设前7个float64是关节位置
            # 实际需要根据消息格式正确解析
            all_positions.append(timestamp)  # 占位符

        conn.close()

    if len(all_timestamps) < 2:
        print("错误: 数据不足")
        return

    all_timestamps = np.array(all_timestamps)

    # 计算频率统计
    time_diffs = np.diff(all_timestamps)
    frequencies = 1.0 / time_diffs

    print("\n" + "="*60)
    print("视觉控制性能分析")
    print("="*60)

    print(f"\n📊 数据统计:")
    print(f"  消息总数: {len(all_timestamps)}")
    print(f"  时间跨度: {all_timestamps[-1] - all_timestamps[0]:.2f} 秒")

    print(f"\n⏱️  发布频率:")
    print(f"  平均频率: {np.mean(frequencies):.2f} Hz")
    print(f"  中位频率: {np.median(frequencies):.2f} Hz")
    print(f"  最小频率: {np.min(frequencies):.2f} Hz")
    print(f"  最大频率: {np.max(frequencies):.2f} Hz")
    print(f"  标准差: {np.std(frequencies):.2f} Hz")

    print(f"\n⏲️  时间间隔:")
    print(f"  平均间隔: {np.mean(time_diffs)*1000:.2f} ms")
    print(f"  中位间隔: {np.median(time_diffs)*1000:.2f} ms")
    print(f"  最小间隔: {np.min(time_diffs)*1000:.2f} ms")
    print(f"  最大间隔: {np.max(time_diffs)*1000:.2f} ms")
    print(f"  标准差: {np.std(time_diffs)*1000:.2f} ms")

    # 频率分布
    print(f"\n📈 频率分布:")
    percentiles = [50, 75, 90, 95, 99]
    for p in percentiles:
        val = np.percentile(frequencies, p)
        print(f"  {p}%: {val:.2f} Hz")

    # 如果指定了输出目录，生成图表
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 频率分布图
        plt.figure(figsize=(12, 8))

        plt.subplot(2, 2, 1)
        plt.hist(frequencies, bins=50, edgecolor='black')
        plt.xlabel('频率 (Hz)')
        plt.ylabel('数量')
        plt.title('发布频率分布')
        plt.axvline(np.mean(frequencies), color='r', linestyle='--', label=f'平均: {np.mean(frequencies):.1f} Hz')
        plt.legend()

        plt.subplot(2, 2, 2)
        plt.plot(all_timestamps[1:] - all_timestamps[0], frequencies)
        plt.xlabel('时间 (s)')
        plt.ylabel('频率 (Hz)')
        plt.title('频率随时间变化')
        plt.grid(True)

        plt.subplot(2, 2, 3)
        plt.hist(time_diffs * 1000, bins=50, edgecolor='black')
        plt.xlabel('时间间隔 (ms)')
        plt.ylabel('数量')
        plt.title('时间间隔分布')
        plt.axvline(np.mean(time_diffs)*1000, color='r', linestyle='--',
                   label=f'平均: {np.mean(time_diffs)*1000:.2f} ms')
        plt.legend()

        plt.subplot(2, 2, 4)
        plt.plot(all_timestamps[1:] - all_timestamps[0], time_diffs * 1000)
        plt.xlabel('时间 (s)')
        plt.ylabel('时间间隔 (ms)')
        plt.title('时间间隔随时间变化')
        plt.grid(True)

        plt.tight_layout()
        plot_file = output_path / 'frequency_analysis.png'
        plt.savefig(plot_file, dpi=150)
        print(f"\n📊 图表已保存: {plot_file}")
        plt.close()

    print("\n" + "="*60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 analyze_vision_control.py <rosbag_path> [output_dir]")
        sys.exit(1)

    rosbag_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    analyze_rosbag(rosbag_path, output_dir)