#!/usr/bin/env python3
"""
诊断仿真中的姿态偏移问题
"""

import numpy as np
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.motion_mapper import ArmMotionMapper
from src.core.geometric_arm_solver import GeometricArmSolver
import pinocchio as pin

def diagnose_simulation_offset():
    """诊断仿真偏移"""

    print("="*80)
    print("仿真姿态偏移诊断")
    print("="*80)

    # 加载配置
    config = get_config()

    # 加载机器人模型
    urdf_path = os.path.join(project_root, "config", config.robot_model_urdf_file)
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    # 初始化motion mapper
    mapper = ArmMotionMapper()

    print("\n1️⃣ 测试：人体手臂自然下垂")
    print("-"*80)

    # 模拟人体手臂下垂的关键点（在肩部坐标系中）
    # 肩部在原点，手臂垂直向下
    human_keypoints = {
        'shoulder': [0.0, 0.0, 0.0],
        'elbow': [0.0, 0.0, -0.3],      # 向下30cm（Z负方向）
        'wrist': [0.0, 0.0, -0.6],      # 向下60cm
        'index_mcp': [0.05, 0.0, -0.6], # 手指
        'pinky_mcp': [-0.05, 0.0, -0.6]
    }

    print("人体关键点（肩部坐标系）:")
    print(f"  肩部: {human_keypoints['shoulder']}")
    print(f"  肘部: {human_keypoints['elbow']}")
    print(f"  手腕: {human_keypoints['wrist']}")

    # 通过motion mapper转换
    result = mapper.human_to_robot(human_keypoints)
    if result is None:
        print("❌ Motion mapper转换失败")
        return

    target_pos, target_quat, mapper_debug = result
    target_elbow = mapper_debug['elbow_pos']

    print(f"\n转换后的目标位置（机器人基座坐标系）:")
    print(f"  肘部: [{target_elbow[0]:.3f}, {target_elbow[1]:.3f}, {target_elbow[2]:.3f}]")
    print(f"  手腕: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]")

    # 初始化几何求解器
    print("\n2️⃣ 几何求解器计算关节角度")
    print("-"*80)

    # 获取控制的关节索引
    controlled_joints = []
    for name in ['Right_Shoulder_Pitch_Joint', 'Right_Shoulder_Roll_Joint',
                 'Right_Shoulder_Yaw_Joint', 'Right_Elbow_Pitch_Joint',
                 'Right_Wrist_Yaw_Joint', 'Right_Wrist_Pitch_Joint',
                 'Right_Wrist_Roll_Joint']:
        if model.existJointName(name):
            controlled_joints.append(model.getJointId(name) - 1)

    ee_frame_id = model.getFrameId(config.robot_model_end_effector_frame)

    geo_solver = GeometricArmSolver(
        model=model,
        data=data,
        controlled_joints=controlled_joints,
        ee_frame_id=ee_frame_id,
        config=config
    )

    # 求解
    q_init = pin.neutral(model)
    q_solution = geo_solver.solve(
        target_pos=target_pos,
        target_quat=target_quat,
        q_init=q_init,
        elbow_pos=target_elbow,
        shoulder_pos=config.robot_shoulder_position
    )

    if q_solution is None:
        print("❌ 几何求解失败")
        return

    print("求解的关节角度:")
    joint_names = ['J0_Shoulder_Pitch', 'J1_Shoulder_Roll', 'J2_Shoulder_Yaw',
                   'J3_Elbow_Pitch', 'J4_Wrist_Yaw', 'J5_Wrist_Pitch', 'J6_Wrist_Roll']
    for i, (name, angle) in enumerate(zip(joint_names, q_solution[:7])):
        print(f"  {name}: {angle:.3f} rad ({np.degrees(angle):.1f}°)")

    print("\n3️⃣ 验证：将关节角度应用到URDF")
    print("-"*80)

    # 应用到模型
    q_full = pin.neutral(model)
    for i, ctrl_idx in enumerate(controlled_joints):
        if i < len(q_solution) and ctrl_idx < len(q_full):
            q_full[ctrl_idx] = q_solution[i]

    pin.forwardKinematics(model, data, q_full)
    pin.updateFramePlacement(model, data, ee_frame_id)

    actual_pos = data.oMf[ee_frame_id].translation

    print("实际末端位置:")
    print(f"  [{actual_pos[0]:.3f}, {actual_pos[1]:.3f}, {actual_pos[2]:.3f}]")
    print(f"\n目标末端位置:")
    print(f"  [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]")
    print(f"\n位置误差:")
    error = np.linalg.norm(actual_pos - target_pos)
    print(f"  {error*1000:.2f} mm")

    # 检查手臂方向
    shoulder_pos = np.array(config.robot_shoulder_position)
    arm_vector = actual_pos - shoulder_pos
    arm_direction = arm_vector / np.linalg.norm(arm_vector)

    print(f"\n手臂方向向量:")
    print(f"  [{arm_direction[0]:.3f}, {arm_direction[1]:.3f}, {arm_direction[2]:.3f}]")

    if arm_direction[2] < -0.9:
        print("  ✅ 手臂垂直向下（正确）")
    elif arm_direction[2] > 0.9:
        print("  ❌ 手臂垂直向上（错误！）")
    elif abs(arm_direction[0]) > 0.9:
        print("  ❌ 手臂水平向前/后（错误！）")
    else:
        print(f"  ⚠️ 手臂方向异常（Z分量: {arm_direction[2]:.3f}）")

    print("\n4️⃣ 关键配置检查")
    print("-"*80)
    print(f"joint_directions[0]: {config.robot_joint_directions[0]}")
    print(f"joint_offsets[0]: {config.robot_joint_offsets[0]:.3f} rad")
    print(f"shoulder_position: {config.robot_shoulder_position}")

    print("\n" + "="*80)
    print("诊断完成")
    print("="*80)

if __name__ == "__main__":
    diagnose_simulation_offset()
