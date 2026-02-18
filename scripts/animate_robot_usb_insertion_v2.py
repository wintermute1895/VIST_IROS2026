#!/usr/bin/env python3
"""
机械臂USB插入动画演示 v2.0
更清晰地展示VIST滤波效果
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def load_simulation_data():
    """加载仿真数据"""
    data_file = '/home/ilex/Dev/VIST/peg_in_hole_vist_filtering.npz'
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"请先运行 simulate_peg_in_hole_task.py 生成数据")

    data = np.load(data_file)
    return {
        'human_traj': data['human_trajectory'],
        'filtered_traj': data['filtered_trajectory'],
        'alpha': data['alpha_values'],
        'timestamps': data['timestamps']
    }

def create_realistic_robot_arm(end_effector_pos, base_pos=np.array([0, 0, 0])):
    """
    创建更真实的6-DOF机械臂
    使用改进的逆运动学
    """
    # UR5类似的机械臂参数 (单位: 米)
    d1 = 0.089  # 基座高度
    a2 = 0.425  # 大臂长度
    a3 = 0.392  # 小臂长度
    d4 = 0.109  # 腕部偏移

    # 计算目标位置
    target = end_effector_pos - base_pos

    # 关节1: 基座
    joint0 = base_pos.copy()

    # 关节2: 肩部 (基座顶部)
    joint1 = joint0 + np.array([0, 0, d1])

    # 计算到目标的水平距离和高度
    horizontal_dist = np.sqrt(target[0]**2 + target[1]**2)
    height = target[2] - d1

    # 使用余弦定理计算肘部角度
    reach = np.sqrt(horizontal_dist**2 + height**2)
    reach = min(reach, a2 + a3 - 0.01)  # 限制在工作空间内

    cos_elbow = (a2**2 + a3**2 - reach**2) / (2 * a2 * a3)
    cos_elbow = np.clip(cos_elbow, -1, 1)
    elbow_angle = np.arccos(cos_elbow)

    # 计算肩部角度
    alpha = np.arctan2(height, horizontal_dist)
    beta = np.arctan2(a3 * np.sin(elbow_angle), a2 + a3 * np.cos(elbow_angle))
    shoulder_angle = alpha - beta

    # 计算方位角
    azimuth = np.arctan2(target[1], target[0])

    # 关节3: 肘部
    shoulder_extension = a2 * np.array([
        np.cos(azimuth) * np.cos(shoulder_angle),
        np.sin(azimuth) * np.cos(shoulder_angle),
        np.sin(shoulder_angle)
    ])
    joint2 = joint1 + shoulder_extension

    # 关节4: 腕部
    elbow_extension = a3 * np.array([
        np.cos(azimuth) * np.cos(shoulder_angle + elbow_angle - np.pi),
        np.sin(azimuth) * np.cos(shoulder_angle + elbow_angle - np.pi),
        np.sin(shoulder_angle + elbow_angle - np.pi)
    ])
    joint3 = joint2 + elbow_extension

    # 关节5: 末端执行器
    joint4 = end_effector_pos.copy()

    return np.array([joint0, joint1, joint2, joint3, joint4])

def create_usb_model(position, scale=0.04, color='connector'):
    """创建USB连接器或端口的3D模型"""
    # USB尺寸
    length = scale * 1.5
    width = scale * 0.5
    height = scale * 0.3

    # 8个顶点
    vertices = np.array([
        [-length/2, -width/2, -height/2],
        [length/2, -width/2, -height/2],
        [length/2, width/2, -height/2],
        [-length/2, width/2, -height/2],
        [-length/2, -width/2, height/2],
        [length/2, -width/2, height/2],
        [length/2, width/2, height/2],
        [-length/2, width/2, height/2],
    ]) + position

    # 6个面
    faces = [
        [vertices[j] for j in [0, 1, 2, 3]],  # 底
        [vertices[j] for j in [4, 5, 6, 7]],  # 顶
        [vertices[j] for j in [0, 1, 5, 4]],  # 前
        [vertices[j] for j in [2, 3, 7, 6]],  # 后
        [vertices[j] for j in [0, 3, 7, 4]],  # 左
        [vertices[j] for j in [1, 2, 6, 5]],  # 右
    ]

    return faces

def create_animation():
    """创建改进的机械臂USB插入动画"""
    print("正在加载仿真数据...")
    data = load_simulation_data()

    human_traj = data['human_traj']
    filtered_traj = data['filtered_traj']
    alpha_values = data['alpha']
    timestamps = data['timestamps']

    # 目标位置
    target_pos = np.array([0.5, 0.0, 0.5])

    # 计算误差
    human_errors = np.linalg.norm(human_traj - target_pos, axis=1)
    filtered_errors = np.linalg.norm(filtered_traj - target_pos, axis=1)

    # 创建图形 - 使用2x2布局
    fig = plt.figure(figsize=(18, 10))
    fig.suptitle('VIST滤波机械臂USB插入演示', fontsize=16, fontweight='bold', y=0.98)

    # 左上: 人类输入轨迹 + 机械臂
    ax1 = fig.add_subplot(221, projection='3d')
    ax1.set_title('人类输入 (抖动)', fontsize=13, color='#A23B72', fontweight='bold')
    ax1.set_xlabel('X (m)', fontsize=10)
    ax1.set_ylabel('Y (m)', fontsize=10)
    ax1.set_zlabel('Z (m)', fontsize=10)
    ax1.view_init(elev=25, azim=45)

    # 左下: VIST滤波后轨迹 + 机械臂
    ax2 = fig.add_subplot(223, projection='3d')
    ax2.set_title('VIST滤波 (平滑)', fontsize=13, color='#F18F01', fontweight='bold')
    ax2.set_xlabel('X (m)', fontsize=10)
    ax2.set_ylabel('Y (m)', fontsize=10)
    ax2.set_zlabel('Z (m)', fontsize=10)
    ax2.view_init(elev=25, azim=45)

    # 右上: 意图因子
    ax3 = fig.add_subplot(222)
    ax3.set_title('意图因子 α (控制刚度)', fontsize=12, fontweight='bold')
    ax3.set_xlabel('时间 (s)', fontsize=10)
    ax3.set_ylabel('α', fontsize=10)
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.set_ylim([0, 1.05])
    ax3.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5, label='中等刚度')

    # 右下: 误差对比
    ax4 = fig.add_subplot(224)
    ax4.set_title('位置误差对比', fontsize=12, fontweight='bold')
    ax4.set_xlabel('时间 (s)', fontsize=10)
    ax4.set_ylabel('误差 (mm)', fontsize=10)
    ax4.grid(True, alpha=0.3, linestyle='--')

    # 设置3D坐标轴范围
    for ax in [ax1, ax2]:
        ax.set_xlim([-0.1, 0.7])
        ax.set_ylim([-0.3, 0.3])
        ax.set_zlim([0, 0.7])
        ax.set_box_aspect([0.8, 0.6, 0.7])

    # 初始化绘图元素
    # 人类输入机械臂
    human_arm_line, = ax1.plot([], [], [], 'o-', linewidth=3, markersize=6,
                                color='#A23B72', label='机械臂', zorder=5)
    human_traj_line, = ax1.plot([], [], [], '-', linewidth=1.5, alpha=0.6,
                                  color='#A23B72', label='轨迹')
    human_usb = None

    # VIST滤波机械臂
    filtered_arm_line, = ax2.plot([], [], [], 'o-', linewidth=3, markersize=6,
                                   color='#F18F01', label='机械臂', zorder=5)
    filtered_traj_line, = ax2.plot([], [], [], '-', linewidth=1.5, alpha=0.6,
                                     color='#F18F01', label='轨迹')
    filtered_usb = None

    # 目标USB端口 (两个3D图都显示)
    for ax in [ax1, ax2]:
        ax.scatter(*target_pos, color='green', s=300, marker='*',
                   label='目标', zorder=10, edgecolors='darkgreen', linewidths=2)
        port_faces = create_usb_model(target_pos, scale=0.05, color='port')
        port_poly = Poly3DCollection(port_faces, alpha=0.4, facecolor='lightgreen',
                                      edgecolor='darkgreen', linewidth=2)
        ax.add_collection3d(port_poly)
        ax.legend(loc='upper right', fontsize=9)

    # 意图因子线
    alpha_line, = ax3.plot([], [], linewidth=2.5, color='#06A77D', label='α')
    alpha_fill = None
    ax3.legend(loc='upper right', fontsize=9)

    # 误差线
    human_error_line, = ax4.plot([], [], linewidth=2, color='#A23B72',
                                  label='人类输入', alpha=0.7)
    filtered_error_line, = ax4.plot([], [], linewidth=2.5, color='#F18F01',
                                     label='VIST滤波')
    ax4.legend(loc='upper right', fontsize=9)

    # 文本显示
    info_text = fig.text(0.5, 0.01, '', ha='center', fontsize=11,
                         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    def init():
        human_arm_line.set_data([], [])
        human_arm_line.set_3d_properties([])
        human_traj_line.set_data([], [])
        human_traj_line.set_3d_properties([])
        filtered_arm_line.set_data([], [])
        filtered_arm_line.set_3d_properties([])
        filtered_traj_line.set_data([], [])
        filtered_traj_line.set_3d_properties([])
        alpha_line.set_data([], [])
        human_error_line.set_data([], [])
        filtered_error_line.set_data([], [])
        return (human_arm_line, human_traj_line, filtered_arm_line, filtered_traj_line,
                alpha_line, human_error_line, filtered_error_line)

    def update(frame):
        nonlocal human_usb, filtered_usb, alpha_fill

        # 更新人类输入机械臂
        human_joints = create_realistic_robot_arm(human_traj[frame])
        human_arm_line.set_data(human_joints[:, 0], human_joints[:, 1])
        human_arm_line.set_3d_properties(human_joints[:, 2])

        # 更新人类输入轨迹
        trail_start = max(0, frame - 30)
        human_traj_line.set_data(human_traj[trail_start:frame+1, 0],
                                  human_traj[trail_start:frame+1, 1])
        human_traj_line.set_3d_properties(human_traj[trail_start:frame+1, 2])

        # 更新人类输入USB连接器
        if human_usb is not None:
            human_usb.remove()
        usb_faces = create_usb_model(human_traj[frame], scale=0.04)
        human_usb = Poly3DCollection(usb_faces, alpha=0.8, facecolor='#A23B72',
                                      edgecolor='darkred', linewidth=1.5)
        ax1.add_collection3d(human_usb)

        # 更新VIST滤波机械臂
        filtered_joints = create_realistic_robot_arm(filtered_traj[frame])
        filtered_arm_line.set_data(filtered_joints[:, 0], filtered_joints[:, 1])
        filtered_arm_line.set_3d_properties(filtered_joints[:, 2])

        # 更新VIST滤波轨迹
        filtered_traj_line.set_data(filtered_traj[trail_start:frame+1, 0],
                                     filtered_traj[trail_start:frame+1, 1])
        filtered_traj_line.set_3d_properties(filtered_traj[trail_start:frame+1, 2])

        # 更新VIST滤波USB连接器
        if filtered_usb is not None:
            filtered_usb.remove()
        usb_faces = create_usb_model(filtered_traj[frame], scale=0.04)
        filtered_usb = Poly3DCollection(usb_faces, alpha=0.8, facecolor='#F18F01',
                                         edgecolor='darkorange', linewidth=1.5)
        ax2.add_collection3d(filtered_usb)

        # 更新意图因子
        alpha_line.set_data(timestamps[:frame+1], alpha_values[:frame+1])
        ax3.set_xlim([0, timestamps[-1]])

        # 填充意图因子区域
        if alpha_fill is not None:
            alpha_fill.remove()
        alpha_fill = ax3.fill_between(timestamps[:frame+1], 0, alpha_values[:frame+1],
                                       alpha=0.3, color='#06A77D')

        # 更新误差
        human_error_line.set_data(timestamps[:frame+1], human_errors[:frame+1] * 1000)
        filtered_error_line.set_data(timestamps[:frame+1], filtered_errors[:frame+1] * 1000)
        ax4.set_xlim([0, timestamps[-1]])
        ax4.set_ylim([0, max(human_errors.max(), filtered_errors.max()) * 1100])

        # 更新信息文本
        phase = "探索" if alpha_values[frame] < 0.3 else ("对齐" if alpha_values[frame] < 0.7 else "插入")
        stiffness = "柔顺" if alpha_values[frame] < 0.3 else ("中等" if alpha_values[frame] < 0.7 else "刚性")
        info_text.set_text(
            f'时间: {timestamps[frame]:.2f}s  |  阶段: {phase}  |  '
            f'意图因子: α={alpha_values[frame]:.3f} ({stiffness})  |  '
            f'人类误差: {human_errors[frame]*1000:.1f}mm  |  '
            f'滤波误差: {filtered_errors[frame]*1000:.1f}mm'
        )

        return (human_arm_line, human_traj_line, human_usb, filtered_arm_line,
                filtered_traj_line, filtered_usb, alpha_line, alpha_fill,
                human_error_line, filtered_error_line, info_text)

    # 创建动画 (每3帧采样一次，速度适中)
    n_frames = len(timestamps)
    frame_indices = range(0, n_frames, 3)

    print(f"正在生成动画... (共 {len(frame_indices)} 帧)")
    anim = FuncAnimation(fig, update, frames=frame_indices, init_func=init,
                         blit=False, interval=100, repeat=True)  # 100ms间隔，速度适中

    # 保存动画
    output_file = '/home/ilex/Dev/VIST/robot_usb_insertion_demo.gif'
    print(f"正在保存动画到: {output_file}")
    writer = PillowWriter(fps=10)  # 10fps，更容易看清
    anim.save(output_file, writer=writer, dpi=120)

    file_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"✓ 动画已保存: {output_file}")
    print(f"  文件大小: {file_size:.2f} MB")
    print(f"  总帧数: {len(frame_indices)}")
    print(f"  帧率: 10 fps")
    print(f"\n动画特点:")
    print(f"  - 左侧对比: 人类输入(抖动) vs VIST滤波(平滑)")
    print(f"  - 右上: 意图因子α动态变化")
    print(f"  - 右下: 误差实时对比")
    print(f"  - 底部: 当前状态信息")

    return output_file

if __name__ == '__main__':
    create_animation()
