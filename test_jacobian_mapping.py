#!/usr/bin/env python3
"""
测试雅可比伪逆映射的稳定性

验证：
1. 正运动学：关节空间 → 笛卡尔空间
2. 雅可比计算：J = ∂x/∂q
3. 伪逆映射：q̇ = J† · ẋ
4. 数值稳定性：不同姿态下的条件数
"""

import numpy as np
import pinocchio as pin
import sys
from pathlib import Path

# 添加路径
ros2_ws_root = Path(__file__).parent / "ros2_ws"
sys.path.insert(0, str(ros2_ws_root))

from src.core.ik_solver import PinocchioIKSolver


class JacobianTester:
    """雅可比映射测试器"""

    def __init__(self, ik_solver):
        self.ik_solver = ik_solver
        self.model = ik_solver.model
        self.data = ik_solver.data
        self.ee_frame_id = ik_solver.ee_frame_id
        self.controlled_indices = ik_solver.controlled_indices

    def compute_jacobian(self, q_joints):
        """
        计算雅可比矩阵

        Args:
            q_joints: 7个受控关节的角度

        Returns:
            J: 6x7 雅可比矩阵（位置+姿态）
            J_pos: 3x7 位置雅可比矩阵
        """
        # 扩展到完整配置
        q_full = pin.neutral(self.model).copy()
        for i, ctrl_idx in enumerate(self.controlled_indices):
            q_full[ctrl_idx] = q_joints[i]

        # 更新正运动学
        pin.forwardKinematics(self.model, self.data, q_full)
        pin.updateFramePlacements(self.model, self.data)

        # 计算雅可比矩阵
        J_full = pin.computeFrameJacobian(
            self.model, self.data, q_full, self.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 提取受控关节列
        J = J_full[:, self.controlled_indices]  # 6x7
        J_pos = J[:3, :]  # 3x7 (只有位置)

        return J, J_pos

    def compute_damped_pseudoinverse(self, J, damping=1e-4):
        """
        计算阻尼最小二乘伪逆

        Args:
            J: 雅可比矩阵 (m x n)
            damping: 阻尼系数

        Returns:
            J_pinv: 伪逆矩阵 (n x m)
            condition_number: 条件数（衡量数值稳定性）
        """
        m, n = J.shape
        JJT = J @ J.T  # m x m
        damping_matrix = damping**2 * np.eye(m)

        # 计算条件数（越大越不稳定）
        try:
            condition_number = np.linalg.cond(JJT)
        except:
            condition_number = np.inf

        # 阻尼伪逆
        J_pinv = J.T @ np.linalg.inv(JJT + damping_matrix)

        return J_pinv, condition_number

    def test_forward_mapping(self, q_joints):
        """
        测试正向映射：关节速度 → 笛卡尔速度

        Args:
            q_joints: 关节角度 (7,)

        Returns:
            ee_pos: 末端位置 (3,)
            J_pos: 位置雅可比 (3x7)
        """
        # 扩展到完整配置
        q_full = pin.neutral(self.model).copy()
        for i, ctrl_idx in enumerate(self.controlled_indices):
            q_full[ctrl_idx] = q_joints[i]

        # 正运动学
        pin.forwardKinematics(self.model, self.data, q_full)
        pin.updateFramePlacements(self.model, self.data)

        # 获取末端位置
        ee_transform = self.data.oMf[self.ee_frame_id]
        ee_pos = ee_transform.translation

        # 计算雅可比
        _, J_pos = self.compute_jacobian(q_joints)

        return ee_pos, J_pos

    def test_inverse_mapping(self, q_joints, cart_velocity, damping=1e-4):
        """
        测试逆向映射：笛卡尔速度 → 关节速度

        Args:
            q_joints: 关节角度 (7,)
            cart_velocity: 笛卡尔速度 (3,)
            damping: 阻尼系数

        Returns:
            joint_velocity: 关节速度 (7,)
            condition_number: 条件数
            reconstruction_error: 重建误差
        """
        # 计算雅可比
        _, J_pos = self.compute_jacobian(q_joints)

        # 计算伪逆
        J_pinv, condition_number = self.compute_damped_pseudoinverse(J_pos, damping)

        # 逆向映射：ẋ → q̇
        joint_velocity = J_pinv @ cart_velocity

        # 验证：重建笛卡尔速度
        cart_velocity_reconstructed = J_pos @ joint_velocity
        reconstruction_error = np.linalg.norm(cart_velocity - cart_velocity_reconstructed)

        return joint_velocity, condition_number, reconstruction_error


def main():
    print("=" * 70)
    print("雅可比伪逆映射稳定性测试")
    print("=" * 70)

    # 初始化 IK solver
    project_root = Path(__file__).parent
    urdf_path = project_root / "ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf"

    controlled_joints = [
        'Left_Shoulder_Pitch_Joint',
        'Left_Shoulder_Roll_Joint',
        'Left_Shoulder_Yaw_Joint',
        'Left_Elbow_Pitch_Joint',
        'Left_Wrist_Yaw_Joint',
        'Left_Wrist_Pitch_Joint',
        'Left_Wrist_Roll_Joint'
    ]

    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame="Left_Wrist_Yaw_Link",
        controlled_joints=controlled_joints
    )

    tester = JacobianTester(ik_solver)

    print("\n" + "=" * 70)
    print("测试1: 不同姿态下的条件数")
    print("=" * 70)

    # 测试多个姿态
    test_configs = [
        ("零位", np.zeros(7)),
        ("随机姿态1", np.random.uniform(-0.5, 0.5, 7)),
        ("随机姿态2", np.random.uniform(-1.0, 1.0, 7)),
        ("极限姿态", np.array([0.0, -0.3, 0.0, -1.2, 0.0, 0.8, 0.0])),
    ]

    for name, q_joints in test_configs:
        _, J_pos = tester.compute_jacobian(q_joints)
        _, cond_num = tester.compute_damped_pseudoinverse(J_pos, damping=1e-4)

        print(f"\n{name}:")
        print(f"  关节角度: {q_joints}")
        print(f"  条件数: {cond_num:.2e}")
        print(f"  稳定性: {'✓ 良好' if cond_num < 100 else '⚠ 注意' if cond_num < 1000 else '✗ 不稳定'}")

    print("\n" + "=" * 70)
    print("测试2: 笛卡尔速度 → 关节速度映射")
    print("=" * 70)

    # 固定姿态
    q_test = np.array([0.0, -0.3, 0.0, -1.2, 0.0, 0.8, 0.0])

    # 测试不同的笛卡尔速度
    cart_velocities = [
        ("静止", np.array([0.0, 0.0, 0.0])),
        ("X方向", np.array([0.1, 0.0, 0.0])),
        ("Y方向", np.array([0.0, 0.1, 0.0])),
        ("Z方向", np.array([0.0, 0.0, 0.1])),
        ("混合运动", np.array([0.05, 0.05, 0.05])),
    ]

    for name, cart_vel in cart_velocities:
        joint_vel, cond_num, recon_error = tester.test_inverse_mapping(
            q_test, cart_vel, damping=1e-4
        )

        print(f"\n{name}:")
        print(f"  笛卡尔速度: {cart_vel}")
        print(f"  关节速度: {joint_vel}")
        print(f"  重建误差: {recon_error:.2e} m/s")
        print(f"  映射质量: {'✓ 优秀' if recon_error < 1e-6 else '⚠ 一般' if recon_error < 1e-3 else '✗ 差'}")

    print("\n" + "=" * 70)
    print("测试3: 不同阻尼系数的影响")
    print("=" * 70)

    cart_vel_test = np.array([0.1, 0.05, 0.02])
    damping_values = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2]

    print(f"\n笛卡尔速度: {cart_vel_test}")
    print(f"关节姿态: {q_test}\n")

    for damping in damping_values:
        joint_vel, cond_num, recon_error = tester.test_inverse_mapping(
            q_test, cart_vel_test, damping=damping
        )

        print(f"阻尼系数 λ={damping:.0e}:")
        print(f"  条件数: {cond_num:.2e}")
        print(f"  重建误差: {recon_error:.2e}")
        print(f"  关节速度范数: {np.linalg.norm(joint_vel):.4f}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print("\n建议:")
    print("  1. 条件数 < 100: 数值稳定，可以安全使用")
    print("  2. 重建误差 < 1e-6: 映射精度高")
    print("  3. 阻尼系数建议: 1e-4 ~ 1e-3（平衡稳定性和精度）")


if __name__ == "__main__":
    main()

