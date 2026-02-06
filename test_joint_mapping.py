#!/usr/bin/env python3
"""
测试关节索引映射的正确性
"""
import numpy as np
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.config import get_config

def test_joint_mapping():
    """测试关节索引映射"""
    print("=" * 80)
    print("测试关节索引映射")
    print("=" * 80)

    # 1. 初始化 IK 求解器
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

    # 2. 初始化 VIST 滤波器
    config = get_config()
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 3. 设置测试状态：只有肘部关节有非零值
    print("\n测试1: 设置肘部关节角度为 1.0 弧度")
    print("-" * 80)

    vist_filter.state[:7] = 0.0  # 清零所有关节
    vist_filter.state[3] = 1.0   # 设置索引3（应该是肘部）

    print(f"VIST 状态向量（前7个关节）:")
    for i in range(7):
        joint_name = ik_solver.DEFAULT_RIGHT_ARM_JOINTS[i]
        angle = vist_filter.state[i]
        print(f"  索引 {i}: {joint_name:<35} = {angle:.3f} rad")

    # 4. 转换到完整模型
    q_full = vist_filter._get_full_q_from_controlled(vist_filter.state[:7])

    print(f"\n完整模型关节角度:")
    for i, name in enumerate(ik_solver.model.names):
        if 'Right' in name and 'Joint' in name:
            joint_id = ik_solver.model.getJointId(name)
            idx_q = ik_solver.model.joints[joint_id].idx_q
            angle = q_full[idx_q]
            marker = " ✅ 肘部" if "Elbow" in name else ""
            marker += " ⚠️ 非零!" if angle != 0 and "Elbow" not in name else ""
            print(f"  idx_q={idx_q}: {name:<35} = {angle:.3f} rad{marker}")

    # 5. 验证结果
    print("\n" + "=" * 80)
    elbow_idx_q = ik_solver.model.joints[ik_solver.model.getJointId('Right_Elbow_Pitch_Joint')].idx_q
    wrist_pitch_idx_q = ik_solver.model.joints[ik_solver.model.getJointId('Right_Wrist_Pitch_Joint')].idx_q

    elbow_angle = q_full[elbow_idx_q]
    wrist_pitch_angle = q_full[wrist_pitch_idx_q]

    print(f"验证结果:")
    print(f"  Right_Elbow_Pitch_Joint (idx_q={elbow_idx_q}): {elbow_angle:.3f} rad")
    print(f"  Right_Wrist_Pitch_Joint (idx_q={wrist_pitch_idx_q}): {wrist_pitch_angle:.3f} rad")

    if abs(elbow_angle - 1.0) < 1e-6 and abs(wrist_pitch_angle) < 1e-6:
        print("\n✅ 映射正确！肘部角度被正确映射到 Right_Elbow_Pitch_Joint")
    else:
        print("\n❌ 映射错误！")
        if abs(wrist_pitch_angle - 1.0) < 1e-6:
            print("   肘部角度被错误地映射到了 Right_Wrist_Pitch_Joint")

if __name__ == "__main__":
    test_joint_mapping()
