#!/usr/bin/env python3
"""
完整的肘部角度计算流程调试

从视觉关键点 → motion_mapper → geometric_arm_solver → 最终关节角度
"""

import numpy as np
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper
from src.config import get_config

def test_full_pipeline():
    """测试完整的角度计算流程"""

    print("=" * 80)
    print("完整肘部角度计算流程调试")
    print("=" * 80)

    # 初始化
    config = get_config()
    mapper = ArmMotionMapper()

    # 测试用例：模拟不同的手臂姿态（在肩部坐标系中）
    # 肩部坐标系：X=up, Y=right, Z=forward
    test_cases = [
        {
            "name": "手臂自然下垂（伸直）",
            "human_kps": {
                "shoulder": [0, 0, 0],
                "elbow": [-0.3, 0, 0],  # X负方向 = 向下
                "wrist": [-0.55, 0, 0],  # 继续向下
                "index_mcp": [-0.6, 0.05, 0],
                "pinky_mcp": [-0.6, -0.05, 0],
            },
            "expected_human_elbow_angle": 180,  # 伸直
        },
        {
            "name": "小臂水平向前（90度弯曲）",
            "human_kps": {
                "shoulder": [0, 0, 0],
                "elbow": [-0.3, 0, 0],  # X负方向 = 向下
                "wrist": [-0.3, 0, 0.25],  # Z正方向 = 向前
                "index_mcp": [-0.3, 0.05, 0.3],
                "pinky_mcp": [-0.3, -0.05, 0.3],
            },
            "expected_human_elbow_angle": 90,
        },
        {
            "name": "小臂45度向前",
            "human_kps": {
                "shoulder": [0, 0, 0],
                "elbow": [-0.3, 0, 0],  # 向下
                "wrist": [-0.3 - 0.177, 0, 0.177],  # 45度向下前方
                "index_mcp": [-0.3 - 0.177, 0.05, 0.177 + 0.05],
                "pinky_mcp": [-0.3 - 0.177, -0.05, 0.177 + 0.05],
            },
            "expected_human_elbow_angle": 135,
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"测试 {i}: {case['name']}")
        print(f"{'=' * 80}")

        human_kps = case["human_kps"]

        # Step 1: Motion Mapper
        print("\n[Step 1] Motion Mapper: 视觉坐标 → 机器人笛卡尔空间")
        print("-" * 80)

        result = mapper.human_to_robot(human_kps)
        if result is None:
            print("❌ Motion Mapper 返回 None（奇异配置）")
            continue

        wrist_pos, wrist_quat, debug_info = result
        elbow_pos = debug_info['elbow_pos']

        print(f"  肩部位置（机器人坐标系）: {mapper.P_base_shoulder}")
        print(f"  肘部位置（机器人坐标系）: {elbow_pos}")
        print(f"  腕部位置（机器人坐标系）: {wrist_pos}")

        # 计算向量（在机器人坐标系中）
        v_shoulder_elbow_robot = elbow_pos - mapper.P_base_shoulder
        v_elbow_wrist_robot = wrist_pos - elbow_pos

        print(f"\n  大臂向量（机器人坐标系）: {v_shoulder_elbow_robot}")
        print(f"  小臂向量（机器人坐标系）: {v_elbow_wrist_robot}")

        # 计算向量夹角
        norm1 = np.linalg.norm(v_shoulder_elbow_robot)
        norm2 = np.linalg.norm(v_elbow_wrist_robot)
        cos_angle = np.dot(v_shoulder_elbow_robot, v_elbow_wrist_robot) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        vector_angle_rad = np.arccos(cos_angle)
        vector_angle_deg = np.degrees(vector_angle_rad)

        human_elbow_angle = 180 - vector_angle_deg

        print(f"\n  向量夹角: {vector_angle_deg:.1f}°")
        print(f"  人体肘部角度: {human_elbow_angle:.1f}° (期望: {case['expected_human_elbow_angle']}°)")

        # Step 2: 手动计算肘部角度（模拟 Geometric Arm Solver）
        print(f"\n[Step 2] 手动计算肘部角度（模拟 Geometric Arm Solver）")
        print("-" * 80)

        # 使用和 geometric_arm_solver.py 相同的逻辑
        v_shoulder_elbow = elbow_pos - mapper.P_base_shoulder
        v_elbow_wrist = wrist_pos - elbow_pos

        r = np.linalg.norm(v_shoulder_elbow)
        r_elbow_wrist = np.linalg.norm(v_elbow_wrist)

        cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (r * r_elbow_wrist)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)

        # 当前代码：直接使用向量夹角
        q4_rad = np.arccos(cos_angle)
        q4_deg = np.degrees(q4_rad)

        print(f"  计算出的肘部角度:")
        print(f"    q4 (Elbow Pitch):    {q4_deg:.1f}° = {q4_rad:.3f} rad")

        # 检查URDF限位
        urdf_lower = 0
        urdf_upper = 2.2  # rad
        urdf_upper_deg = np.degrees(urdf_upper)

        print(f"\n  URDF限位检查:")
        if q4_rad > urdf_upper:
            print(f"    ⚠️  q4 = {q4_deg:.1f}° 超出上限 {urdf_upper_deg:.1f}°")
        elif q4_rad < urdf_lower:
            print(f"    ⚠️  q4 = {q4_deg:.1f}° 低于下限 0°")
        else:
            print(f"    ✅ q4 在限位内 [0°, {urdf_upper_deg:.1f}°]")

        # Step 3: 应用关节方向和偏移
        print(f"\n[Step 3] 应用关节方向和偏移")
        print("-" * 80)

        joint_direction = config.robot_joint_directions[3]  # Elbow Pitch
        joint_offset = config.robot_joint_offsets[3]

        q4_final = q4_rad * joint_direction + joint_offset
        q4_final_deg = np.degrees(q4_final)

        print(f"  关节方向系数: {joint_direction}")
        print(f"  关节零位偏移: {joint_offset} rad")
        print(f"  最终电机角度: {q4_final_deg:.1f}° = {q4_final:.3f} rad")

        # 分析
        print(f"\n[分析]")
        print("-" * 80)
        print(f"  人体肘部角度: {human_elbow_angle:.1f}°")
        print(f"  向量夹角:     {vector_angle_deg:.1f}°")
        print(f"  计算的q4:     {q4_deg:.1f}°")
        print(f"  最终电机角度: {q4_final_deg:.1f}°")

        if abs(q4_deg - vector_angle_deg) < 0.1:
            print(f"  ✅ q4 = 向量夹角（符合预期）")
        else:
            print(f"  ❌ q4 ≠ 向量夹角（不符合预期）")

    print(f"\n{'=' * 80}")
    print("调试完成")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    test_full_pipeline()
