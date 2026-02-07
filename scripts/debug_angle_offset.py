#!/usr/bin/env python3
"""
调试脚本：诊断真实大臂和机器人大臂之间的固定角度差

这个脚本会：
1. 模拟一个简单的大臂姿态（向前伸）
2. 通过坐标转换得到机器人坐标系中的向量
3. 使用几何求解器计算关节角度
4. 打印详细的中间结果，帮助定位角度偏移的来源
"""

import numpy as np
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.ik_solver import PinocchioIKSolver

def main():
    print("=" * 80)
    print("🔍 调试：真实大臂和机器人大臂的固定角度差")
    print("=" * 80)

    # 1. 加载配置
    config = get_config()

    # 2. 加载机器人模型
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

    # 3. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id,
        config=config
    )

    print("\n" + "=" * 80)
    print("测试场景 1: 大臂向前平伸（Shoulder Frame）")
    print("=" * 80)

    # 定义测试姿态（Shoulder Frame）
    # Shoulder Frame: X=up, Y=right, Z=forward
    # 大臂向前平伸，小臂也向前伸直
    shoulder_shoulder = np.array([0.0, 0.0, 0.0])  # 肩部在原点
    elbow_shoulder = np.array([0.0, 0.0, 0.3])     # 肘部向前 30cm
    wrist_shoulder = np.array([0.0, 0.0, 0.55])    # 腕部向前 55cm

    print(f"\n📍 Shoulder Frame 中的关键点:")
    print(f"   肩部: {shoulder_shoulder}")
    print(f"   肘部: {elbow_shoulder}")
    print(f"   腕部: {wrist_shoulder}")

    # 坐标转换到 Robot Base Frame
    R = config.rotation_matrix
    shoulder_robot = config.robot_shoulder_position + R @ shoulder_shoulder
    elbow_robot = config.robot_shoulder_position + R @ elbow_shoulder
    wrist_robot = config.robot_shoulder_position + R @ wrist_shoulder

    print(f"\n📍 Robot Base Frame 中的关键点:")
    print(f"   肩部: {shoulder_robot}")
    print(f"   肘部: {elbow_robot}")
    print(f"   腕部: {wrist_robot}")

    # 计算向量
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    print(f"\n📐 Robot Base Frame 中的向量:")
    print(f"   肩→肘: {v_shoulder_elbow}")
    print(f"   肘→腕: {v_elbow_wrist}")

    # 使用几何求解器计算关节角度
    q_solution = geo_solver.solve(shoulder_robot, elbow_robot, wrist_robot)

    print(f"\n🎯 几何求解器计算的关节角度:")
    print(f"   弧度: {q_solution}")
    print(f"   角度: {np.degrees(q_solution)}")

    # 分析 q1 (Shoulder Pitch)
    print(f"\n🔍 详细分析 q1 (Shoulder Pitch):")
    print(f"   v_shoulder_elbow[0] (X, forward): {v_shoulder_elbow[0]:.4f}")
    print(f"   v_shoulder_elbow[2] (Z, up):      {v_shoulder_elbow[2]:.4f}")
    print(f"   arctan2(Z, X) = arctan2({v_shoulder_elbow[2]:.4f}, {v_shoulder_elbow[0]:.4f})")
    q1_raw = np.arctan2(v_shoulder_elbow[2], v_shoulder_elbow[0])
    print(f"   q1 (原始): {q1_raw:.4f} rad = {np.degrees(q1_raw):.2f}°")
    print(f"   q1 (应用方向系数后): {q_solution[0]:.4f} rad = {np.degrees(q_solution[0]):.2f}°")
    print(f"   关节方向系数: {geo_solver.joint_directions[0]}")

    print("\n" + "=" * 80)
    print("测试场景 2: 大臂向上抬起 45°（Shoulder Frame）")
    print("=" * 80)

    # 大臂向上抬起 45°
    angle_45 = np.pi / 4
    elbow_shoulder = np.array([0.3 * np.sin(angle_45), 0.0, 0.3 * np.cos(angle_45)])
    wrist_shoulder = elbow_shoulder + np.array([0.25 * np.sin(angle_45), 0.0, 0.25 * np.cos(angle_45)])

    print(f"\n📍 Shoulder Frame 中的关键点:")
    print(f"   肩部: {shoulder_shoulder}")
    print(f"   肘部: {elbow_shoulder}")
    print(f"   腕部: {wrist_shoulder}")

    # 坐标转换
    elbow_robot = config.robot_shoulder_position + R @ elbow_shoulder
    wrist_robot = config.robot_shoulder_position + R @ wrist_shoulder

    print(f"\n📍 Robot Base Frame 中的关键点:")
    print(f"   肩部: {shoulder_robot}")
    print(f"   肘部: {elbow_robot}")
    print(f"   腕部: {wrist_robot}")

    # 计算向量
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    print(f"\n📐 Robot Base Frame 中的向量:")
    print(f"   肩→肘: {v_shoulder_elbow}")
    print(f"   肘→腕: {v_elbow_wrist}")

    # 使用几何求解器计算关节角度
    q_solution = geo_solver.solve(shoulder_robot, elbow_robot, wrist_robot)

    print(f"\n🎯 几何求解器计算的关节角度:")
    print(f"   弧度: {q_solution}")
    print(f"   角度: {np.degrees(q_solution)}")

    # 分析 q1 (Shoulder Pitch)
    print(f"\n🔍 详细分析 q1 (Shoulder Pitch):")
    print(f"   v_shoulder_elbow[0] (X, forward): {v_shoulder_elbow[0]:.4f}")
    print(f"   v_shoulder_elbow[2] (Z, up):      {v_shoulder_elbow[2]:.4f}")
    print(f"   arctan2(Z, X) = arctan2({v_shoulder_elbow[2]:.4f}, {v_shoulder_elbow[0]:.4f})")
    q1_raw = np.arctan2(v_shoulder_elbow[2], v_shoulder_elbow[0])
    print(f"   q1 (原始): {q1_raw:.4f} rad = {np.degrees(q1_raw):.2f}°")
    print(f"   q1 (应用方向系数后): {q_solution[0]:.4f} rad = {np.degrees(q_solution[0]):.2f}°")
    print(f"   关节方向系数: {geo_solver.joint_directions[0]}")
    print(f"   预期角度: 45°")
    print(f"   角度差: {np.degrees(q_solution[0]) - 45:.2f}°")

    print("\n" + "=" * 80)
    print("✅ 调试完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
