#!/usr/bin/env python3
"""
演示J0偏移的必要性
"""

import numpy as np
import sys
import os

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
import pinocchio as pin

def demonstrate_j0_offset():
    """演示J0偏移的作用"""

    print("="*80)
    print("J0偏移配置说明")
    print("="*80)

    # 加载配置
    config = get_config()

    # 加载机器人模型
    urdf_path = os.path.join(project_root, "config", config.robot_model_urdf_file)
    model = pin.buildModelFromUrdf(urdf_path)

    print("\n1️⃣ 机器人URDF定义")
    print("-" * 80)

    # 获取右臂关节
    right_joints = [name for name in model.names if 'Right' in name and 'Joint' not in name]
    print(f"右臂关节数量: {len(right_joints)}")

    # 测试不同的J0角度
    print("\n2️⃣ J0角度对应的手臂姿态")
    print("-" * 80)

    # 创建测试配置
    q = pin.neutral(model)
    data = model.createData()

    # 找到右臂的关节索引
    right_shoulder_pitch_idx = None
    for i, name in enumerate(model.names):
        if 'Right_Shoulder_Pitch' in name:
            right_shoulder_pitch_idx = i
            break

    if right_shoulder_pitch_idx is None:
        print("⚠️ 未找到Right_Shoulder_Pitch关节")
        return

    # 测试不同角度
    test_angles = [0, -np.pi/4, -np.pi/2, -np.pi]
    angle_names = ["0° (水平向前?)", "-45° (斜向下)", "-90° (垂直向下)", "-180° (向后)"]

    for angle, name in zip(test_angles, angle_names):
        q_test = q.copy()
        q_test[right_shoulder_pitch_idx] = angle
        pin.forwardKinematics(model, data, q_test)

        # 获取末端位置
        ee_frame_id = model.getFrameId(config.robot_model_end_effector_frame)
        pin.updateFramePlacement(model, data, ee_frame_id)
        ee_pos = data.oMf[ee_frame_id].translation

        print(f"\nJ0 = {angle:.3f} rad ({np.degrees(angle):.1f}°) - {name}")
        print(f"   末端位置: [{ee_pos[0]:.3f}, {ee_pos[1]:.3f}, {ee_pos[2]:.3f}]")
        print(f"   Z坐标: {ee_pos[2]:.3f}m (相对于base)")

    print("\n3️⃣ 人体-机器人对齐")
    print("-" * 80)
    print("人体自然下垂姿态：")
    print("  - 肩部到手腕：垂直向下")
    print("  - 这应该对应机器人的某个J0角度")
    print()
    print("如果机器人J0=0°时手臂是水平的：")
    print("  - 需要J0=-90°才能让手臂垂直向下")
    print("  - 所以配置 joint_offsets[0] = -1.57 (-90°)")
    print()
    print("这样当人体手臂下垂时：")
    print("  - 几何求解器计算出J0=0°（人体坐标系）")
    print("  - 应用偏移：q_final = 0 * (-1) + (-1.57) = -1.57")
    print("  - 机器人J0被命令到-90°，手臂下垂")

    print("\n4️⃣ 真机 vs 仿真")
    print("-" * 80)
    print("这个偏移与真机/仿真无关！")
    print("  - 真机和仿真使用相同的URDF")
    print("  - URDF定义了关节的零位")
    print("  - 所以真机和仿真需要相同的偏移")
    print()
    print("偏移只与以下因素有关：")
    print("  1. URDF中J0的零位定义")
    print("  2. 人体自然姿态的定义")
    print("  3. 你希望如何对齐这两者")

    print("\n5️⃣ 当前配置")
    print("-" * 80)
    print(f"joint_offsets[0] = {config.robot_joint_offsets[0]:.3f} rad")
    print(f"                 = {np.degrees(config.robot_joint_offsets[0]):.1f}°")
    print(f"joint_directions[0] = {config.robot_joint_directions[0]}")
    print()
    print("含义：")
    print("  - 人体手臂下垂（几何求解器输出0°）")
    print("  - 应用方向系数：0 * (-1) = 0")
    print("  - 应用偏移：0 + (-1.57) = -1.57")
    print("  - 机器人J0 = -90°（手臂下垂）")

    print("\n" + "="*80)

if __name__ == "__main__":
    demonstrate_j0_offset()
