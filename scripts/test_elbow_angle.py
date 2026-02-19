#!/usr/bin/env python3
"""
测试肘部角度计算

验证几何映射的肘部角度是否正确
"""
import numpy as np

def test_elbow_angle():
    """测试不同肘部弯曲角度的计算"""

    print("=" * 60)
    print("肘部角度计算测试")
    print("=" * 60)

    # 测试用例
    test_cases = [
        {
            "name": "完全伸直",
            "shoulder": np.array([0, 0, 0]),
            "elbow": np.array([0.3, 0, 0]),
            "wrist": np.array([0.6, 0, 0]),
            "expected_human_angle": 180  # 人体肘部角度（伸直）
        },
        {
            "name": "弯曲90度",
            "shoulder": np.array([0, 0, 0]),
            "elbow": np.array([0.3, 0, 0]),
            "wrist": np.array([0.3, 0.3, 0]),
            "expected_human_angle": 90  # 人体肘部角度
        },
        {
            "name": "弯曲45度",
            "shoulder": np.array([0, 0, 0]),
            "elbow": np.array([0.3, 0, 0]),
            "wrist": np.array([0.3 + 0.3*np.cos(np.radians(45)), 0.3*np.sin(np.radians(45)), 0]),
            "expected_human_angle": 135  # 人体肘部角度
        },
    ]

    for case in test_cases:
        print(f"\n测试: {case['name']}")
        print(f"  肩部: {case['shoulder']}")
        print(f"  肘部: {case['elbow']}")
        print(f"  腕部: {case['wrist']}")

        # 计算向量
        v_shoulder_elbow = case['elbow'] - case['shoulder']
        v_elbow_wrist = case['wrist'] - case['elbow']

        # 计算夹角（代码中的方法）
        r1 = np.linalg.norm(v_shoulder_elbow)
        r2 = np.linalg.norm(v_elbow_wrist)
        cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (r1 * r2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)

        # 向量夹角
        vector_angle_rad = np.arccos(cos_angle)
        vector_angle_deg = np.degrees(vector_angle_rad)

        # 人体肘部角度（补角）
        human_elbow_angle = 180 - vector_angle_deg

        print(f"  向量夹角: {vector_angle_deg:.1f}°")
        print(f"  人体肘部角度: {human_elbow_angle:.1f}°")
        print(f"  期望人体角度: {case['expected_human_angle']}°")

        # 检查URDF定义
        print(f"\n  如果URDF定义:")
        print(f"    - q4=0° 表示伸直 → 应该使用: q4 = π - arccos(cos_angle) = {np.degrees(np.pi - vector_angle_rad):.1f}°")
        print(f"    - q4=0° 表示折叠 → 应该使用: q4 = arccos(cos_angle) = {vector_angle_deg:.1f}°")

        # 判断哪个更合理
        if abs(human_elbow_angle - case['expected_human_angle']) < 1:
            print(f"  ✅ 使用补角（π - arccos）更符合人体")
        else:
            print(f"  ⚠️ 需要检查URDF定义")

if __name__ == "__main__":
    test_elbow_angle()