#!/usr/bin/env python3
"""
检查末端执行器位置工具

目的：
1. 显示所有可能的末端执行器 frame
2. 计算每个 frame 在零位时的位置
3. 帮助确定哪个是真正的末端执行器

使用方法：
    python3 scripts/check_end_effector.py
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
    print("  末端执行器位置检查工具")
    print("="*80)

    # 加载 URDF
    urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf'
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    print(f"\n✓ 已加载 URDF: {urdf_path}")
    print(f"  总关节数: {model.nq}")
    print(f"  总 frames: {model.nframes}")

    # 零位配置
    q_zero = np.zeros(model.nq)

    # 计算正运动学
    pin.forwardKinematics(model, data, q_zero)
    pin.updateFramePlacements(model, data)

    # 查找左臂相关的 frames
    print("\n" + "="*80)
    print("  左臂相关的 Frames（零位时的位置）")
    print("="*80)

    left_frames = []
    for i in range(model.nframes):
        frame_name = model.frames[i].name
        if 'Left' in frame_name and 'Wrist' in frame_name:
            left_frames.append((i, frame_name))

    if not left_frames:
        print("❌ 未找到左臂腕部相关的 frames")
        return

    print(f"\n找到 {len(left_frames)} 个左臂腕部 frames:\n")
    print(f"{'Frame ID':<10} {'Frame Name':<30} {'Position (m)':<40} {'Distance from Origin':<20}")
    print("-"*100)

    for frame_id, frame_name in left_frames:
        position = data.oMf[frame_id].translation
        distance = np.linalg.norm(position)
        print(f"{frame_id:<10} {frame_name:<30} [{position[0]:+.4f}, {position[1]:+.4f}, {position[2]:+.4f}]  {distance:.4f} m")

    # 找出距离原点最远的（通常是末端执行器）
    max_distance = 0
    ee_candidate = None
    for frame_id, frame_name in left_frames:
        position = data.oMf[frame_id].translation
        distance = np.linalg.norm(position)
        if distance > max_distance:
            max_distance = distance
            ee_candidate = (frame_id, frame_name)

    print("\n" + "="*80)
    print("  推荐的末端执行器")
    print("="*80)
    print(f"\n基于距离原点最远的原则，推荐使用:")
    print(f"  Frame ID: {ee_candidate[0]}")
    print(f"  Frame Name: {ee_candidate[1]}")
    print(f"  Distance: {max_distance:.4f} m")

    # 显示关节顺序
    print("\n" + "="*80)
    print("  左臂关节顺序")
    print("="*80)
    print("\n左臂的 7 个关节（按顺序）:")
    left_joints = [
        "Left_Shoulder_Pitch_Joint",
        "Left_Shoulder_Roll_Joint",
        "Left_Shoulder_Yaw_Joint",
        "Left_Elbow_Pitch_Joint",
        "Left_Wrist_Yaw_Joint",
        "Left_Wrist_Pitch_Joint",
        "Left_Wrist_Roll_Joint"
    ]

    for i, joint_name in enumerate(left_joints, 1):
        print(f"  {i}. {joint_name}")

    print("\n💡 提示:")
    print("  - 对于标准的 SRS 构型（Shoulder-Roll-Shoulder），末端执行器通常是:")
    print("    * Wrist_Pitch_Link（如果 Pitch 是最后一个自由度）")
    print("    * Wrist_Yaw_Link（如果 Yaw 是最后一个自由度）")
    print("  - Roll 关节通常用于工具旋转，不一定是末端执行器")
    print("\n  - 建议使用距离原点最远的 frame 作为末端执行器")


if __name__ == '__main__':
    main()