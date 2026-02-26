#!/usr/bin/env python3
"""
可视化轨迹对比结果
"""

import pickle
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter


def load_data(filepath):
    """加载测试数据"""
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
    return data


def interpolate_to_common_time(data):
    """将两个轨迹插值到统一时间轴"""
    # 找到公共时间范围
    t_start = max(data['vision_timestamps'][0], data['exo_timestamps'][0])
    t_end = min(data['vision_timestamps'][-1], data['exo_timestamps'][-1])

    # 创建统一时间轴（使用较高频率）
    common_freq = 250.0  # Hz
    common_time = np.arange(t_start, t_end, 1.0 / common_freq)

    # 插值纯视觉控制数据
    vision_interp = np.zeros((len(common_time), 7))
    for joint_idx in range(7):
        interpolator = interp1d(
            data['vision_timestamps'],
            data['vision_data'][:, joint_idx],
            kind='cubic',
            fill_value='extrapolate'
        )
        vision_interp[:, joint_idx] = interpolator(common_time)

    # 插值遥操臂数据
    exo_interp = np.zeros((len(common_time), 7))
    for joint_idx in range(7):
        interpolator = interp1d(
            data['exo_timestamps'],
            data['exo_data'][:, joint_idx],
            kind='cubic',
            fill_value='extrapolate'
        )
        exo_interp[:, joint_idx] = interpolator(common_time)

    return common_time, vision_interp, exo_interp


def compute_derivatives(trajectory, timestamps):
    """计算速度、加速度、Jerk"""
    dt = np.mean(np.diff(timestamps))
    window_length = 51
    polyorder = 3

    velocity = np.zeros_like(trajectory)
    acceleration = np.zeros_like(trajectory)
    jerk = np.zeros_like(trajectory)

    for joint_idx in range(trajectory.shape[1]):
        # 速度
        velocity[:, joint_idx] = savgol_filter(
            trajectory[:, joint_idx],
            window_length=window_length,
            polyorder=polyorder,
            deriv=1,
            delta=dt
        )

        # 加速度
        acceleration[:, joint_idx] = savgol_filter(
            trajectory[:, joint_idx],
            window_length=window_length,
            polyorder=polyorder,
            deriv=2,
            delta=dt
        )

        # Jerk
        jerk[:, joint_idx] = savgol_filter(
            acceleration[:, joint_idx],
            window_length=window_length,
            polyorder=polyorder,
            deriv=1,
            delta=dt
        )

    return velocity, acceleration, jerk


def visualize_comparison(data, output_path='data/trajectory_comparison.png'):
    """可视化对比结果"""
    # 插值到统一时间轴
    print("插值到统一时间轴...")
    common_time, vision_interp, exo_interp = interpolate_to_common_time(data)

    # 计算导数
    print("计算导数...")
    vision_vel, vision_acc, vision_jerk = compute_derivatives(vision_interp, common_time)
    exo_vel, exo_acc, exo_jerk = compute_derivatives(exo_interp, common_time)

    # 计算误差
    position_error = np.abs(vision_interp - exo_interp)
    velocity_error = np.abs(vision_vel - exo_vel)

    # 创建图表
    fig, axes = plt.subplots(4, 2, figsize=(16, 12))

    # 选择关节1进行可视化
    joint_idx = 0

    # 1. 位置对比
    ax = axes[0, 0]
    ax.plot(common_time, vision_interp[:, joint_idx], label='纯视觉控制', alpha=0.7)
    ax.plot(common_time, exo_interp[:, joint_idx], label='遥操臂', alpha=0.7)
    ax.set_ylabel('位置 (rad)')
    ax.set_title(f'关节{joint_idx+1} 位置对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. 位置误差
    ax = axes[0, 1]
    ax.plot(common_time, position_error[:, joint_idx])
    ax.set_ylabel('位置误差 (rad)')
    ax.set_title(f'关节{joint_idx+1} 位置误差')
    ax.grid(True, alpha=0.3)

    # 3. 速度对比
    ax = axes[1, 0]
    ax.plot(common_time, vision_vel[:, joint_idx], label='纯视觉控制', alpha=0.7)
    ax.plot(common_time, exo_vel[:, joint_idx], label='遥操臂', alpha=0.7)
    ax.set_ylabel('速度 (rad/s)')
    ax.set_title(f'关节{joint_idx+1} 速度对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 4. 速度误差
    ax = axes[1, 1]
    ax.plot(common_time, velocity_error[:, joint_idx])
    ax.set_ylabel('速度误差 (rad/s)')
    ax.set_title(f'关节{joint_idx+1} 速度误差')
    ax.grid(True, alpha=0.3)

    # 5. 加速度对比
    ax = axes[2, 0]
    ax.plot(common_time, vision_acc[:, joint_idx], label='纯视觉控制', alpha=0.7)
    ax.plot(common_time, exo_acc[:, joint_idx], label='遥操臂', alpha=0.7)
    ax.set_ylabel('加速度 (rad/s²)')
    ax.set_title(f'关节{joint_idx+1} 加速度对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 6. Jerk对比
    ax = axes[2, 1]
    ax.plot(common_time, vision_jerk[:, joint_idx], label='纯视觉控制', alpha=0.7)
    ax.plot(common_time, exo_jerk[:, joint_idx], label='遥操臂', alpha=0.7)
    ax.set_ylabel('Jerk (rad/s³)')
    ax.set_title(f'关节{joint_idx+1} Jerk对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 7. 频谱分析 - 纯视觉控制
    ax = axes[3, 0]
    from scipy.fft import fft, fftfreq
    N = len(vision_interp[:, joint_idx])
    dt = common_time[1] - common_time[0]
    yf = fft(vision_interp[:, joint_idx])
    xf = fftfreq(N, dt)[:N//2]
    ax.plot(xf, 2.0/N * np.abs(yf[0:N//2]))
    ax.set_xlabel('频率 (Hz)')
    ax.set_ylabel('幅度')
    ax.set_title('纯视觉控制频谱')
    ax.set_xlim([0, 50])
    ax.grid(True, alpha=0.3)

    # 8. 频谱分析 - 遥操臂
    ax = axes[3, 1]
    yf = fft(exo_interp[:, joint_idx])
    ax.plot(xf, 2.0/N * np.abs(yf[0:N//2]))
    ax.set_xlabel('频率 (Hz)')
    ax.set_ylabel('幅度')
    ax.set_title('遥操臂频谱')
    ax.set_xlim([0, 50])
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"可视化结果已保存到: {output_path}")

    # 打印统计信息
    print("\n=== 统计信息 ===")
    print(f"位置RMSE: {np.sqrt(np.mean(position_error**2)):.6f} rad")
    print(f"速度RMSE: {np.sqrt(np.mean(velocity_error**2)):.6f} rad/s")
    print(f"最大位置误差: {np.max(position_error):.6f} rad")
    print(f"最大速度误差: {np.max(velocity_error):.6f} rad/s")

    # 计算平均Jerk
    vision_jerk_rms = np.sqrt(np.mean(vision_jerk**2))
    exo_jerk_rms = np.sqrt(np.mean(exo_jerk**2))
    print(f"\n纯视觉控制 RMS Jerk: {vision_jerk_rms:.4f} rad/s³")
    print(f"遥操臂 RMS Jerk: {exo_jerk_rms:.4f} rad/s³")


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 visualize_trajectory_comparison.py <data_file>")
        sys.exit(1)

    data_file = sys.argv[1]
    print(f"加载数据: {data_file}")
    data = load_data(data_file)

    visualize_comparison(data)


if __name__ == '__main__':
    main()