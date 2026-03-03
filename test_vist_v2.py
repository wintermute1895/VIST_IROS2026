#!/usr/bin/env python3
"""
测试 VIST v2.0：意图检测 + 笛卡尔约束 + 雅可比伪逆映射

测试场景：
1. 高速运动 → a 低 → XYZ 自由
2. 低速运动 → a 高 → XY 粘稠，Z 自由
3. 速度变化 → a 动态调整
"""

import numpy as np
import sys
from pathlib import Path

# 添加路径
ros2_ws_root = Path(__file__).parent / "ros2_ws"
sys.path.insert(0, str(ros2_ws_root))

from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver


class SimpleConfig:
    """简单配置对象"""
    def __init__(self):
        self.robot_model_urdf_file = "ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf"
        self.robot_model_end_effector_frame = "Left_Wrist_Yaw_Link"


def test_intent_detection():
    """测试意图检测功能"""
    print("=" * 70)
    print("VIST v2.0 意图检测测试")
    print("=" * 70)

    # 初始化
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

    config = SimpleConfig()
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame,
        controlled_joints=controlled_joints
    )

    # 创建 VIST 滤波器
    print("\n初始化 VIST v2.0...")
    kf = VISTKalmanFilter(ik_solver, config)

    print("\n" + "=" * 70)
    print("测试场景1: 高速运动（自由移动）")
    print("=" * 70)

    # 初始位置
    q_base = np.array([0.0, -0.3, 0.0, -1.2, 0.0, 0.8, 0.0])

    # 模拟高速运动：快速改变关节角度
    print("\n模拟快速运动（大幅度变化）...")
    for i in range(20):
        # 快速变化
        q_obs = q_base + 0.1 * np.sin(i * 0.5) * np.ones(7)
        q_obs += np.random.normal(0, 0.02, 7)  # 添加噪声

        q_filtered = kf.update(q_obs, None)

        if i % 5 == 0:
            print(f"  帧{i}: 速度={kf.current_velocity_norm:.4f} m/s, α={kf.current_alpha:.2f}, "
                  f"模式={'精密' if kf.is_precision_mode else '自由'}")

    print("\n" + "=" * 70)
    print("测试场景2: 低速运动（精密对准）")
    print("=" * 70)

    # 重置滤波器
    kf.reset(q_base)

    # 模拟低速运动：微小变化
    print("\n模拟慢速运动（微小变化）...")
    for i in range(20):
        # 微小变化
        q_obs = q_base + 0.005 * np.sin(i * 0.1) * np.ones(7)
        q_obs += np.random.normal(0, 0.02, 7)

        q_filtered = kf.update(q_obs, None)

        if i % 5 == 0:
            print(f"  帧{i}: 速度={kf.current_velocity_norm:.4f} m/s, α={kf.current_alpha:.2f}, "
                  f"模式={'精密' if kf.is_precision_mode else '自由'}")

    print("\n" + "=" * 70)
    print("测试场景3: 速度变化（动态调整）")
    print("=" * 70)

    # 重置滤波器
    kf.reset(q_base)

    # 模拟速度从快到慢
    print("\n模拟速度从快到慢...")
    for i in range(30):
        # 速度逐渐减小
        amplitude = 0.1 * (1.0 - i / 30.0)  # 从0.1降到0
        q_obs = q_base + amplitude * np.sin(i * 0.3) * np.ones(7)
        q_obs += np.random.normal(0, 0.02, 7)

        q_filtered = kf.update(q_obs, None)

        if i % 5 == 0:
            print(f"  帧{i}: 速度={kf.current_velocity_norm:.4f} m/s, α={kf.current_alpha:.2f}, "
                  f"模式={'精密' if kf.is_precision_mode else '自由'}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print("\n观察:")
    print("  ✓ 高速运动时：a 应该接近 0（自由移动）")
    print("  ✓ 低速运动时：a 应该接近 5（精密对准）")
    print("  ✓ 速度变化时：a 应该平滑过渡")
    print("\n笛卡尔约束效果:")
    print("  - a 低时：XYZ 都自由")
    print("  - a 高时：XY 粘稠（速度降低），Z 自由（速度保持）")


if __name__ == "__main__":
    test_intent_detection()
