#!/usr/bin/env python3
"""
生成论文表格数据
根据采集的rosbag数据计算Table I, II, III的指标
"""

import numpy as np
from pathlib import Path
import argparse
from scipy import signal

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState

class PaperTableGenerator:
    def __init__(self, rosbag_path):
        self.rosbag_path = rosbag_path

    def load_joint_data(self, topic_name):
        """从rosbag中加载关节数据"""
        storage_options = StorageOptions(uri=str(self.rosbag_path), storage_id='sqlite3')
        converter_options = ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr'
        )

        reader = SequentialReader()
        reader.open(storage_options, converter_options)

        timestamps = []
        positions = []

        while reader.has_next():
            topic, data, timestamp = reader.read_next()
            if topic == topic_name:
                try:
                    msg = deserialize_message(data, JointState)
                    if len(msg.position) > 0:
                        timestamps.append(timestamp * 1e-9)
                        positions.append(np.array(msg.position))
                except Exception:
                    continue

        if not timestamps:
            return None, None

        return np.array(timestamps), np.array(positions)

    def calculate_normalized_jerk(self, timestamps, positions):
        """计算归一化Jerk"""
        dt = np.diff(timestamps)

        # 计算速度（角度/秒）
        velocity = np.diff(positions, axis=0) / dt[:, np.newaxis]

        # 计算加速度
        acceleration = np.diff(velocity, axis=0) / dt[1:, np.newaxis]

        # 计算Jerk
        jerk = np.diff(acceleration, axis=0) / dt[2:, np.newaxis]

        # 归一化Jerk: NJ = sqrt(T^5 / (2 * duration^3) * sum(jerk^2))
        duration = timestamps[-1] - timestamps[0]
        T = duration

        jerk_squared_sum = np.sum(jerk ** 2)
        normalized_jerk = np.sqrt(T**5 / (2 * duration**3) * jerk_squared_sum)

        return normalized_jerk

    def calculate_sparc(self, timestamps, positions):
        """计算SPARC平滑度指标"""
        # SPARC需要对速度进行傅里叶变换
        dt = np.mean(np.diff(timestamps))

        # 计算速度幅值
        velocity = np.diff(positions, axis=0) / np.diff(timestamps)[:, np.newaxis]
        velocity_magnitude = np.linalg.norm(velocity, axis=1)

        # 傅里叶变换
        N = len(velocity_magnitude)
        fft_vals = np.fft.fft(velocity_magnitude)
        power = np.abs(fft_vals[:N//2]) ** 2
        freqs = np.fft.fftfreq(N, dt)[:N//2]

        # 计算累积功率
        cumsum_power = np.cumsum(power)
        total_power = cumsum_power[-1]

        # 找到包含99.9%功率的频率
        threshold = 0.999 * total_power
        idx = np.where(cumsum_power >= threshold)[0]
        if len(idx) > 0:
            fc = freqs[idx[0]]
        else:
            fc = freqs[-1]

        # SPARC = -∫(1/fc) * log(P(f)/Pmax) df
        # 简化计算
        sparc = -np.sum(np.log(power / np.max(power) + 1e-10)) / len(power)

        return sparc

    def calculate_spatial_variance(self, positions_list):
        """计算空间方差（需要多次试验数据）"""
        if len(positions_list) < 2:
            return None

        # 将所有轨迹对齐到相同长度
        min_len = min(len(p) for p in positions_list)
        aligned = [p[:min_len] for p in positions_list]

        # 计算每个时间点的方差
        positions_array = np.array(aligned)  # (n_trials, n_timesteps, n_joints)
        variance = np.var(positions_array, axis=0)  # (n_timesteps, n_joints)

        # 返回平均方差
        return np.mean(variance)

    def calculate_radial_deviation(self, positions_list):
        """计算径向偏差（需要多次试验数据）"""
        if len(positions_list) < 2:
            return None

        # 计算平均轨迹
        min_len = min(len(p) for p in positions_list)
        aligned = [p[:min_len] for p in positions_list]
        mean_trajectory = np.mean(aligned, axis=0)

        # 计算每条轨迹到平均轨迹的距离
        deviations = []
        for traj in aligned:
            deviation = np.linalg.norm(traj - mean_trajectory, axis=1)
            deviations.append(np.mean(deviation))

        return np.mean(deviations)

    def generate_table_ii(self, raw_topic, filtered_topic):
        """生成Table II: 平滑度指标"""
        print("\n=== Table II: Smoothness Metrics ===\n")

        # 加载原始和滤波后的数据
        ts_raw, pos_raw = self.load_joint_data(raw_topic)
        ts_filt, pos_filt = self.load_joint_data(filtered_topic)

        if ts_raw is None or ts_filt is None:
            print("错误: 无法加载数据")
            return

        # 计算指标
        nj_raw = self.calculate_normalized_jerk(ts_raw, pos_raw)
        nj_filt = self.calculate_normalized_jerk(ts_filt, pos_filt)

        sparc_raw = self.calculate_sparc(ts_raw, pos_raw)
        sparc_filt = self.calculate_sparc(ts_filt, pos_filt)

        # 打印表格
        print("| Method | Normalized Jerk | SPARC |")
        print("|--------|----------------|-------|")
        print(f"| Raw Teleoperation | {nj_raw:.4f} | {sparc_raw:.4f} |")
        print(f"| VIST (Ours) | {nj_filt:.4f} | {sparc_filt:.4f} |")
        print(f"| Improvement | {(1 - nj_filt/nj_raw)*100:.1f}% | {(sparc_filt/sparc_raw - 1)*100:.1f}% |")

        return {
            'raw': {'nj': nj_raw, 'sparc': sparc_raw},
            'filtered': {'nj': nj_filt, 'sparc': sparc_filt}
        }

    def generate_table_iii(self, topic_name, n_trials=1):
        """生成Table III: 空间一致性指标"""
        print("\n=== Table III: Spatial Consistency ===\n")

        # 加载数据
        ts, pos = self.load_joint_data(topic_name)

        if ts is None:
            print("错误: 无法加载数据")
            return

        if n_trials == 1:
            print("注意: 只有单次试验数据，使用估计值")
            # 使用单次数据的统计特性估计
            variance = np.var(pos, axis=0).mean()
            deviation = np.std(pos, axis=0).mean()

            print("| Method | Spatial Variance (deg²) | Radial Deviation (deg) |")
            print("|--------|------------------------|----------------------|")
            print(f"| VIST (Ours) | {variance:.4f} (estimated) | {deviation:.4f} (estimated) |")

            return {'variance': variance, 'deviation': deviation}
        else:
            # 多次试验的情况（未实现）
            print("多次试验分析需要额外的数据采集")
            return None

    def generate_table_i(self):
        """生成Table I: 成功率（需要任务定义）"""
        print("\n=== Table I: Success Rates ===\n")
        print("注意: 成功率需要定义具体任务和评估标准")
        print("\n| Task | GELLO | ACT | VIST (Ours) |")
        print("|------|-------|-----|-------------|")
        print("| Pick & Place | TBD | TBD | TBD |")
        print("| Assembly | TBD | TBD | TBD |")
        print("| Manipulation | TBD | TBD | TBD |")
        print("\n需要: 定义任务协议并进行多次试验")

def main():
    parser = argparse.ArgumentParser(description='生成论文表格数据')
    parser.add_argument('--rosbag', type=str, required=True, help='rosbag目录路径')
    parser.add_argument('--raw-topic', type=str, default='/right_arm_joint_control',
                       help='原始关节状态topic')
    parser.add_argument('--filtered-topic', type=str, default='/filtered_right_joint_control',
                       help='滤波后关节状态topic')

    args = parser.parse_args()

    generator = PaperTableGenerator(args.rosbag)

    # 生成所有表格
    print("=" * 60)
    print("论文数据表格生成")
    print("=" * 60)

    generator.generate_table_i()
    table_ii_results = generator.generate_table_ii(args.raw_topic, args.filtered_topic)
    table_iii_results = generator.generate_table_iii(args.filtered_topic)

    print("\n" + "=" * 60)
    print("数据生成完成")
    print("=" * 60)

if __name__ == '__main__':
    main()