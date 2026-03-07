#!/usr/bin/env python3
"""
ROS 2 Bag 轨迹对比可视化脚本

功能：
1. 从两个文件夹中读取所有 ROS 2 bag 文件
2. 提取关节角度数据
3. 使用 URDF 进行正向运动学计算
4. 在 3D 图表中对比可视化两组轨迹

依赖安装：
pip install rosbags pinocchio matplotlib numpy

作者：Claude Code
日期：2026-03-06
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore
import pinocchio as pin

# 创建 typestore 用于消息反序列化
typestore = get_typestore(Stores.ROS2_HUMBLE)

# ============================================================================
# 配置参数（请根据实际情况修改）
# ============================================================================

# URDF 文件路径
URDF_PATH = "/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description.urdf"

# 末端执行器 Link 名称（请根据 URDF 文件中的实际名称修改）
EE_LINK_NAME = "Left_Wrist_Roll_Link"  # 左臂末端法兰

# ROS 2 Topic 名称
JOINT_STATES_TOPIC = "/robot1/left_arm/joint_states"

# 数据路径
GELLO_DATA_PATH = "/media/ilex/Cyan_data/data/GELLO/01_GELLO_0305_raw_10_group_data/"
ONEEURO_DATA_PATH = "/media/ilex/UBUNTU 20_0/data/oneeuro/oneeuro_0306_data/"

# ⚠️ 强烈注意：目标孔坐标设置 ⚠️
# 请务必将其修改为机械臂基坐标系（Base Frame）下真实的孔位坐标 [X, Y, Z]！
# 如果你不确定真实的坐标位置，或者不希望在图中显示目标孔，
# 请务必将其设置为 None ！！！（例如：TARGET_HOLE = None）
# 本次代码已加入坐标轴保护逻辑，即使坐标偏差很大也不会拉崩轨迹图比例，但红星可能会飞出可视区。
TARGET_HOLE = np.array([0.42, -0.11, 0.28])  # 请替换为真实坐标或 None

# 中文字体设置（用于显示中文标题）
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================================
# 工具函数
# ============================================================================

def load_urdf_model(urdf_path):
    """
    加载 URDF 模型并返回 Pinocchio 模型和数据对象

    Args:
        urdf_path: URDF 文件路径

    Returns:
        model: Pinocchio 模型对象
        data: Pinocchio 数据对象
    """
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()
    return model, data


def get_ee_frame_id(model, ee_link_name):
    """
    获取末端执行器的 Frame ID

    Args:
        model: Pinocchio 模型对象
        ee_link_name: 末端执行器 Link 名称

    Returns:
        frame_id: Frame ID
    """
    if model.existFrame(ee_link_name):
        return model.getFrameId(ee_link_name)
    else:
        raise ValueError(f"Frame '{ee_link_name}' not found in URDF model. "
                        f"Available frames: {[model.frames[i].name for i in range(model.nframes)]}")


def compute_fk(model, data, frame_id, joint_positions):
    """
    计算正向运动学，返回末端执行器的 XYZ 坐标

    Args:
        model: Pinocchio 模型对象
        data: Pinocchio 数据对象
        frame_id: 末端执行器 Frame ID
        joint_positions: 关节角度数组

    Returns:
        xyz: 末端执行器的 [x, y, z] 坐标
    """
    # 确保关节角度数组长度正确
    if len(joint_positions) != model.nq:
        q = np.zeros(model.nq)
        q[:min(len(joint_positions), model.nq)] = joint_positions[:min(len(joint_positions), model.nq)]
    else:
        q = np.array(joint_positions)

    # 计算正向运动学
    pin.forwardKinematics(model, data, q)
    pin.updateFramePlacements(model, data)

    # 获取末端执行器位置
    ee_pose = data.oMf[frame_id]
    xyz = ee_pose.translation.copy()  # ⚠️ 必须 .copy() 深拷贝，否则所有点会指向同一内存地址

    return xyz


def find_all_bag_folders(root_path):
    """
    递归查找所有包含 .db3 文件的文件夹

    Args:
        root_path: 根目录路径

    Returns:
        bag_folders: 包含 bag 文件的文件夹路径列表
    """
    bag_folders = []
    root = Path(root_path)

    if not root.exists():
        print(f"警告：路径不存在 - {root_path}")
        return bag_folders

    # 查找所有 experiment_xx 文件夹
    for exp_folder in sorted(root.glob("experiment_*")):
        if exp_folder.is_dir():
            # 检查是否包含 .db3 文件
            db3_files = list(exp_folder.glob("*.db3"))
            if db3_files:
                bag_folders.append(exp_folder)

    return bag_folders


def extract_trajectory_from_bag(bag_path, model, data, frame_id, topic_name):
    """
    从 ROS 2 bag 文件中提取末端执行器轨迹

    Args:
        bag_path: bag 文件夹路径
        model: Pinocchio 模型对象
        data: Pinocchio 数据对象
        frame_id: 末端执行器 Frame ID
        topic_name: Joint States Topic 名称

    Returns:
        trajectory: Nx3 数组，每行为 [x, y, z] 坐标
    """
    trajectory = []

    try:
        with Reader(bag_path) as reader:
            # 查找 joint_states topic
            connections = [c for c in reader.connections if c.topic == topic_name]

            if not connections:
                print(f"警告：在 {bag_path} 中未找到 topic '{topic_name}'")
                return np.array(trajectory)

            # 读取消息
            for connection, timestamp, rawdata in reader.messages(connections=connections):
                # 反序列化消息
                msg = typestore.deserialize_cdr(rawdata, connection.msgtype)

                # 提取关节角度
                joint_positions = np.array(msg.position)

                # 计算正向运动学
                try:
                    xyz = compute_fk(model, data, frame_id, joint_positions)
                    trajectory.append(xyz)
                except Exception as e:
                    print(f"FK 计算错误: {e}")
                    continue

    except Exception as e:
        print(f"读取 bag 文件错误 {bag_path}: {e}")

    return np.array(trajectory)


def extract_all_trajectories(data_path, model, data, frame_id, topic_name):
    """
    从指定路径下的所有 bag 文件中提取轨迹

    Args:
        data_path: 数据根目录
        model: Pinocchio 模型对象
        data: Pinocchio 数据对象
        frame_id: 末端执行器 Frame ID
        topic_name: Joint States Topic 名称

    Returns:
        trajectories: 轨迹列表，每个元素为 Nx3 数组
    """
    trajectories = []
    bag_folders = find_all_bag_folders(data_path)

    print(f"在 {data_path} 中找到 {len(bag_folders)} 个 bag 文件夹")

    for bag_folder in bag_folders:
        print(f"  处理: {bag_folder.name}")
        trajectory = extract_trajectory_from_bag(bag_folder, model, data, frame_id, topic_name)

        if len(trajectory) > 0:
            trajectories.append(trajectory)
            print(f"    提取了 {len(trajectory)} 个数据点")
        else:
            print(f"    未提取到数据")

    return trajectories


def select_best_trajectory(trajectories, target_hole=None):
    """
    从多条轨迹中选择最优的一条

    ⚠️ 重要：筛选逻辑已针对实际场景优化
    - 如果提供目标孔：只考虑 XY 平面距离（忽略 Z 轴高度误差）
    - 否则：选择路径最短（最平滑）的轨迹

    Args:
        trajectories: 轨迹列表，每个元素为 Nx3 数组
        target_hole: 目标孔位置 [x, y, z]，如果为 None 则不使用

    Returns:
        best_trajectory: 最优轨迹（Nx3 数组），如果没有有效轨迹则返回 None
    """
    if len(trajectories) == 0:
        return None

    if len(trajectories) == 1:
        return trajectories[0]

    if target_hole is not None:
        # ⚠️ 只使用 XY 平面距离进行匹配（忽略 Z 轴）
        min_distance_xy = float('inf')
        best_traj = None

        for traj in trajectories:
            if len(traj) > 0:
                # 计算末端点在 XY 平面上到目标的距离
                end_point_xy = traj[-1, :2]  # 只取 X, Y
                target_xy = target_hole[:2]   # 只取 X, Y
                distance_xy = np.linalg.norm(end_point_xy - target_xy)

                if distance_xy < min_distance_xy:
                    min_distance_xy = distance_xy
                    best_traj = traj

        if best_traj is not None:
            print(f"    选择标准：XY 平面距离 = {min_distance_xy:.4f} m")

        return best_traj
    else:
        # 选择路径最短（最平滑）的轨迹
        min_length = float('inf')
        best_traj = None

        for traj in trajectories:
            if len(traj) > 1:
                # 计算路径总长度
                path_length = np.sum(np.linalg.norm(np.diff(traj, axis=0), axis=1))

                if path_length < min_length:
                    min_length = path_length
                    best_traj = traj

        if best_traj is not None:
            print(f"    选择标准：路径长度 = {min_length:.4f} m")

        return best_traj


def plot_trajectories_3d(gello_trajectories, oneeuro_trajectories, target_hole=None):
    """
    在 3D 图表中绘制两组轨迹对比

    ⚠️ 重要改进：
    1. 坐标轴范围仅由轨迹数据决定，不受目标孔坐标影响
    2. 底部投影固定在轨迹数据的最低 Z 平面
    3. 目标孔如果超出视野范围会被裁剪，不会拉伸坐标轴

    Args:
        gello_trajectories: GELLO 轨迹列表
        oneeuro_trajectories: One-Euro 轨迹列表
        target_hole: 目标孔位置 [x, y, z]，None 则不显示
    """
    # 选择最优轨迹
    print("\n选择最优轨迹...")
    gello_best = select_best_trajectory(gello_trajectories, target_hole)
    oneeuro_best = select_best_trajectory(oneeuro_trajectories, target_hole)

    if gello_best is None and oneeuro_best is None:
        print("错误：没有有效的轨迹数据")
        return

    if gello_best is not None:
        print(f"  GELLO 最优轨迹: {len(gello_best)} 个数据点")
    if oneeuro_best is not None:
        print(f"  One-Euro 最优轨迹: {len(oneeuro_best)} 个数据点")

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    # ============================================================================
    # ⚠️ 关键：先计算轨迹数据的坐标范围（不包含目标孔）
    # ============================================================================
    all_points = []
    if gello_best is not None and len(gello_best) > 0:
        all_points.append(gello_best)
    if oneeuro_best is not None and len(oneeuro_best) > 0:
        all_points.append(oneeuro_best)

    if all_points:
        all_points = np.vstack(all_points)
        x_min, x_max = all_points[:, 0].min(), all_points[:, 0].max()
        y_min, y_max = all_points[:, 1].min(), all_points[:, 1].max()
        z_min, z_max = all_points[:, 2].min(), all_points[:, 2].max()
    else:
        x_min, x_max = 0, 1
        y_min, y_max = 0, 1
        z_min, z_max = 0, 1

    # ============================================================================
    # 绘制轨迹线条
    # ============================================================================
    if gello_best is not None and len(gello_best) > 0:
        ax.plot(gello_best[:, 0], gello_best[:, 1], gello_best[:, 2],
               color='lightcoral', alpha=0.8, linewidth=2.5, label='GELLO')

    if oneeuro_best is not None and len(oneeuro_best) > 0:
        ax.plot(oneeuro_best[:, 0], oneeuro_best[:, 1], oneeuro_best[:, 2],
               color='steelblue', alpha=0.8, linewidth=2.5, label='One-Euro')

    # ============================================================================
    # 绘制底部 XY 平面投影（固定在 z_min 下方一点，避免与轨迹粘连）
    # ============================================================================
    # 投影平面稍微往下沉一点，避免和真实轨迹重叠
    z_proj_plane = z_min - (z_max - z_min) * 0.1 if z_max > z_min else z_min - 0.05

    if gello_best is not None and len(gello_best) > 0:
        ax.scatter(gello_best[:, 0], gello_best[:, 1],
                  np.full_like(gello_best[:, 2], z_proj_plane),
                  color='lightcoral', alpha=0.25, s=8, label='_nolegend_', zorder=1)

    if oneeuro_best is not None and len(oneeuro_best) > 0:
        ax.scatter(oneeuro_best[:, 0], oneeuro_best[:, 1],
                  np.full_like(oneeuro_best[:, 2], z_proj_plane),
                  color='steelblue', alpha=0.25, s=8, label='_nolegend_', zorder=1)

    # ============================================================================
    # 绘制目标孔（不影响坐标轴范围）
    # ============================================================================
    if target_hole is not None:
        # 绘制目标孔，但不让它影响坐标轴范围
        # 如果目标孔在视野外，它会被裁剪或不可见
        ax.scatter(target_hole[0], target_hole[1], target_hole[2],
                  color='red', marker='*', s=400,
                  edgecolors='black', linewidths=2.0,
                  label='Target Hole', zorder=100)

        # 在底部平面也画一个投影
        ax.scatter(target_hole[0], target_hole[1], z_min,
                  color='red', marker='*', s=200,
                  edgecolors='black', linewidths=1.5,
                  alpha=0.5, label='_nolegend_', zorder=99)

    # ============================================================================
    # 设置坐标轴范围（仅基于轨迹数据，添加适当边距）
    # ============================================================================
    margin = 0.05
    ax.set_xlim([x_min - margin, x_max + margin])
    ax.set_ylim([y_min - margin, y_max + margin])
    ax.set_zlim([z_min - margin, z_max + margin])

    # ============================================================================
    # 图表美化
    # ============================================================================
    ax.legend(loc='upper left', fontsize=12, framealpha=0.9)
    ax.set_xlabel('X (m)', fontsize=12, labelpad=10)
    ax.set_ylabel('Y (m)', fontsize=12, labelpad=10)
    ax.set_zlabel('Z (m)', fontsize=12, labelpad=10)
    ax.set_title('GELLO 与 One-Euro 轨迹对比', fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.view_init(elev=20, azim=45)

    plt.tight_layout()

    # 保存图片
    output_path = "/home/ilex/Dev/VIST/trajectory_comparison_3d.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存至: {output_path}")

    plt.show()


# ============================================================================
# 主程序
# ============================================================================

def main():
    print("=" * 80)
    print("ROS 2 Bag 轨迹对比可视化")
    print("=" * 80)

    # 1. 加载 URDF 模型
    print("\n[1/4] 加载 URDF 模型...")
    try:
        model, data = load_urdf_model(URDF_PATH)
        print(f"  模型加载成功: {model.nq} 个关节")
    except Exception as e:
        print(f"  错误：无法加载 URDF 文件 - {e}")
        return

    # 2. 获取末端执行器 Frame ID
    print(f"\n[2/4] 查找末端执行器 Frame '{EE_LINK_NAME}'...")
    try:
        frame_id = get_ee_frame_id(model, EE_LINK_NAME)
        print(f"  Frame ID: {frame_id}")
    except Exception as e:
        print(f"  错误：{e}")
        return

    # 3. 提取 GELLO 轨迹
    print(f"\n[3/4] 提取轨迹数据...")
    print(f"\n  GELLO 数据:")
    gello_trajectories = extract_all_trajectories(
        GELLO_DATA_PATH, model, data, frame_id, JOINT_STATES_TOPIC
    )
    print(f"  共提取 {len(gello_trajectories)} 条 GELLO 轨迹")

    # 4. 提取 One-Euro 轨迹
    print(f"\n  One-Euro 数据:")
    oneeuro_trajectories = extract_all_trajectories(
        ONEEURO_DATA_PATH, model, data, frame_id, JOINT_STATES_TOPIC
    )
    print(f"  共提取 {len(oneeuro_trajectories)} 条 One-Euro 轨迹")

    # 5. 绘制对比图
    print(f"\n[4/4] 绘制 3D 对比图...")
    if len(gello_trajectories) == 0 and len(oneeuro_trajectories) == 0:
        print("  错误：没有提取到任何轨迹数据")
        return

    plot_trajectories_3d(gello_trajectories, oneeuro_trajectories, TARGET_HOLE)

    print("\n" + "=" * 80)
    print("处理完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
