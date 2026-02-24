#!/usr/bin/env python3
"""
对比多个话题的数据
用于分析不同层级数据的差异
使用鲁棒的指标计算方法：均匀重采样 + Savitzky-Golay滤波求导
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState


def extract_trajectory(rosbag_path, topic):
    """从rosbag中提取指定话题的轨迹"""
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
                    timestamps.append(timestamp * 1e-9)  # 转换为秒
            except Exception as e:
                print(f"警告：反序列化消息失败: {e}")
                continue

    if not trajectories:
        return None, None

    trajectory = np.array(trajectories)

    # 单位转换：遥操臂原始数据是角度，需要转换为弧度
    if 'joint_control' in topic and 'robot' not in topic:
        # 这是遥操臂原始输出，单位是角度
        trajectory = np.deg2rad(trajectory)
        print(f"  注意：{topic} 数据从角度转换为弧度")

    return trajectory, np.array(timestamps)


def compute_metrics(trajectory, timestamps):
    """
    计算基础指标（使用鲁棒方法）

    方案：均匀重采样 + Savitzky-Golay滤波求导
    1. 均匀重采样：消除时间戳抖动
    2. SG滤波求导：在平滑曲线上解析求导
    """
    if trajectory is None or len(trajectory) < 20:
        return None

    # 计算原始频率
    total_duration = timestamps[-1] - timestamps[0]
    original_freq = (len(trajectory) - 1) / total_duration if total_duration > 0 else 0

    # 步骤1：均匀重采样
    # 生成均匀时间网格（使用原始频率或250Hz，取较小值）
    target_freq = min(original_freq, 250.0)
    num_samples = int(total_duration * target_freq)

    if num_samples < 20:
        return None

    # 生成均匀时间轴
    uniform_time = np.linspace(timestamps[0], timestamps[-1], num_samples)
    uniform_dt = uniform_time[1] - uniform_time[0]

    # 对每个关节进行插值重采样
    uniform_trajectory = np.zeros((num_samples, trajectory.shape[1]))
    for joint_idx in range(trajectory.shape[1]):
        # 使用三次样条插值
        interpolator = interp1d(
            timestamps,
            trajectory[:, joint_idx],
            kind='cubic',
            fill_value='extrapolate'
        )
        uniform_trajectory[:, joint_idx] = interpolator(uniform_time)

    # 步骤2：使用Savitzky-Golay滤波器计算导数
    # 窗口长度：根据频率自适应调整（约50ms的数据）
    window_length = int(target_freq * 0.05)  # 50ms窗口
    if window_length < 5:
        window_length = 5
    if window_length % 2 == 0:
        window_length += 1
    if window_length > len(uniform_trajectory) // 3:
        window_length = (len(uniform_trajectory) // 3) | 1  # 确保是奇数

    polyorder = min(3, window_length - 1)

    try:
        # 计算位置（0阶导数 - 平滑）
        position_smooth = np.zeros_like(uniform_trajectory)
        # 计算速度（1阶导数）
        velocity = np.zeros_like(uniform_trajectory)
        # 计算加速度（2阶导数）
        acceleration = np.zeros_like(uniform_trajectory)

        for joint_idx in range(trajectory.shape[1]):
            # 平滑位置
            position_smooth[:, joint_idx] = savgol_filter(
                uniform_trajectory[:, joint_idx],
                window_length=window_length,
                polyorder=polyorder,
                deriv=0,
                delta=uniform_dt
            )

            # 计算速度（1阶导数）
            velocity[:, joint_idx] = savgol_filter(
                uniform_trajectory[:, joint_idx],
                window_length=window_length,
                polyorder=polyorder,
                deriv=1,
                delta=uniform_dt
            )

            # 计算加速度（2阶导数）
            acceleration[:, joint_idx] = savgol_filter(
                uniform_trajectory[:, joint_idx],
                window_length=window_length,
                polyorder=polyorder,
                deriv=2,
                delta=uniform_dt
            )

        # 计算Jerk（加速度的导数）
        jerk = np.zeros_like(uniform_trajectory)
        for joint_idx in range(trajectory.shape[1]):
            jerk[:, joint_idx] = savgol_filter(
                acceleration[:, joint_idx],
                window_length=window_length,
                polyorder=polyorder,
                deriv=1,
                delta=uniform_dt
            )

    except Exception as e:
        print(f"警告：SG滤波失败: {e}")
        return None

    # 步骤3：计算统计指标（使用中位数和百分位数）
    # 速度指标
    velocity_abs = np.abs(velocity)
    avg_velocity = np.median(velocity_abs)
    max_velocity = np.percentile(velocity_abs, 99)
    rms_velocity = np.sqrt(np.mean(velocity_abs ** 2))

    # 加速度指标
    acceleration_abs = np.abs(acceleration)
    avg_acceleration = np.median(acceleration_abs)
    max_acceleration = np.percentile(acceleration_abs, 99)
    rms_acceleration = np.sqrt(np.mean(acceleration_abs ** 2))

    # Jerk指标
    jerk_abs = np.abs(jerk)
    avg_jerk = np.median(jerk_abs)
    max_jerk = np.percentile(jerk_abs, 99)
    rms_jerk = np.sqrt(np.mean(jerk_abs ** 2))

    return {
        'frequency': original_freq,
        'resampled_frequency': target_freq,
        'avg_velocity': avg_velocity,
        'max_velocity': max_velocity,
        'rms_velocity': rms_velocity,
        'avg_acceleration': avg_acceleration,
        'max_acceleration': max_acceleration,
        'rms_acceleration': rms_acceleration,
        'avg_jerk': avg_jerk,
        'max_jerk': max_jerk,
        'rms_jerk': rms_jerk,
        'num_samples': len(trajectory),
        'resampled_samples': num_samples,
        'duration': total_duration,
        'sg_window_ms': window_length * uniform_dt * 1000
    }


def compare_topics(rosbag_path, topics, output_dir):
    """对比多个话题的数据"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"对比话题数据")
    print(f"{'='*60}\n")

    results = {}

    # 提取每个话题的数据
    for topic in topics:
        print(f"提取话题: {topic}")
        trajectory, timestamps = extract_trajectory(rosbag_path, topic)

        if trajectory is None:
            print(f"  ⚠️  话题无数据")
            continue

        print(f"  ✓ 提取了 {len(trajectory)} 个样本")

        # 计算指标
        metrics = compute_metrics(trajectory, timestamps)
        if metrics:
            results[topic] = {
                'trajectory': trajectory,
                'timestamps': timestamps,
                'metrics': metrics
            }

    if not results:
        print("\n❌ 没有可用的数据")
        return

    # 生成对比报告
    print(f"\n{'='*60}")
    print(f"指标对比")
    print(f"{'='*60}\n")

    comparison = {}
    for topic, data in results.items():
        metrics = data['metrics']
        print(f"\n话题: {topic}")
        print(f"  原始样本数: {metrics['num_samples']}")
        print(f"  重采样样本数: {metrics['resampled_samples']}")
        print(f"  时长: {metrics['duration']:.2f}秒")
        print(f"  原始频率: {metrics['frequency']:.2f} Hz")
        print(f"  重采样频率: {metrics['resampled_frequency']:.2f} Hz")
        print(f"  SG窗口: {metrics['sg_window_ms']:.1f} ms")
        print(f"  中位速度: {metrics['avg_velocity']:.4f} rad/s ({metrics['avg_velocity']*57.3:.2f}°/s)")
        print(f"  99%速度: {metrics['max_velocity']:.4f} rad/s ({metrics['max_velocity']*57.3:.2f}°/s)")
        print(f"  RMS速度: {metrics['rms_velocity']:.4f} rad/s")
        print(f"  中位加速度: {metrics['avg_acceleration']:.4f} rad/s²")
        print(f"  99%加速度: {metrics['max_acceleration']:.4f} rad/s²")
        print(f"  RMS加速度: {metrics['rms_acceleration']:.4f} rad/s²")
        print(f"  中位Jerk: {metrics['avg_jerk']:.4f} rad/s³")
        print(f"  99%Jerk: {metrics['max_jerk']:.4f} rad/s³")
        print(f"  RMS Jerk: {metrics['rms_jerk']:.4f} rad/s³")

        comparison[topic] = metrics

    # 保存对比结果
    with open(output_dir / 'comparison.json', 'w') as f:
        json.dump(comparison, f, indent=2)

    print(f"\n✓ 对比结果保存到: {output_dir / 'comparison.json'}")

    # 生成可视化
    generate_plots(results, output_dir)

    print(f"\n✓ 可视化图表保存到: {output_dir}")


