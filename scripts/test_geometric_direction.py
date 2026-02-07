#!/usr/bin/env python3
"""
实际测试几何求解器在 direction=1 和 direction=-1 时的行为
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.config_loader import VISTConfig
from core.geometric_arm_solver import GeometricArmSolver
import pinocchio as pin

def test_geometric_solver_with_directions():
    """测试几何求解器在不同 direction 设置下的行为"""

    print("=" * 80)
    print("几何求解器 direction 参数测试")
    print("=" * 80)

    # 加载配置
    config = VISTConfig()

    # 加载机器人模型
    urdf_path = os.path.join(os.path.dirname(__file__), '..', 'urdf', 'gr1t2_right_arm.urdf')
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    # 定义控制关节
    controlled_joints = [
        'Right_Shoulder_Pitch_Joint',
        'Right_Shoulder_Roll_Joint',
        'Right_Shoulder_Yaw_Joint',
        'Right_Elbow_Pitch_Joint',
        'Right_Wrist_Yaw_Joint',
        'Right_Wrist_Pitch_Joint',
        'Right_Wrist_Roll_Joint'
    ]
    controlled_indices = [model.getJointId(name) - 1 for name in controlled_joints]
    ee_frame_id = model.getFrameId("Right_Wrist_Roll_Link")

    # 测试场景：手臂向前伸直，然后弯曲肘部
    shoulder_pos = np.array(config.robot_shoulder_position)

    test_cases = [
        ("手臂伸直", 0.0),
        ("肘部弯曲 60°", 60.0),
        ("肘部弯曲 90°", 90.0),
        ("肘部弯曲 120°", 120.0),
    ]

    for direction_value in [1, -1]:
        print(f"\n{'=' * 80}")
        print(f"测试 direction = {direction_value}")
        print(f"{'=' * 80}")

        # 临时修改配置
        original_direction = config._config['robot']['joint_directions'][3]
        config._config['robot']['joint_directions'][3] = direction_value

        # 创建几何求解器
        geo_solver = GeometricArmSolver(
            model=model,
            data=data,
            controlled_joints=controlled_indices,
            ee_frame_id=ee_frame_id,
            config=config
        )

        print(f"\n配置:")
        print(f"  joint_directions[3] = {geo_solver.joint_directions[3]}")
        print(f"  joint_offsets[3] = {geo_solver.joint_offsets[3]}")
        print(f"  joint_limits[3] = {config.robot_joint_limits[3]}")
        print()

        print(f"{'场景':<15} {'肘部角度':<12} {'q4_calc':<15} {'q4_final':<15} {'是否超限'}")
        print("-" * 80)

        for scene, elbow_angle_deg in test_cases:
            # 构造测试姿态
            # 大臂向前平伸，小臂根据 elbow_angle 弯曲
            elbow_angle_rad = np.radians(elbow_angle_deg)

            # 肘部位置（大臂向前 0.3m）
            elbow_pos = shoulder_pos + np.array([0.3, 0.0, 0.0])

            # 腕部位置（根据肘部角度计算）
            # 如果 elbow_angle = 0°，小臂继续向前
            # 如果 elbow_angle = 90°，小臂向下
            forearm_length = 0.25
            wrist_offset = np.array([
                forearm_length * np.cos(elbow_angle_rad),
                0.0,
                -forearm_length * np.sin(elbow_angle_rad)
            ])
            wrist_pos = elbow_pos + wrist_offset

            # 计算几何解
            try:
                q_solution = geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)

                # 提取 q4
                q4_final = q_solution[3]

                # 反推 q4_calc
                q4_calc = (q4_final - geo_solver.joint_offsets[3]) / geo_solver.joint_directions[3]

                # 检查是否超限
                limit = config.robot_joint_limits[3]
                within_limit = (q4_final >= limit[0]) and (q4_final <= limit[1])
                status = "✓ 正常" if within_limit else "✗ 超限"

                print(f"{scene:<15} {elbow_angle_deg:>6.0f}°  "
                      f"{np.degrees(q4_calc):>6.1f}° ({q4_calc:>5.2f})  "
                      f"{np.degrees(q4_final):>6.1f}° ({q4_final:>5.2f})  "
                      f"{status}")

            except Exception as e:
                print(f"{scene:<15} {elbow_angle_deg:>6.0f}°  ERROR: {e}")

        # 恢复原始配置
        config._config['robot']['joint_directions'][3] = original_direction

    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    print("\n关键发现:")
    print("1. arccos(cos_angle) 总是返回 [0°, 180°]，表示两向量夹角")
    print("2. direction=1: 保持原始角度，q4 ∈ [0°, 180°]")
    print("3. direction=-1: 翻转角度符号，q4 ∈ [-180°, 0°]")
    print()
    print("物理意义:")
    print("- direction=1: 肘部从伸直(0°)向正方向弯曲(+角度)")
    print("- direction=-1: 肘部从伸直(0°)向负方向弯曲(-角度)")
    print()
    print("如果机器人肘部只能单向弯曲，direction=-1 会让它反向弯曲，")
    print("这可能导致:")
    print("  1. 超出物理限制（关节卡死）")
    print("  2. 电机控制器拒绝执行")
    print("  3. 运动方向与预期相反")
    print()
    print("建议:")
    print("- 如果 direction=1 时映射正确，保持 direction=1")
    print("- 如果电机方向需要调整，在电机驱动层面翻转，而非运动学层面")
    print("=" * 80)

if __name__ == "__main__":
    test_geometric_solver_with_directions()
