#!/usr/bin/env python3
"""
完整的性能指标分析脚本
包含物理极限滤波、所有指标测量、配置化可视化

功能：
1. 物理极限滤波器：剔除不符合物理规律的离群点
2. 测量所有指标：控制指令、原始反馈、清洗后反馈
3. 配置文件控制可视化：决定显示哪些数据
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
import yaml
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState

# 尝试导入FollowJoint消息类型
try:
    from lbot_arm_interfaces.msg import FollowJoint
    HAS_FOLLOW_JOINT = True
except ImportError:
    HAS_FOLLOW_JOINT = False
    print("警告：无法导入FollowJoint消息类型")


def compute_sparc(velocity, dt):
    """
    计算SPARC (Spectral Arc Length)指标

    SPARC是基于速度频谱的平滑度指标，越大越平滑
    参考: Balasubramanian et al. (2015) "On the analysis of movement smoothness"

    Args:
        velocity: 速度数组 (N, num_joints)
        dt: 采样时间间隔

    Returns:
        sparc: SPARC值（越大越平滑）
    """
    # 计算所有关节的速度幅值
    velocity_magnitude = np.linalg.norm(velocity, axis=1)

    # 计算功率谱密度
    from scipy.fft import rfft, rfftfreq
    N = len(velocity_magnitude)

    # FFT
    fft_vals = rfft(velocity_magnitude)
    freqs = rfftfreq(N, dt)

    # 功率谱
    power = np.abs(fft_vals) ** 2

    # 归一化功率谱
    power_norm = power / np.sum(power)

    # 累积功率谱
    cumsum_power = np.cumsum(power_norm)

    # 找到包含99.9%能量的频率
    idx_99 = np.where(cumsum_power >= 0.999)[0]
    if len(idx_99) == 0:
        idx_99 = len(freqs) - 1
    else:
        idx_99 = idx_99[0]

    # 计算频谱弧长
    freqs_truncated = freqs[:idx_99+1]
    power_truncated = power_norm[:idx_99+1]

    # 归一化到[0, 1]
    if len(freqs_truncated) > 1:
        freq_norm = freqs_truncated / freqs_truncated[-1]
        power_cumsum = np.cumsum(power_truncated)
        power_cumsum_norm = power_cumsum / power_cumsum[-1]

        # 计算弧长
        arc_length = 0
        for i in range(1, len(freq_norm)):
            dx = freq_norm[i] - freq_norm[i-1]
            dy = power_cumsum_norm[i] - power_cumsum_norm[i-1]
            arc_length += np.sqrt(dx**2 + dy**2)

        # SPARC = -arc_length (负号使得越大越平滑)
        sparc = -arc_length
    else:
        sparc = 0.0

    return sparc


def load_config(config_path):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def extract_trajectory(rosbag_path, topic):
    """从rosbag中提取指定话题的轨迹，自动检测消息类型"""
    storage_options = StorageOptions(uri=str(rosbag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    trajectories = []
    timestamps = []

    # 检测消息类型
    is_follow_joint = 'joint_follow' in topic

    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name == topic:
            try:
                if is_follow_joint and HAS_FOLLOW_JOINT:
                    # 使用FollowJoint消息类型
                    msg = deserialize_message(data, FollowJoint)
                    if len(msg.joints) > 0:
                        trajectories.append(np.array(msg.joints))
                        timestamps.append(timestamp * 1e-9)
                else:
                    # 使用JointState消息类型
                    msg = deserialize_message(data, JointState)
                    if len(msg.position) > 0:
                        trajectories.append(np.array(msg.position))
                        timestamps.append(timestamp * 1e-9)
            except Exception as e:
                # 静默跳过反序列化错误
                continue

    if not trajectories:
        return None, None

    trajectory = np.array(trajectories)

    # 单位转换：遥操臂原始数据是角度，需要转换为弧度
    if 'joint_control' in topic and 'robot' not in topic:
        trajectory = np.deg2rad(trajectory)
        print(f"  注意：{topic} 数据从角度转换为弧度")

    return trajectory, np.array(timestamps)


def apply_physical_filter(trajectory, timestamps, config):
    """
    应用物理极限滤波器，剔除不符合物理规律的离群点

    原理：
    1. 计算相邻点的速度
    2. 如果速度超过物理极限，判定为传感器故障
    3. 用插值替换离群点

    这不是造假，这是Outlier Rejection（离群点剔除）
    """
    limits = config['physical_limits']
    max_vel = limits['max_velocity'] * limits['velocity_threshold_multiplier']

    cleaned_trajectory = trajectory.copy()
    outlier_mask = np.zeros(len(trajectory), dtype=bool)

    num_joints = trajectory.shape[1]

    for joint_idx in range(num_joints):
        joint_pos = trajectory[:, joint_idx]

        # 计算速度
        dt = np.diff(timestamps)
        velocity = np.diff(joint_pos) / dt

        # 检测离群点（速度超过物理极限）
        outliers = np.abs(velocity) > max_vel

        # 将离群点标记扩展到位置数组（前后两个点都标记）
        outlier_indices = np.where(outliers)[0]
        for idx in outlier_indices:
            outlier_mask[idx] = True
            outlier_mask[idx + 1] = True

    # 统计离群点
    num_outliers = np.sum(outlier_mask)
    outlier_ratio = num_outliers / len(trajectory) * 100

    if num_outliers > 0:
        # 使用插值替换离群点
        valid_indices = np.where(~outlier_mask)[0]

        if len(valid_indices) < 10:
            print(f"  ⚠️  警告：有效点太少（{len(valid_indices)}），无法进行插值")
            return trajectory, outlier_mask

        for joint_idx in range(num_joints):
            # 使用有效点进行插值
            interpolator = interp1d(
                timestamps[valid_indices],
                trajectory[valid_indices, joint_idx],
                kind=limits['interpolation_method'],
                fill_value='extrapolate'
            )
            # 替换离群点
            cleaned_trajectory[outlier_mask, joint_idx] = interpolator(
                timestamps[outlier_mask]
            )

    print(f"  ✓ 检测到 {num_outliers} 个离群点 ({outlier_ratio:.2f}%)")

    return cleaned_trajectory, outlier_mask


def compute_metrics_robust(trajectory, timestamps, config):
    """
    计算鲁棒的性能指标
    使用均匀重采样 + Savitzky-Golay滤波
    """
    if trajectory is None or len(trajectory) < 20:
        return None

    # 计算原始频率
    total_duration = timestamps[-1] - timestamps[0]
    original_freq = (len(trajectory) - 1) / total_duration if total_duration > 0 else 0

    # 均匀重采样
    target_freq = min(original_freq, 250.0)
    num_samples = int(total_duration * target_freq)

    if num_samples < 20:
        return None

    uniform_time = np.linspace(timestamps[0], timestamps[-1], num_samples)
    uniform_dt = uniform_time[1] - uniform_time[0]

    # 对每个关节进行插值重采样
    uniform_trajectory = np.zeros((num_samples, trajectory.shape[1]))
    for joint_idx in range(trajectory.shape[1]):
        interpolator = interp1d(
            timestamps,
            trajectory[:, joint_idx],
            kind='cubic',
            fill_value='extrapolate'
        )
        uniform_trajectory[:, joint_idx] = interpolator(uniform_time)

    # 使用Savitzky-Golay滤波器计算导数
    window_length = int(target_freq * 0.05)  # 50ms窗口
    if window_length < 5:
        window_length = 5
    if window_length % 2 == 0:
        window_length += 1
    if window_length > len(uniform_trajectory) // 3:
        window_length = (len(uniform_trajectory) // 3) | 1

    polyorder = min(3, window_length - 1)

    try:
        velocity = np.zeros_like(uniform_trajectory)
        acceleration = np.zeros_like(uniform_trajectory)
        jerk = np.zeros_like(uniform_trajectory)

        for joint_idx in range(trajectory.shape[1]):
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

    # 计算统计指标
    velocity_abs = np.abs(velocity)
    acceleration_abs = np.abs(acceleration)
    jerk_abs = np.abs(jerk)

    # 计算Normalized Jerk (Table II指标)
    # 公式: NJ = sqrt(T^5 / (2 * duration^3) * sum(jerk^2))
    T = len(uniform_trajectory)
    normalized_jerk = np.sqrt(
        (T ** 5) / (2 * total_duration ** 3) * np.sum(jerk ** 2)
    )

    # 计算SPARC (Spectral Arc Length) - Table II指标
    # 基于速度的频谱分析
    sparc_value = compute_sparc(velocity, uniform_dt)

    return {
        'frequency': original_freq,
        'resampled_frequency': target_freq,
        'avg_velocity': np.median(velocity_abs),
        'max_velocity': np.percentile(velocity_abs, 99),
        'rms_velocity': np.sqrt(np.mean(velocity_abs ** 2)),
        'avg_acceleration': np.median(acceleration_abs),
        'max_acceleration': np.percentile(acceleration_abs, 99),
        'rms_acceleration': np.sqrt(np.mean(acceleration_abs ** 2)),
        'avg_jerk': np.median(jerk_abs),
        'max_jerk': np.percentile(jerk_abs, 99),
        'rms_jerk': np.sqrt(np.mean(jerk_abs ** 2)),
        # Table II指标
        'normalized_jerk': normalized_jerk,
        'sparc': sparc_value,
        # 基础信息
        'num_samples': len(trajectory),
        'resampled_samples': num_samples,
        'duration': total_duration,
        'sg_window_ms': window_length * uniform_dt * 1000,
        # 保存导数数据用于可视化
        'uniform_time': uniform_time,
        'uniform_trajectory': uniform_trajectory,
        'velocity': velocity,
        'acceleration': acceleration,
        'jerk': jerk
    }


def analyze_all_data(rosbag_path, config, output_dir):
    """分析所有数据源"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"完整性能指标分析")
    print(f"{'='*60}\n")

    all_results = {}

    # 1. 提取控制指令数据
    if config['data_sources']['command']['enabled']:
        print("提取控制指令数据...")
        for topic in config['data_sources']['command']['topics']:
            trajectory, timestamps = extract_trajectory(rosbag_path, topic)
            if trajectory is not None:
                print(f"  ✓ {topic}: {len(trajectory)} 个样本")
                metrics = compute_metrics_robust(trajectory, timestamps, config)
                if metrics:
                    all_results['command'] = {
                        'topic': topic,
                        'trajectory': trajectory,
                        'timestamps': timestamps,
                        'metrics': metrics,
                        'label': config['data_sources']['command']['label'],
                        'color': config['data_sources']['command']['color']
                    }
                    break  # 找到第一个有效话题就停止
            else:
                print(f"  ⚠️  {topic}: 无数据")

    # 2. 提取真机反馈数据（原始）
    if config['data_sources']['feedback_raw']['enabled']:
        print("\n提取真机反馈数据（原始）...")
        for topic in config['data_sources']['feedback_raw']['topics']:
            trajectory, timestamps = extract_trajectory(rosbag_path, topic)
            if trajectory is not None:
                print(f"  ✓ {topic}: {len(trajectory)} 个样本")

                # 计算原始指标
                metrics_raw = compute_metrics_robust(trajectory, timestamps, config)
                if metrics_raw:
                    all_results['feedback_raw'] = {
                        'topic': topic,
                        'trajectory': trajectory,
                        'timestamps': timestamps,
                        'metrics': metrics_raw,
                        'label': config['data_sources']['feedback_raw']['label'],
                        'color': config['data_sources']['feedback_raw']['color']
                    }

                # 3. 应用物理极限滤波（如果启用）
                if config['data_sources']['feedback_cleaned']['enabled']:
                    print("\n应用物理极限滤波...")
                    # 注意：这里暂时不实际应用滤波，只是占位
                    # 用户说先看纯净数据
                    # cleaned_trajectory, outlier_mask = apply_physical_filter(
                    #     trajectory, timestamps, config
                    # )
                    # 暂时直接使用原始数据
                    cleaned_trajectory = trajectory
                    outlier_mask = np.zeros(len(trajectory), dtype=bool)
                    print(f"  注意：物理极限滤波已禁用，使用原始数据")

                    metrics_cleaned = compute_metrics_robust(
                        cleaned_trajectory, timestamps, config
                    )
                    if metrics_cleaned:
                        all_results['feedback_cleaned'] = {
                            'topic': topic + ' (cleaned)',
                            'trajectory': cleaned_trajectory,
                            'timestamps': timestamps,
                            'metrics': metrics_cleaned,
                            'outlier_mask': outlier_mask,
                            'label': config['data_sources']['feedback_cleaned']['label'],
                            'color': config['data_sources']['feedback_cleaned']['color']
                        }

    # 4. 提取遥操臂输出数据
    if config['data_sources']['exo_output']['enabled']:
        print("\n提取遥操臂输出数据...")
        for topic in config['data_sources']['exo_output']['topics']:
            trajectory, timestamps = extract_trajectory(rosbag_path, topic)
            if trajectory is not None:
                print(f"  ✓ {topic}: {len(trajectory)} 个样本")
                metrics = compute_metrics_robust(trajectory, timestamps, config)
                if metrics:
                    all_results['exo_output'] = {
                        'topic': topic,
                        'trajectory': trajectory,
                        'timestamps': timestamps,
                        'metrics': metrics,
                        'label': config['data_sources']['exo_output']['label'],
                        'color': config['data_sources']['exo_output']['color']
                    }

    if not all_results:
        print("\n❌ 没有可用的数据")
        return

    # 打印指标对比
    print(f"\n{'='*60}")
    print(f"指标对比")
    print(f"{'='*60}\n")

    comparison = {}
    for source_name, data in all_results.items():
        metrics = data['metrics']
        print(f"\n{data['label']} ({data['topic']})")
        print(f"  样本数: {metrics['num_samples']}")
        print(f"  时长: {metrics['duration']:.2f}秒")
        print(f"  频率: {metrics['frequency']:.2f} Hz")
        print(f"  中位速度: {metrics['avg_velocity']:.4f} rad/s ({metrics['avg_velocity']*57.3:.2f}°/s)")
        print(f"  99%速度: {metrics['max_velocity']:.4f} rad/s ({metrics['max_velocity']*57.3:.2f}°/s)")
        print(f"  中位加速度: {metrics['avg_acceleration']:.4f} rad/s²")
        print(f"  99%加速度: {metrics['max_acceleration']:.4f} rad/s²")
        print(f"  中位Jerk: {metrics['avg_jerk']:.4f} rad/s³")
        print(f"  99%Jerk: {metrics['max_jerk']:.4f} rad/s³")
        print(f"  --- Table II 指标 ---")
        print(f"  Normalized Jerk: {metrics['normalized_jerk']:.2f}")
        print(f"  SPARC: {metrics['sparc']:.4f}")

        comparison[source_name] = {
            'label': data['label'],
            'topic': data['topic'],
            'metrics': {
                'frequency': metrics['frequency'],
                'avg_velocity': metrics['avg_velocity'],
                'max_velocity': metrics['max_velocity'],
                'rms_velocity': metrics['rms_velocity'],
                'avg_acceleration': metrics['avg_acceleration'],
                'max_acceleration': metrics['max_acceleration'],
                'rms_acceleration': metrics['rms_acceleration'],
                'avg_jerk': metrics['avg_jerk'],
                'max_jerk': metrics['max_jerk'],
                'rms_jerk': metrics['rms_jerk'],
                'normalized_jerk': metrics['normalized_jerk'],
                'sparc': metrics['sparc'],
                'num_samples': metrics['num_samples'],
                'duration': metrics['duration']
            }
        }

    # 保存结果
    if config['output']['save_json']:
        with open(output_dir / 'all_metrics.json', 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 指标保存到: {output_dir / 'all_metrics.json'}")

    # 生成可视化
    if config['output']['save_plots']:
        generate_visualizations(all_results, config, output_dir)
        print(f"\n✓ 可视化保存到: {output_dir}")


def generate_visualizations(all_results, config, output_dir):
    """生成可视化图表"""
    viz_config = config['visualization']

    # 1. 轨迹对比图
    if viz_config['trajectory_comparison']['enabled']:
        generate_trajectory_comparison(all_results, viz_config, config, output_dir)

    # 2. 指标对比柱状图
    if viz_config['metrics_bar_chart']['enabled']:
        generate_metrics_bar_chart(all_results, viz_config, config, output_dir)


def generate_trajectory_comparison(all_results, viz_config, config, output_dir):
    """生成轨迹对比图"""
    traj_config = viz_config['trajectory_comparison']

    fig, axes = plt.subplots(4, 1, figsize=(15, 12))

    # 选择要显示的数据源
    sources_to_plot = []
    if traj_config['show_command'] and 'command' in all_results:
        sources_to_plot.append(('command', all_results['command']))
    if traj_config['show_feedback_raw'] and 'feedback_raw' in all_results:
        sources_to_plot.append(('feedback_raw', all_results['feedback_raw']))
    if traj_config['show_feedback_cleaned'] and 'feedback_cleaned' in all_results:
        sources_to_plot.append(('feedback_cleaned', all_results['feedback_cleaned']))
    if traj_config['show_exo_output'] and 'exo_output' in all_results:
        sources_to_plot.append(('exo_output', all_results['exo_output']))

    # 绘制位置
    ax = axes[0]
    for source_name, data in sources_to_plot:
        t = data['timestamps'] - data['timestamps'][0]
        ax.plot(t, data['trajectory'][:, 0],
                label=data['label'],
                color=data['color'],
                alpha=0.7,
                linewidth=1.5)
    ax.set_ylabel('位置 (rad)')
    ax.set_title('关节1轨迹对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 绘制速度
    ax = axes[1]
    for source_name, data in sources_to_plot:
        if viz_config['velocity_comparison'][f'show_{source_name}']:
            metrics = data['metrics']
            t = metrics['uniform_time'] - metrics['uniform_time'][0]
            ax.plot(t, metrics['velocity'][:, 0],
                    label=data['label'],
                    color=data['color'],
                    alpha=0.7,
                    linewidth=1.5)
    ax.set_ylabel('速度 (rad/s)')
    ax.set_title('关节1速度对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 绘制加速度
    ax = axes[2]
    for source_name, data in sources_to_plot:
        if viz_config['acceleration_comparison'][f'show_{source_name}']:
            metrics = data['metrics']
            t = metrics['uniform_time'] - metrics['uniform_time'][0]
            ax.plot(t, metrics['acceleration'][:, 0],
                    label=data['label'],
                    color=data['color'],
                    alpha=0.7,
                    linewidth=1.5)
    ax.set_ylabel('加速度 (rad/s²)')
    ax.set_title('关节1加速度对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 绘制Jerk
    ax = axes[3]
    for source_name, data in sources_to_plot:
        if viz_config['jerk_comparison'][f'show_{source_name}']:
            metrics = data['metrics']
            t = metrics['uniform_time'] - metrics['uniform_time'][0]
            ax.plot(t, metrics['jerk'][:, 0],
                    label=data['label'],
                    color=data['color'],
                    alpha=0.7,
                    linewidth=1.5)
    ax.set_ylabel('Jerk (rad/s³)')
    ax.set_title('关节1 Jerk对比')
    ax.set_xlabel('时间 (s)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'trajectory_comparison.png',
                dpi=config['output']['dpi'])
    plt.close()
    print(f"  ✓ 生成轨迹对比图")


def generate_metrics_bar_chart(all_results, viz_config, config, output_dir):
    """生成指标对比柱状图"""
    metrics_to_plot = viz_config['metrics_bar_chart']['metrics']

    num_metrics = len(metrics_to_plot)
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    metric_labels = {
        'avg_velocity': '中位速度 (rad/s)',
        'max_velocity': '99%速度 (rad/s)',
        'avg_acceleration': '中位加速度 (rad/s²)',
        'max_acceleration': '99%加速度 (rad/s²)',
        'avg_jerk': '中位Jerk (rad/s³)',
        'max_jerk': '99%Jerk (rad/s³)'
    }

    for idx, metric_name in enumerate(metrics_to_plot):
        ax = axes[idx]

        labels = []
        values = []
        colors = []

        for source_name, data in all_results.items():
            labels.append(data['label'])
            values.append(data['metrics'][metric_name])
            colors.append(data['color'])

        x = np.arange(len(labels))
        ax.bar(x, values, color=colors, alpha=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15, ha='right')
        ax.set_ylabel(metric_labels.get(metric_name, metric_name))
        ax.set_title(f'{metric_labels.get(metric_name, metric_name)}对比')
        ax.grid(True, alpha=0.3, axis='y')

    # 隐藏多余的子图
    for idx in range(num_metrics, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()
    plt.savefig(output_dir / 'metrics_comparison.png',
                dpi=config['output']['dpi'])
    plt.close()
    print(f"  ✓ 生成指标对比图")


def main():
    parser = argparse.ArgumentParser(description='完整性能指标分析')
    parser.add_argument('--rosbag', required=True, help='rosbag目录路径')
    parser.add_argument('--config', default='config/analysis_config.yaml',
                        help='配置文件路径')
    parser.add_argument('--output', default='data/analysis', help='输出目录')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 分析数据
    analyze_all_data(args.rosbag, config, args.output)


if __name__ == '__main__':
    main()