def generate_plots(results, output_dir):
    """生成对比图表"""
    if len(results) == 0:
        return

    # 1. 轨迹对比（第一个关节）
    plt.figure(figsize=(15, 10))

    # 1.1 位置对比
    plt.subplot(3, 1, 1)
    for topic, data in results.items():
        trajectory = data['trajectory']
        timestamps = data['timestamps']
        timestamps = timestamps - timestamps[0]  # 从0开始
        plt.plot(timestamps, trajectory[:, 0], label=topic, alpha=0.7)
    plt.xlabel('时间 (s)')
    plt.ylabel('关节角度 (rad)')
    plt.title('关节1位置对比')
    plt.legend()
    plt.grid(True)

    # 1.2 速度对比
    plt.subplot(3, 1, 2)
    for topic, data in results.items():
        trajectory = data['trajectory']
        timestamps = data['timestamps']
        timestamps = timestamps - timestamps[0]
        dt = np.diff(timestamps)
        velocity = np.diff(trajectory[:, 0]) / dt
        plt.plot(timestamps[1:], velocity, label=topic, alpha=0.7)
    plt.xlabel('时间 (s)')
    plt.ylabel('关节速度 (rad/s)')
    plt.title('关节1速度对比')
    plt.legend()
    plt.grid(True)

    # 1.3 加速度对比
    plt.subplot(3, 1, 3)
    for topic, data in results.items():
        trajectory = data['trajectory']
        timestamps = data['timestamps']
        timestamps = timestamps - timestamps[0]
        dt = np.diff(timestamps)
        velocity = np.diff(trajectory[:, 0]) / dt
        acceleration = np.diff(velocity) / dt[1:]
        plt.plot(timestamps[2:], acceleration, label=topic, alpha=0.7)
    plt.xlabel('时间 (s)')
    plt.ylabel('关节加速度 (rad/s²)')
    plt.title('关节1加速度对比')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.savefig(output_dir / 'trajectory_comparison.png', dpi=150)
    plt.close()

    # 2. 指标对比柱状图
    metrics_names = ['frequency', 'avg_velocity', 'max_velocity', 'avg_jerk', 'max_jerk']
    metrics_labels = ['频率 (Hz)', '平均速度 (rad/s)', '最大速度 (rad/s)', '平均Jerk (rad/s³)', '最大Jerk (rad/s³)']

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, (metric_name, metric_label) in enumerate(zip(metrics_names, metrics_labels)):
        ax = axes[idx]
        topics_list = list(results.keys())
        values = [results[topic]['metrics'][metric_name] for topic in topics_list]

        ax.bar(range(len(topics_list)), values)
        ax.set_xticks(range(len(topics_list)))
        ax.set_xticklabels([t.split('/')[-1] for t in topics_list], rotation=45, ha='right')
        ax.set_ylabel(metric_label)
        ax.set_title(f'{metric_label}对比')
        ax.grid(True, alpha=0.3)

    # 隐藏多余的子图
    for idx in range(len(metrics_names), len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()
    plt.savefig(output_dir / 'metrics_comparison.png', dpi=150)
    plt.close()

    print(f"  ✓ 生成轨迹对比图: trajectory_comparison.png")
    print(f"  ✓ 生成指标对比图: metrics_comparison.png")


def main():
    parser = argparse.ArgumentParser(description='对比多个话题的数据')
    parser.add_argument('--rosbag', required=True, help='rosbag目录路径')
    parser.add_argument('--topics', required=True, nargs='+', help='要对比的话题列表')
    parser.add_argument('--output', default='data/comparison', help='输出目录')

    args = parser.parse_args()

    compare_topics(args.rosbag, args.topics, args.output)


if __name__ == '__main__':
    main()