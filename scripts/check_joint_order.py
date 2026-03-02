#!/usr/bin/env python3
"""
检查 URDF 关节顺序工具

目的：
1. 显示 URDF 中定义的关节顺序
2. 显示每个关节的父子关系
3. 确定正确的运动链

使用方法：
    python3 scripts/check_joint_order.py
"""

import numpy as np
import sys
from pathlib import Path

# 添加项目路径
ros2_ws_root = Path('/home/ilex/Dev/VIST/ros2_ws')
sys.path.insert(0, str(ros2_ws_root))

import pinocchio as pin


def main():
    print("="*80)
    print("  URDF 关节顺序检查工具")
    print("="*80)

    # 加载 URDF
    urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf'
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    print(f"\n✓ 已加载 URDF: {urdf_path}")
    print(f"  总关节数: {model.nq}")
    print(f"  总 joints: {model.njoints}")

    # 显示所有关节
    print("\n" + "="*80)
    print("  URDF 中的关节顺序（按 joint_id）")
    print("="*80)

    print(f"\n{'Joint ID':<10} {'Joint Name':<35} {'Parent':<20} {'Type':<15}")
    print("-"*80)

    for joint_id in range(model.njoints):
        joint_name = model.names[joint_id]
        parent_id = model.parents[joint_id]
        parent_name = model.names[parent_id] if parent_id > 0 else "universe"

        # 获取关节类型
        joint_type = "unknown"
        if joint_id < len(model.joints):
            jnt = model.joints[joint_id]
            joint_type = str(jnt).split()[0]

        print(f"{joint_id:<10} {joint_name:<35} {parent_name:<20} {joint_type:<15}")

    # 只显示左臂关节
    print("\n" + "="*80)
    print("  左臂关节链（从基座到末端）")
    print("="*80)

    left_joints = []
    for joint_id in range(model.njoints):
        joint_name = model.names[joint_id]
        if 'Left' in joint_name and 'Joint' in joint_name:
            left_joints.append((joint_id, joint_name))

    print(f"\n找到 {len(left_joints)} 个左臂关节:\n")
    for i, (joint_id, joint_name) in enumerate(left_joints, 1):
        parent_id = model.parents[joint_id]
        parent_name = model.names[parent_id] if parent_id > 0 else "universe"
        print(f"  {i}. {joint_name:<35} (parent: {parent_name})")

    # 零位配置
    q_zero = np.zeros(model.nq)

    # 计算正运动学
    pin.forwardKinematics(model, data, q_zero)
    pin.updateFramePlacements(model, data)

    # 显示左臂腕部 frames 的位置
    print("\n" + "="*80)
    print("  左臂腕部 Frames 位置（零位）")
    print("="*80)

    wrist_frames = []
    for i in range(model.nframes):
        frame_name = model.frames[i].name
        if 'Left' in frame_name and 'Wrist' in frame_name and 'Link' in frame_name:
            wrist_frames.append((i, frame_name))

    print(f"\n{'Frame Name':<30} {'Position (m)':<40} {'Z (m)':<10}")
    print("-"*80)

    for frame_id, frame_name in wrist_frames:
        position = data.oMf[frame_id].translation
        print(f"{frame_name:<30} [{position[0]:+.4f}, {position[1]:+.4f}, {position[2]:+.4f}]  {position[2]:.4f}")

    # 分析
    print("\n" + "="*80)
    print("  分析结果")
    print("="*80)

    print("\n根据 Z 坐标（从高到低）：")
    wrist_positions = []
    for frame_id, frame_name in wrist_frames:
        position = data.oMf[frame_id].translation
        wrist_positions.append((frame_name, position[2]))

    wrist_positions.sort(key=lambda x: x[1], reverse=True)
    for i, (name, z) in enumerate(wrist_positions, 1):
        print(f"  {i}. {name:<30} Z = {z:.4f} m")

    print("\n💡 分析:")
    print("  - Z 坐标最高的通常是最靠近肩部的关节")
    print("  - Z 坐标最低的通常是最末端的关节")
    print("  - 对于标准的 7-DOF 机械臂：")
    print("    * 如果 Roll 的 Z 最低，说明 Roll 是最后一个关节（末端执行器）")
    print("    * 如果 Pitch 的 Z 最低，说明 Pitch 是最后一个关节（末端执行器）")
    print("    * 如果 Yaw 的 Z 最低，说明 Yaw 是最后一个关节（末端执行器）")

    print("\n⚠️  重要提示:")
    print("  - URDF 中的关节顺序 ≠ 控制指令中的关节顺序")
    print("  - 需要确认控制指令中的关节顺序与 URDF 是否一致")
    print("  - 如果不一致，需要建立映射关系")


if __name__ == '__main__':
    main()