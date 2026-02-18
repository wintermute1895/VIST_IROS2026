#!/usr/bin/env python3
"""
机械臂USB插入动画演示
Robotic Arm USB Insertion Animation with VIST Filtering
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

def create_robot_arm_segments(end_effector_pos, base_pos=np.array([0, 0, 0])):
    """
    创建简化的6自由度机械臂关节位置
    使用逆运动学近似计算各关节位置
    """
    # 简化的机械臂链接长度 (单位: 米)
    L1 = 0.3  # 基座到肩部
    L2 = 0.25  # 肩部到肘部
    L3 = 0.2  # 肘部到腕部
    L4 = 0.15  # 腕部到末端执行器

    # 计算从基座到末端的向量
    target_vec = end_effector_pos - base_pos
    target_dist = np.linalg.norm(target_vec)
    target_dir = target_vec / (target_dist + 1e-6)

    # 简化的逆运动学：沿着目标方向分配关节
    # 关节1: 基座
    joint1 = base_pos.copy()

    # 关节2: 肩部 (向上抬起)
    shoulder_offset = np.array([0, 0, L1])
    joint2 = joint1 + shoulder_offset

    # 关节3: 肘部 (朝向目标方向)
    elbow_dir = target_dir * 0.7 + np.array([0, 0, 0.3])
    elbow_dir = elbow_dir / (np.linalg.norm(elbow_dir) + 1e-6)
    joint3 = joint2 + elbow_dir * L2

    # 关节4: 腕部
    wrist_vec = end_effector_pos - joint3
    wrist_dist = np.linalg.norm(wrist_vec)
    if wrist_dist > L3 + L4:
        wrist_dir = wrist_vec / (wrist_dist + 1e-6)
        joint4 = joint3 + wrist_dir * L3
    else:
        # 使用余弦定理计算腕部位置
        wrist_dir = wrist_vec / (wrist_dist + 1e-6)
        joint4 = joint3 + wrist_dir * L3

    # 关节5: 末端执行器
    joint5 = end_effector_pos.copy()

    return np.array([joint1, joint2, joint3, joint4, joint5])

def create_usb_connector(position, orientation_angle=0, scale=0.03):
    """创建USB连接器的3D模型"""
    # USB连接器尺寸 (简化为长方体)
    length, width, height = scale * 2, scale * 0.8, scale * 0.6

    # 定义USB连接器的8个顶点
    vertices = np.array([
        [-length/2, -width/2, -height/2],
        [length/2, -width/2, -height/2],
        [length/2, width/2, -height/2],
        [-length/2, width/2, -height/2],
        [-length/2, -width/2, height/2],
        [length/2, -width/2, height/2],
        [length/2, width/2, height/2],
        [-length/2, width/2, height/2],
    ])

    # 旋转
    cos_a, sin_a = np.cos(orientation_angle), np.sin(orientation_angle)
    rot_z = np.array([[cos_a, -sin_a, 0], [sin_a, cos_a, 0], [0, 0, 1]])
    vertices = vertices @ rot_z.T

    # 平移到指定位置
    vertices += position

    # 定义6个面
    faces = [
        [vertices[0], vertices[1], vertices[2], vertices[3]],  # 底面
        [vertices[4], vertices[5], vertices[6], vertices[7]],  # 顶面
        [vertices[0], vertices[1], vertices[5], vertices[4]],  # 前面
        [vertices[2], vertices[3], vertices[7], vertices[6]],  # 后面
        [vertices[0], vertices[3], vertices[7], vertices[4]],  # 左面
        [vertices[1], vertices[2], vertices[6], vertices[5]],  # 右面
    ]

    return faces

def create_usb_port(position, scale=0.035):
    """创建USB端口的3D模型 (目标位置)"""
    # USB端口尺寸 (略大于连接器)
    length, width, height = scale * 2.2, scale * 0.9, scale * 0.7

    # 定义端口的8个顶点
    vertices = np.array([
        [-length/2, -width/2, -height/2],
        [length/2, -width/2, -height/2],
        [length/2, width/2, -height/2],
        [-length/2, width/2, -height/2],
        [-length/2, -width/2, height/2],
        [length/2, -width/2, height/2],
        [length/2, width/2, height/2],
        [-length/2, width/2, height/2],
    ])

    vertices += position

    faces = [
        [vertices[0], vertices[1], vertices[2], vertices[3]],
        [vertices[4], vertices[5], vertices[6], vertices[7]],
        [vertices[0], vertices[1], vertices[5], vertices[4]],
        [vertices[2], vertices[3], vertices[7], vertices[6]],
        [vertices[0], vertices[3], vertices[7], vertices[4]],
        [vertices[1], vertices[2], vertices[6], vertices[5]],
    ]

    return faces

def create_animation():
    """创建机械臂USB插入动画"""
    print("正在加载仿真数据...")
    data = load_simulation_data()

    human_traj = data['human_traj']
    filtered_traj = data['filtered_traj']
    alpha_values = data['alpha']
    timestamps = data['timestamps']

    # 目标位置 (USB端口位置)
    target_pos = np.array([0.5, 0.0, 0.5])

    # 创建图形
    fig = plt.figure(figsize=(16, 9))

    # 3D视图 - 机械臂
    ax1 = fig.add_subplot(121, projection='3d')
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title('机械臂USB插入演示 (VIST滤波)', fontsize=14, fontweight='bold')

    # 设置视角
    ax1.view_init(elev=20, azim=45)

    # 2D视图 - 意图因子和误差
    ax2 = fig.add_subplot(222)
    ax2.set_xlabel('时间 (s)')
    ax2.set_ylabel('意图因子 α')
    ax2.set_title('意图因子变化', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1.05])

    ax3 = fig.add_subplot(224)
    ax3.set_xlabel('时间 (s)')
    ax3.set_ylabel('距离误差 (m)')
    ax3.set_title('末端执行器误差', fontsize=12)
    ax3.grid(True, alpha=0.3)
    ax3.set_yscale('log')

    # 计算误差
    errors = np.linalg.norm(filtered_traj - target_pos, axis=1)

    # 初始化绘图元素
    arm_line, = ax1.plot([], [], [], 'o-', linewidth=4, markersize=8,
                          color='#2E86AB', label='机械臂')
    usb_connector = None
    usb_port = None

    human_line, = ax1.plot([], [], [], '--', linewidth=1.5, alpha=0.4,
                            color='#A23B72', label='人类输入')
    filtered_line, = ax1.plot([], [], [], '-', linewidth=2, alpha=0.8,
                               color='#F18F01', label='VIST滤波')

    alpha_line, = ax2.plot([], [], linewidth=2, color='#06A77D')
    error_line, = ax3.plot([], [], linewidth=2, color='#D62828')

    # 添加目标点
    ax1.scatter(*target_pos, color='green', s=200, marker='*',
                label='目标位置', zorder=10)

    # 绘制USB端口
    port_faces = create_usb_port(target_pos)
    usb_port = Poly3DCollection(port_faces, alpha=0.3, facecolor='green',
                                 edgecolor='darkgreen', linewidth=1.5)
    ax1.add_collection3d(usb_port)

    # 设置坐标轴范围
    ax1.set_xlim([-0.2, 0.7])
    ax1.set_ylim([-0.4, 0.4])
    ax1.set_zlim([0, 0.8])

    ax1.legend(loc='upper left', fontsize=10)

    # 添加文本显示
    time_text = ax1.text2D(0.02, 0.95, '', transform=ax1.transAxes, fontsize=11)
    alpha_text = ax1.text2D(0.02, 0.90, '', transform=ax1.transAxes, fontsize=11)
    error_text = ax1.text2D(0.02, 0.85, '', transform=ax1.transAxes, fontsize=11)

    def init():
        arm_line.set_data([], [])
        arm_line.set_3d_properties([])
        human_line.set_data([], [])
        human_line.set_3d_properties([])
        filtered_line.set_data([], [])
        filtered_line.set_3d_properties([])
        alpha_line.set_data([], [])
        error_line.set_data([], [])
        return arm_line, human_line, filtered_line, alpha_line, error_line

    def update(frame):
        nonlocal usb_connector

        # 更新机械臂位置
        ee_pos = filtered_traj[frame]
        joints = create_robot_arm_segments(ee_pos)

        arm_line.set_data(joints[:, 0], joints[:, 1])
        arm_line.set_3d_properties(joints[:, 2])

        # 移除旧的USB连接器
        if usb_connector is not None:
            usb_connector.remove()

        # 绘制新的USB连接器
        connector_faces = create_usb_connector(ee_pos)
        usb_connector = Poly3DCollection(connector_faces, alpha=0.7,
                                          facecolor='#2E86AB',
                                          edgecolor='darkblue', linewidth=1)
        ax1.add_collection3d(usb_connector)

        # 更新轨迹
        human_line.set_data(human_traj[:frame+1, 0], human_traj[:frame+1, 1])
        human_line.set_3d_properties(human_traj[:frame+1, 2])

        filtered_line.set_data(filtered_traj[:frame+1, 0], filtered_traj[:frame+1, 1])
        filtered_line.set_3d_properties(filtered_traj[:frame+1, 2])

        # 更新意图因子图
        alpha_line.set_data(timestamps[:frame+1], alpha_values[:frame+1])
        ax2.set_xlim([0, timestamps[-1]])

        # 更新误差图
        error_line.set_data(timestamps[:frame+1], errors[:frame+1])
        ax3.set_xlim([0, timestamps[-1]])

        # 更新文本
        time_text.set_text(f'时间: {timestamps[frame]:.2f}s')
        alpha_text.set_text(f'意图因子: α={alpha_values[frame]:.3f}')
        error_text.set_text(f'误差: {errors[frame]*1000:.2f}mm')

        return arm_line, usb_connector, human_line, filtered_line, alpha_line, error_line

    # 创建动画 (每5帧采样一次以减小文件大小)
    n_frames = len(timestamps)
    frame_indices = range(0, n_frames, 5)

    print(f"正在生成动画... (共 {len(frame_indices)} 帧)")
    anim = FuncAnimation(fig, update, frames=frame_indices, init_func=init,
                         blit=False, interval=50, repeat=True)

    # 保存动画
    output_file = '/home/ilex/Dev/VIST/robot_usb_insertion_animation.gif'
    print(f"正在保存动画到: {output_file}")
    writer = PillowWriter(fps=20)
    anim.save(output_file, writer=writer, dpi=100)

    file_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"✓ 动画已保存: {output_file}")
    print(f"  文件大小: {file_size:.2f} MB")
    print(f"  总帧数: {len(frame_indices)}")
    print(f"  帧率: 20 fps")

    return output_file

if __name__ == '__main__':
    create_animation()
