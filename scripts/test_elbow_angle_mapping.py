#!/usr/bin/env python3
"""
测试肘部角度映射关系

验证：
1. URDF零位对应的实际姿态
2. 向量夹角和电机角度的关系
3. 人体肘部角度和电机角度的关系
"""

import numpy as np
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def test_angle_calculation():
    """测试不同姿态下的角度计算"""

    print("=" * 60)
    print("肘部角度映射关系测试")
    print("=" * 60)

    # 测试用例：不同的手臂姿态
    test_cases = [
        {
            "name": "手臂伸直（垂直向下）",
            "v_shoulder_elbow": np.array([0, 0, -1]),  # 向下
            "v_elbow_wrist": np.array([0, 0, -1]),     # 向下
            "expected_human_angle": 180,  # 人体肘部角度
        },
        {
            "name": "小臂水平向前（90度弯曲）",
            "v_shoulder_elbow": np.array([0, 0, -1]),  # 向下
            "v_elbow_wrist": np.array([1, 0, 0]),      # 向前
            "expected_human_angle": 90,
        },
        {
            "name": "手臂完全折叠",
            "v_shoulder_elbow": np.array([0, 0, -1]),  # 向下
            "v_elbow_wrist": np.array([0, 0, 1]),      # 向上
            "expected_human_angle": 0,
        },
        {
            "name": "小臂45度",
            "v_shoulder_elbow": np.array([0, 0, -1]),  # 向下
            "v_elbow_wrist": np.array([0.707, 0, -0.707]),  # 45度向下前方
            "expected_human_angle": 135,
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['name']}")
        print("-" * 60)

        v1 = case["v_shoulder_elbow"]
        v2 = case["v_elbow_wrist"]

        # 归一化
        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        # 计算向量夹角
        cos_angle = np.dot(v1, v2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        vector_angle_rad = np.arccos(cos_angle)
        vector_angle_deg = np.degrees(vector_angle_rad)

        # 计算人体肘部角度（补角）
        human_angle_deg = 180 - vector_angle_deg

        # 当前代码计算的电机角度（直接使用向量夹角）
        motor_angle_current = vector_angle_deg

        # 如果URDF零位是伸直姿态，电机角度应该等于向量夹角
        # 如果URDF零位不是伸直姿态，需要添加偏移

        print(f"  大臂方向: {v1}")
        print(f"  小臂方向: {v2}")
        print(f"  向量夹角: {vector_angle_deg:.1f}°")
        print(f"  人体肘部角度: {human_angle_deg:.1f}° (期望: {case['expected_human_angle']}°)")
        print(f"  当前代码计算的电机角度: {motor_angle_current:.1f}°")

        # 检查URDF限位
        urdf_lower = 0
        urdf_upper = 2.2  # rad = 126°
        urdf_upper_deg = np.degrees(urdf_upper)

        if motor_angle_current > urdf_upper_deg:
            print(f"  ⚠️  警告：电机角度 {motor_angle_current:.1f}° 超出URDF上限 {urdf_upper_deg:.1f}°")
        elif motor_angle_current < urdf_lower:
            print(f"  ⚠️  警告：电机角度 {motor_angle_current:.1f}° 低于URDF下限 {urdf_lower}°")
        else:
            print(f"  ✅ 电机角度在URDF限位内 [0°, {urdf_upper_deg:.1f}°]")

    print("\n" + "=" * 60)
    print("结论分析")
    print("=" * 60)
    print("如果URDF零位定义：")
    print("  - q4 = 0° → 手臂伸直")
    print("  - q4 = 126° → 手臂最大弯曲")
    print("\n那么：")
    print("  - 电机角度 = 向量夹角")
    print("  - 人体肘部角度 = 180° - 向量夹角")
    print("\n但是！如果实际测试发现角度不够，可能的原因：")
    print("  1. URDF零位不是手臂伸直，而是某个预设角度")
    print("  2. 需要添加角度偏移量")
    print("  3. 向量计算的坐标系有问题")

if __name__ == "__main__":
    test_angle_calculation()
