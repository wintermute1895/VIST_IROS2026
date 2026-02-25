#!/usr/bin/env python3
"""
完整的外骨骼数据分析
包括：单独评估、频谱分析、主成分分析、可视化
"""

import numpy as np
import json
import matplotlib.pyplot as plt
from pathlib import Path
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState
from scipy import signal, fft
from sklearn.decomposition import PCA
import warnings
warnings.filterwarnings('ignore')


def extract_joint_data(bag_path, topic_name):
    """提取关节数据"""
    storage_options = StorageOptions(uri=str(bag_path), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    timestamps = []
    positions = []

    while reader.has_next():
        topic, data, t = reader.read_next()

        if topic == topic_name:
            msg = deserialize_message(data, JointState)

            if msg.position and len(msg.position) > 0:
                timestamps.append(t / 1e9)
                positions.append(list(msg.position))

    return np.array(timestamps), np.array(positions)


def analyze_single_dataset(timestamps, positions, name):
    """单独分析一组数据"""
    print(f"\n{'='*80}")
    print(f"【{name}】数据分析")
    print(f"{'='*80}")

    # 基本统计
    dt = np.diff(timestamps)
    velocities = np.diff(positions, axis=0) / dt[:, np.newaxis]
    accelerations = np.diff(velocities, axis=0) / dt[1:, np.newaxis]
    jerks = np.diff(accelerations, axis=0) / dt[2:, np.newaxis]

    print(f"\n1. 基本信息")
    print(f"   时长: {timestamps[-1] - timestamps[0]:.2f}s")
    print(f"   采样数: {len(timestamps)}")
    print(f"   平均频率: {len(timestamps) / (timestamps[-1] - timestamps[0]):.1f} Hz")
    print(f"   时间间隔: {np.mean(dt)*1000:.2f} ± {np.std(dt)*1000:.2f} ms")

    print(f"\n2. 位置统计 (rad)")
    for i in range(min(7, positions.shape[1])):
        print(f"   关节{i}: 均值={np.mean(positions[:, i]):.4f}, "
              f"标准差={np.std(positions[:, i]):.4f}, "
              f"范围={np.ptp(positions[:, i]):.4f}")

    print(f"\n3. 速度统计 (rad/s)")
    for i in range(min(7, velocities.shape[1])):
        print(f"   关节{i}: RMS={np.sqrt(np.mean(velocities[:, i]**2)):.4f}, "
              f"最大={np.max(np.abs(velocities[:, i])):.4f}")

    print(f"\n4. 加速度统计 (rad/s²)")
    for i in range(min(7, accelerations.shape[1])):
        print(f"   关节{i}: RMS={np.sqrt(np.mean(accelerations[:, i]**2)):.4f}, "
              f"最大={np.max(np.abs(accelerations[:, i])):.4f}")

    print(f"\n5. 抖动统计 (rad/s³) - 平滑度指标")
    for i in range(min(7, jerks.shape[1])):
        print(f"   关节{i}: RMS={np.sqrt(np.mean(jerks[:, i]**2)):.4f}, "
              f"最大={np.max(np.abs(jerks[:, i])):.4f}")

    overall_jerk_rms = np.sqrt(np.mean(jerks**2))
    print(f"\n   整体抖动RMS: {overall_jerk_rms:.4f}")

    # 频谱分析
    print(f"\n6. 频谱分析")
    sampling_rate = 1.0 / np.mean(dt)

    for i in range(min(7, positions.shape[1])):
        # 对位置信号进行FFT
        n = len(positions[:, i])
        freqs = fft.fftfreq(n, d=1/sampling_rate)
        fft_vals = fft.fft(positions[:, i])
        power = np.abs(fft_vals)**2

        # 只看正频率
        positive_freqs = freqs[:n//2]
        positive_power = power[:n//2]

        # 找到主要频率成分
        peak_idx = np.argmax(positive_power[1:]) + 1  # 跳过DC分量
        dominant_freq = positive_freqs[peak_idx]

        # 计算频带能量分布
        low_freq_power = np.sum(positive_power[(positive_freqs < 1)])
        mid_freq_power = np.sum(positive_power[(positive_freqs >= 1) & (positive_freqs < 10)])
        high_freq_power = np.sum(positive_power[(positive_freqs >= 10)])
        total_power = np.sum(positive_power)

        print(f"   关节{i}:")
        print(f"     主频: {dominant_freq:.2f} Hz")
        print(f"     低频(<1Hz): {low_freq_power/total_power*100:.1f}%")
        print(f"     中频(1-10Hz): {mid_freq_power/total_power*100:.1f}%")
        print(f"     高频(>10Hz): {high_freq_power/total_power*100:.1f}%")

    # 主成分分析
    print(f"\n7. 主成分分析 (PCA)")
    pca = PCA()
    pca.fit(positions)

    print(f"   前3个主成分解释的方差比:")
    for i in range(min(3, len(pca.explained_variance_ratio_))):
        print(f"     PC{i+1}: {pca.explained_variance_ratio_[i]*100:.2f}%")

    cumulative_variance = np.cumsum(pca.explained_variance_ratio_)
    n_components_90 = np.argmax(cumulative_variance >= 0.90) + 1
    print(f"   达到90%方差需要的主成分数: {n_components_90}")

    # 返回分析结果
    return {
        'name': name,
        'duration': float(timestamps[-1] - timestamps[0]),
        'num_samples': int(len(timestamps)),
        'avg_frequency': float(len(timestamps) / (timestamps[-1] - timestamps[0])),
        'overall_jerk_rms': float(overall_jerk_rms),
        'overall_velocity_rms': float(np.sqrt(np.mean(velocities**2))),
        'overall_acceleration_rms': float(np.sqrt(np.mean(accelerations**2))),
        'pca_variance_ratio': pca.explained_variance_ratio_.tolist(),
        'n_components_90': int(n_components_90),
        'positions': positions,
        'velocities': velocities,
        'accelerations': accelerations,
        'jerks': jerks,
        'timestamps': timestamps,
        'sampling_rate': float(sampling_rate)
    }


def create_visualizations(raw_results, filtered_results, output_dir):
    """创建可视化图表"""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # 1. 时域对比图
    fig, axes = plt.subplots(3, 1, figsize=(15, 10))

    # 选择一个关节进行展示（关节3 - 肘部）
    joint_idx = 3

    # 位置
    axes[0].plot(raw_results['timestamps'][:500],
                 raw_results['positions'][:500, joint_idx],
                 label='无滤波', alpha=0.7)
    axes[0].plot(filtered_results['timestamps'][:500],
                 filtered_results['positions'][:500, joint_idx],
                 label='One-Euro滤波', alpha=0.7)
    axes[0].set_ylabel('位置 (rad)')
    axes[0].set_title(f'关节{joint_idx}时域对比（前500个样本）')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 速度
    axes[1].plot(raw_results['timestamps'][1:501],
                 raw_results['velocities'][:500, joint_idx],
                 label='无滤波', alpha=0.7)
    axes[1].plot(filtered_results['timestamps'][1:501],
                 filtered_results['velocities'][:500, joint_idx],
                 label='One-Euro滤波', alpha=0.7)
    axes[1].set_ylabel('速度 (rad/s)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # 加速度
    axes[2].plot(raw_results['timestamps'][2:502],
                 raw_results['accelerations'][:500, joint_idx],
                 label='无滤波', alpha=0.7)
    axes[2].plot(filtered_results['timestamps'][2:502],
                 filtered_results['accelerations'][:500, joint_idx],
                 label='One-Euro滤波', alpha=0.7)
    axes[2].set_ylabel('加速度 (rad/s²)')
    axes[2].set_xlabel('时间 (s)')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'time_domain_comparison.png', dpi=300)
    print(f"✅ 时域对比图已保存: {output_dir / 'time_domain_comparison.png'}")
    plt.close()

    # 2. 频谱对比图
    fig, axes = plt.subplots(2, 1, figsize=(15, 8))

    for idx, (results, label) in enumerate([(raw_results, '无滤波'),
                                              (filtered_results, 'One-Euro滤波')]):
        n = len(results['positions'][:, joint_idx])
        freqs = fft.fftfreq(n, d=1/results['sampling_rate'])
        fft_vals = fft.fft(results['positions'][:, joint_idx])
        power = np.abs(fft_vals)**2

        positive_freqs = freqs[:n//2]
        positive_power = power[:n//2]

        axes[idx].semilogy(positive_freqs, positive_power)
        axes[idx].set_ylabel('功率谱密度')
        axes[idx].set_title(f'{label} - 关节{joint_idx}频谱')
        axes[idx].grid(True, alpha=0.3)
        axes[idx].set_xlim([0, 40])  # 只显示0-40Hz

    axes[1].set_xlabel('频率 (Hz)')
    plt.tight_layout()
    plt.savefig(output_dir / 'frequency_spectrum.png', dpi=300)
    print(f"✅ 频谱对比图已保存: {output_dir / 'frequency_spectrum.png'}")
    plt.close()

    # 3. 抖动对比柱状图
    fig, ax = plt.subplots(figsize=(12, 6))

    joints = np.arange(7)
    width = 0.35

    raw_jerks = [np.sqrt(np.mean(raw_results['jerks'][:, i]**2))
                 for i in range(7)]
    filtered_jerks = [np.sqrt(np.mean(filtered_results['jerks'][:, i]**2))
                      for i in range(7)]

    ax.bar(joints - width/2, raw_jerks, width, label='无滤波', alpha=0.8)
    ax.bar(joints + width/2, filtered_jerks, width, label='One-Euro滤波', alpha=0.8)

    ax.set_ylabel('抖动RMS (rad/s³)')
    ax.set_xlabel('关节编号')
    ax.set_title('各关节抖动对比')
    ax.set_xticks(joints)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'jerk_comparison.png', dpi=300)
    print(f"✅ 抖动对比图已保存: {output_dir / 'jerk_comparison.png'}")
    plt.close()

    # 4. PCA可视化
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    for idx, (results, label) in enumerate([(raw_results, '无滤波'),
                                              (filtered_results, 'One-Euro滤波')]):
        pca = PCA()
        pca.fit(results['positions'])

        axes[idx].bar(range(1, 8), pca.explained_variance_ratio_[:7] * 100)
        axes[idx].set_xlabel('主成分')
        axes[idx].set_ylabel('解释方差比 (%)')
        axes[idx].set_title(f'{label} - PCA方差解释')
        axes[idx].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'pca_analysis.png', dpi=300)
    print(f"✅ PCA分析图已保存: {output_dir / 'pca_analysis.png'}")
    plt.close()


def main():
    # 数据路径
    raw_bag = Path("data/exo_raw_20260225_092520/exo_raw_data")
    filtered_bag = Path("data/exo_oneeuro_20260225_095136/exo_oneeuro_data")

    print("正在提取数据...")
    raw_timestamps, raw_positions = extract_joint_data(
        raw_bag, "/right_arm_joint_control"
    )
    filtered_timestamps, filtered_positions = extract_joint_data(
        filtered_bag, "/filtered_right_joint_control"
    )

    print(f"✅ 数据提取完成")

    # 单独分析每组数据
    raw_results = analyze_single_dataset(
        raw_timestamps, raw_positions, "无滤波数据"
    )

    filtered_results = analyze_single_dataset(
        filtered_timestamps, filtered_positions, "One-Euro滤波数据"
    )

    # 对比总结
    print(f"\n{'='*80}")
    print("【对比总结】")
    print(f"{'='*80}")

    print(f"\n抖动改善: {(1 - filtered_results['overall_jerk_rms']/raw_results['overall_jerk_rms'])*100:.1f}%")
    print(f"加速度改善: {(1 - filtered_results['overall_acceleration_rms']/raw_results['overall_acceleration_rms'])*100:.1f}%")
    print(f"PCA复杂度: {raw_results['n_components_90']} → {filtered_results['n_components_90']} 个主成分")

    # 保存结果
    results = {
        'raw': {k: v for k, v in raw_results.items()
                if not isinstance(v, np.ndarray)},
        'filtered': {k: v for k, v in filtered_results.items()
                     if not isinstance(v, np.ndarray)}
    }

    output_file = Path("data/comprehensive_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ 分析结果已保存: {output_file}")

    # 创建可视化
    print(f"\n正在生成可视化图表...")
    create_visualizations(raw_results, filtered_results, "data/analysis_plots")

    print(f"\n{'='*80}")
    print("分析完成！")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()