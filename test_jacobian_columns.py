#!/usr/bin/env python3
"""
测试雅可比矩阵列与关节的对应关系

对左臂的每个关节分别旋转±45度，观察雅可比矩阵哪一列发生变化
"""

import numpy as np
import pinocchio as pin
import sys
import os

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'ros2_ws/src'))

from core.ik_solver import PinocchioIKSolver


def print_jacobian_diff(J_base, J_perturbed, joint_idx, delta_angle):
    """打印雅可比矩阵的差异"""
    J_diff = J_perturbed - J_base

    # 计算每一列的范数
    col_norms = np.linalg.norm(J_diff, axis=0)

    print(f"\n关节 {joint_idx} 旋转 {np.rad2deg(delta_angle):+.1f}°:")
    print(f"  雅可比矩阵列范数变化: {col_norms}")
    print(f"  最大变化列: {np.argmax(col_norms)} (范数={col_norms[np.argmax(col_norms)]:.6f})")

    # 打印变化最大的列
    max_col = np.argmax(col_norms)
    if col_norms[max_col] > 1e-6:
        print(f"  第 {max_col} 列变化:")
        print(f"    位置部分 (前3行): {J_diff[:3, max_col]}")
        print(f"    姿态部分 (后3行): {J_diff[3:, max_col]}")


def main():
    print("=" * 80)
    print("雅可比矩阵列与关节对应关系测试")
    print("=" * 80)

    # 初始化IK求解器（使用左臂）
    print("\n初始化IK求解器（左臂）...")

    # 左臂关节名称
    left_arm_joints = [
        "Left_Shoulder_Pitch_Joint",
        "Left_Shoulder_Roll_Joint",
        "Left_Shoulder_Yaw_Joint",
        "Left_Elbow_Pitch_Joint",
        "Left_Wrist_Yaw_Joint",
        "Left_Wrist_Pitch_Joint",
        "Left_Wrist_Roll_Joint"
    ]

    ik_solver = PinocchioIKSolver(
        urdf_path="/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf",
        end_effector_frame="Left_Wrist_Roll_Link",
        controlled_joints=left_arm_joints
    )

    # 获取左臂末端执行器frame ID
    ee_frame_id = ik_solver.ee_frame_id
    print(f"左臂末端执行器 frame ID: {ee_frame_id}")
    print(f"受控关节索引: {ik_solver.controlled_indices}")
    print(f"受控关节数量: {len(ik_solver.controlled_indices)}")

    # 基准关节角度（全零）
    q_base = np.zeros(7)

    # 计算基准雅可比矩阵
    q_full_base = np.zeros(ik_solver.model.nq)
    q_full_base[ik_solver.controlled_indices] = q_base

    pin.forwardKinematics(ik_solver.model, ik_solver.data, q_full_base)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)

    J_full_base = pin.computeFrameJacobian(
        ik_solver.model,
        ik_solver.data,
        q_full_base,
        ee_frame_id,
        pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
    )
    J_base = J_full_base[:, ik_solver.controlled_indices]

    print(f"\n基准雅可比矩阵形状: {J_base.shape}")
    print(f"基准雅可比矩阵:\n{J_base}")

    # 测试每个关节
    delta_angles = [np.deg2rad(45), np.deg2rad(-45)]

    for joint_idx in range(7):
        print(f"\n{'=' * 80}")
        print(f"测试关节 {joint_idx} ({left_arm_joints[joint_idx]})")
        print(f"{'=' * 80}")

        for delta_angle in delta_angles:
            # 扰动关节角度
            q_perturbed = q_base.copy()
            q_perturbed[joint_idx] += delta_angle

            # 计算扰动后的雅可比矩阵
            q_full_perturbed = np.zeros(ik_solver.model.nq)
            q_full_perturbed[ik_solver.controlled_indices] = q_perturbed

            pin.forwardKinematics(ik_solver.model, ik_solver.data, q_full_perturbed)
            pin.updateFramePlacements(ik_solver.model, ik_solver.data)

            J_full_perturbed = pin.computeFrameJacobian(
                ik_solver.model,
                ik_solver.data,
                q_full_perturbed,
                ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )
            J_perturbed = J_full_perturbed[:, ik_solver.controlled_indices]

            # 打印差异
            print_jacobian_diff(J_base, J_perturbed, joint_idx, delta_angle)

    print(f"\n{'=' * 80}")
    print("测试完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
