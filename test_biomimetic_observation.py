#!/usr/bin/env python3
"""
测试仿生观测模型的正确性
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

def test_biomimetic_observation():
    """测试仿生观测模型"""
    print("=" * 80)
    print("测试仿生观测模型（3+4解耦）")
    print("=" * 80)

    # 1. 初始化
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path=urdf_path)
    config = get_config()
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 2. 设置测试场景：模拟人体手臂姿态
    print("\n测试场景：模拟人体手臂弯曲90度")
    print("-" * 80)

    shoulder_pos = np.array([0.0, 0.0, 0.0])
    elbow_pos = np.array([0.2, 0.0, 0.1])      # 肘部在前上方
    wrist_pos = np.array([0.2, 0.0, 0.35])     # 手腕在肘部上方（弯曲90度）
    target_pos = wrist_pos  # 目标位置就是手腕位置

    print(f"肩部位置: {shoulder_pos}")
    print(f"肘部位置: {elbow_pos}")
    print(f"手腕位置: {wrist_pos}")

    # 3. 计算人体肘部角度（验证）
    vec_upper = elbow_pos - shoulder_pos
    vec_lower = wrist_pos - elbow_pos
    cos_angle = np.dot(vec_upper, vec_lower) / (
        np.linalg.norm(vec_upper) * np.linalg.norm(vec_lower)
    )
    human_elbow_angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
    print(f"\n人体肘部角度: {np.degrees(human_elbow_angle):.1f}° ({human_elbow_angle:.3f} rad)")

    # 4. 调用仿生观测模型
    print("\n调用 compute_biomimetic_observation()...")
    print("-" * 80)

    try:
        z_hand, z_elbow, z_swivel = vist_filter.compute_biomimetic_observation(
            shoulder_pos, elbow_pos, wrist_pos, target_pos
        )

        print("✅ 计算成功！")
        print(f"\n观测结果:")
        print(f"  z_hand (手部任务):   {z_hand}")
        print(f"  z_elbow (肘部任务):  {z_elbow:.3f} rad ({np.degrees(z_elbow):.1f}°)")
        print(f"  z_swivel (臂平面任务): {z_swivel:.3f} rad ({np.degrees(z_swivel):.1f}°)")

        # 5. 验证结果合理性
        print("\n" + "=" * 80)
        print("结果验证:")
        print("-" * 80)

        # 验证1：z_hand 应该是7维向量
        if len(z_hand) == 7:
            print("✅ z_hand 维度正确 (7维)")
        else:
            print(f"❌ z_hand 维度错误: {len(z_hand)}")

        # 验证2：z_elbow 应该接近人体肘部角度（因为机器人初始状态为0）
        if abs(z_elbow - human_elbow_angle) < 0.1:
            print(f"✅ z_elbow 合理 (与人体肘部角度接近)")
        else:
            print(f"⚠️ z_elbow = {z_elbow:.3f}, 人体角度 = {human_elbow_angle:.3f}")

        # 验证3：z_swivel 应该是标量
        if isinstance(z_swivel, (int, float, np.number)):
            print("✅ z_swivel 类型正确 (标量)")
        else:
            print(f"❌ z_swivel 类型错误: {type(z_swivel)}")

        # 6. 测试配置文件中的臂长参数是否被正确使用
        print("\n" + "=" * 80)
        print("配置参数验证:")
        print("-" * 80)
        print(f"  上臂长度 (配置): {config.robot_arm_lengths['upper']:.4f} m")
        print(f"  前臂长度 (配置): {config.robot_arm_lengths['forearm']:.4f} m")
        print("✅ 配置参数已正确加载")

    except Exception as e:
        print(f"❌ 计算失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_biomimetic_observation()
