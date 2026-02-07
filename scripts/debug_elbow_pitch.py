#!/usr/bin/env python3
"""
调试脚本：诊断 Elbow_Pitch 关节的旋转问题

测试不同的肘部弯曲角度，验证 q4 的计算是否正确
"""

import numpy as np
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.ik_solver import PinocchioIKSolver

def main():
    print("=" * 80)
    print("🔍 调试：Elbow_Pitch 关节旋转问题")
    print("=" * 80)

    # 加载配置和模型
    config = get_config()
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path=urdf_path)
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id,
        config=config
    )

    R = config.rotation_matrix

    # ==========================================
    # 测试 1: 手臂完全伸直（肘部角度 = 180°）
    # ==========================================
    print("\n" + "=" * 80)
    print("测试 1: 手臂完全伸直（肘部角度应该 = 180°）")
    print("=" * 80)

    # Shoulder Frame: 手臂向前伸直
    shoulder_shoulder = np.array([0.0, 0.0, 0.0])
    elbow_shoulder = np.array([0.0, 0.0, 0.3])      # 向前30cm
    wrist_shoulder = np.array([0.0, 0.0, 0.55])     # 继续向前25cm（伸直）

    print(f"\nShoulder Frame:")
    print(f"  肩部: {shoulder_shoulder}")
    print(f"  肘部: {elbow_shoulder}")
    print(f"  腕部: {wrist_shoulder}")

    # 转换到 Robot Frame
    shoulder_robot = config.robot_shoulder_position + R @ shoulder_shoulder
    elbow_robot = config.robot_shoulder_position + R @ elbow_shoulder
    wrist_robot = config.robot_shoulder_position + R @ wrist_shoulder

    # 计算向量和夹角
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (
        np.linalg.norm(v_shoulder_elbow) * np.linalg.norm(v_elbow_wrist)
    )
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle_rad = np.arccos(cos_angle)
    angle_deg = np.degrees(angle_rad)

    print(f"\n向量分析:")
    print(f"  v_shoulder_elbow: {v_shoulder_elbow}")
    print(f"  v_elbow_wrist: {v_elbow_wrist}")
    print(f"  两向量夹角: {angle_deg:.2f}° (应该接近 0°，表示平行)")

    # 几何求解器计算
    q_solution = geo_solver.solve(shoulder_robot, elbow_robot, wrist_robot)

    print(f"\n关节角度:")
    print(f"  q4 (Elbow_Pitch): {np.degrees(q_solution[3]):.2f}°")
    print(f"  预期: 180° (手臂伸直)")
    print(f"  偏差: {np.degrees(q_solution[3]) - 180:.2f}°")

    # ==========================================
    # 测试 2: 肘部弯曲 90°
    # ==========================================
    print("\n" + "=" * 80)
    print("测试 2: 肘部弯曲 90°")
    print("=" * 80)

    # Shoulder Frame: 大臂向前，小臂向上弯曲90°
    elbow_shoulder = np.array([0.0, 0.0, 0.3])      # 向前30cm
    wrist_shoulder = np.array([0.25, 0.0, 0.3])     # 向上25cm（90度弯曲）

    print(f"\nShoulder Frame:")
    print(f"  肩部: {shoulder_shoulder}")
    print(f"  肘部: {elbow_shoulder}")
    print(f"  腕部: {wrist_shoulder}")

    # 转换到 Robot Frame
    elbow_robot = config.robot_shoulder_position + R @ elbow_shoulder
    wrist_robot = config.robot_shoulder_position + R @ wrist_shoulder

    # 计算向量和夹角
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (
        np.linalg.norm(v_shoulder_elbow) * np.linalg.norm(v_elbow_wrist)
    )
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle_rad = np.arccos(cos_angle)
    angle_deg = np.degrees(angle_rad)

    print(f"\n向量分析:")
    print(f"  v_shoulder_elbow: {v_shoulder_elbow}")
    print(f"  v_elbow_wrist: {v_elbow_wrist}")
    print(f"  两向量夹角: {angle_deg:.2f}° (应该接近 90°)")

    # 几何求解器计算
    q_solution = geo_solver.solve(shoulder_robot, elbow_robot, wrist_robot)

    print(f"\n关节角度:")
    print(f"  q4 (Elbow_Pitch): {np.degrees(q_solution[3]):.2f}°")
    print(f"  预期: 90° (肘部弯曲90度)")
    print(f"  偏差: {np.degrees(q_solution[3]) - 90:.2f}°")

    # ==========================================
    # 测试 3: 肘部完全折叠（角度接近 0°）
    # ==========================================
    print("\n" + "=" * 80)
    print("测试 3: 肘部完全折叠（角度接近 0°）")
    print("=" * 80)

    # Shoulder Frame: 大臂向前，小臂向后折叠
    elbow_shoulder = np.array([0.0, 0.0, 0.3])      # 向前30cm
    wrist_shoulder = np.array([0.0, 0.0, 0.05])     # 向后折叠（接近肩部）

    print(f"\nShoulder Frame:")
    print(f"  肩部: {shoulder_shoulder}")
    print(f"  肘部: {elbow_shoulder}")
    print(f"  腕部: {wrist_shoulder}")

    # 转换到 Robot Frame
    elbow_robot = config.robot_shoulder_position + R @ elbow_shoulder
    wrist_robot = config.robot_shoulder_position + R @ wrist_shoulder

    # 计算向量和夹角
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (
        np.linalg.norm(v_shoulder_elbow) * np.linalg.norm(v_elbow_wrist)
    )
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle_rad = np.arccos(cos_angle)
    angle_deg = np.degrees(angle_rad)

    print(f"\n向量分析:")
    print(f"  v_shoulder_elbow: {v_shoulder_elbow}")
    print(f"  v_elbow_wrist: {v_elbow_wrist}")
    print(f"  两向量夹角: {angle_deg:.2f}° (应该接近 180°，表示反向)")

    # 几何求解器计算
    q_solution = geo_solver.solve(shoulder_robot, elbow_robot, wrist_robot)

    print(f"\n关节角度:")
    print(f"  q4 (Elbow_Pitch): {np.degrees(q_solution[3]):.2f}°")
    print(f"  预期: 接近 0° (肘部完全折叠)")
    print(f"  偏差: {np.degrees(q_solution[3]):.2f}°")

    # ==========================================
    # 分析 q4 的计算公式
    # ==========================================
    print("\n" + "=" * 80)
    print("分析 q4 的计算公式")
    print("=" * 80)

    print(f"\n当前公式: q4 = π - arccos(cos_angle)")
    print(f"  - 两向量平行（angle=0°）  → q4 = 180°")
    print(f"  - 两向量垂直（angle=90°） → q4 = 90°")
    print(f"  - 两向量反向（angle=180°）→ q4 = 0°")

    print(f"\n这个定义假设:")
    print(f"  - q4 = 180° 表示手臂完全伸直")
    print(f"  - q4 = 0° 表示手臂完全折叠")

    print(f"\n如果机器人URDF的定义是:")
    print(f"  - q4 = 0° 表示手臂完全伸直")
    print(f"  - q4 = 180° 表示手臂完全折叠")
    print(f"  那么需要修改公式为: q4 = arccos(cos_angle)")

    print("\n" + "=" * 80)
    print("✅ 调试完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
