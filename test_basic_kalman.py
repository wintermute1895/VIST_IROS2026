#!/usr/bin/env python3
"""
VIST 基础卡尔曼滤波测试脚本

测试目标：
1. 验证卡尔曼滤波基本功能
2. 验证关节方向映射
3. 验证滤波平滑效果
"""

import numpy as np
import sys
from pathlib import Path

# 添加路径
ros2_ws_root = Path(__file__).parent / "ros2_ws"
sys.path.insert(0, str(ros2_ws_root))

from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.config.config_loader import get_config


class SimpleConfig:
    """简单配置对象"""
    def __init__(self):
        self.robot_model_urdf_file = "config/urdf/lkls73_o2_dual_arm_description_absolute.urdf"
        self.robot_model_end_effector_frame = "Left_End_Effector"


def test_basic_kalman_filter():
    """测试基础卡尔曼滤波"""
    print("=" * 60)
    print("VIST 基础卡尔曼滤波测试")
    print("=" * 60)

    # 创建配置
    config = SimpleConfig()

    # 创建 IK solver（用于接口兼容）
    project_root = Path(__file__).parent
    urdf_path = project_root / config.robot_model_urdf_file

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
        end_effector_frame=config.robot_model_end_effector_frame,
        controlled_joints=controlled_joints
    )

    # 创建卡尔曼滤波器
    kf = VISTKalmanFilter(ik_solver, config)

    print("\n" + "=" * 60)
    print("测试1: 恒定输入（验证收敛）")
    print("=" * 60)

    # 恒定输入
    constant_input = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    target_pose = np.eye(4)  # 简单的目标位姿

    print(f"\n输入: {constant_input}")
    print("\n开始滤波...")

    for i in range(10):
        filtered = kf.update(constant_input, target_pose)
        if i % 3 == 0:
            print(f"  第{i+1}帧: {filtered[:3]}... (前3个关节)")

    print(f"\n最终输出: {filtered}")
    print(f"与输入差异: {np.linalg.norm(filtered - constant_input):.6f}")

    print("\n" + "=" * 60)
    print("测试2: 带噪声输入（验证平滑）")
    print("=" * 60)

    # 重置滤波器
    kf.reset()

    # 带噪声的输入
    base_input = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    noise_std = 0.02

    print(f"\n基准输入: {base_input}")
    print(f"噪声标准差: {noise_std}")
    print("\n开始滤波...")

    for i in range(10):
        noisy_input = base_input + np.random.normal(0, noise_std, 7)
        filtered = kf.update(noisy_input, target_pose)
        if i % 3 == 0:
            print(f"  第{i+1}帧:")
            print(f"    噪声输入: {noisy_input[:3]}...")
            print(f"    滤波输出: {filtered[:3]}...")

    print("\n" + "=" * 60)
    print("测试3: 关节方向映射（索引2和4反转）")
    print("=" * 60)

    # 重置滤波器
    kf.reset()

    # 测试关节2和4的方向
    test_input = np.zeros(7)
    test_input[2] = 0.5  # 关节2（索引2）
    test_input[4] = 0.3  # 关节4（索引4）

    print(f"\n输入（关节2=0.5, 关节4=0.3）: {test_input}")
    print("\n注意：如果在节点中已经反转，这里应该看到正常的值")

    for i in range(5):
        filtered = kf.update(test_input, target_pose)

    print(f"\n滤波输出: {filtered}")
    print(f"  关节2（索引2）: {filtered[2]:.6f}")
    print(f"  关节4（索引4）: {filtered[4]:.6f}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_basic_kalman_filter()
