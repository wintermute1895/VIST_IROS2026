#!/usr/bin/env python3
"""
测试 direction 参数的数学逻辑
对比 direction=1 和 direction=-1 时的角度计算
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.config_loader import VISTConfig

def test_elbow_angle_calculation():
    """测试肘部角度计算的数学逻辑"""

    print("=" * 80)
    print("肘部角度计算逻辑测试")
    print("=" * 80)

    # 模拟不同的肘部弯曲状态
    test_cases = [
        ("手臂伸直", 1.0),      # cos_angle = 1.0 → 两向量平行
        ("弯曲30°", 0.866),     # cos_angle = cos(30°)
        ("弯曲60°", 0.5),       # cos_angle = cos(60°)
        ("弯曲90°", 0.0),       # cos_angle = cos(90°)
        ("弯曲120°", -0.5),     # cos_angle = cos(120°)
        ("弯曲150°", -0.866),   # cos_angle = cos(150°)
        ("完全弯曲", -1.0),     # cos_angle = -1.0 → 两向量反向
    ]

    print("\n几何计算公式: q4 = arccos(cos_angle)")
    print("   cos_angle = dot(v_shoulder_elbow, v_elbow_wrist) / (|v1| * |v2|)")
    print("   arccos 返回范围: [0, π] rad = [0°, 180°]")
    print()

    # 测试 direction=1
    print("\n" + "=" * 80)
    print("情况 1: direction = 1, offset = 0")
    print("=" * 80)
    print(f"{'状态':<12} {'cos_angle':<12} {'q4_calc':<15} {'q4_final':<15} {'物理意义'}")
    print("-" * 80)

    for state, cos_angle in test_cases:
        q4_calc = np.arccos(cos_angle)
        direction = 1
        offset = 0
        q4_final = q4_calc * direction + offset

        print(f"{state:<12} {cos_angle:>10.3f}  "
              f"{np.degrees(q4_calc):>6.1f}° ({q4_calc:>5.2f})  "
              f"{np.degrees(q4_final):>6.1f}° ({q4_final:>5.2f})  "
              f"肘部弯曲 {np.degrees(q4_final):.0f}°")

    # 测试 direction=-1
    print("\n" + "=" * 80)
    print("情况 2: direction = -1, offset = 0")
    print("=" * 80)
    print(f"{'状态':<12} {'cos_angle':<12} {'q4_calc':<15} {'q4_final':<15} {'物理意义'}")
    print("-" * 80)

    for state, cos_angle in test_cases:
        q4_calc = np.arccos(cos_angle)
        direction = -1
        offset = 0
        q4_final = q4_calc * direction + offset

        # 分析物理意义
        if q4_final == 0:
            meaning = "手臂伸直（零位）"
        elif q4_final > 0:
            meaning = f"肘部向正方向弯曲 {np.degrees(q4_final):.0f}°"
        else:
            meaning = f"肘部向负方向弯曲 {np.degrees(q4_final):.0f}°"

        print(f"{state:<12} {cos_angle:>10.3f}  "
              f"{np.degrees(q4_calc):>6.1f}° ({q4_calc:>5.2f})  "
              f"{np.degrees(q4_final):>6.1f}° ({q4_final:>5.2f})  "
              f"{meaning}")

    # 关键分析
    print("\n" + "=" * 80)
    print("关键分析")
    print("=" * 80)
    print("\n1. 几何计算的物理意义:")
    print("   - arccos(cos_angle) 计算的是两个向量的夹角")
    print("   - 夹角范围: [0°, 180°]，总是正值")
    print("   - 0° = 手臂伸直，180° = 手臂完全弯曲")
    print()
    print("2. direction=1 的效果:")
    print("   - q4_final = q4_calc (不翻转)")
    print("   - 范围: [0°, 180°]")
    print("   - 物理意义: 肘部从伸直(0°)到完全弯曲(180°)")
    print()
    print("3. direction=-1 的效果:")
    print("   - q4_final = -q4_calc (翻转符号)")
    print("   - 范围: [-180°, 0°]")
    print("   - 物理意义: 肘部从完全弯曲(-180°)到伸直(0°)")
    print("   - ⚠️  注意: 负角度意味着向相反方向弯曲!")
    print()
    print("4. 问题诊断:")
    print("   - 如果机器人 URDF 定义 q4 ∈ [0°, 180°] (只能正向弯曲)")
    print("     那么 direction=-1 会产生负角度，可能超出物理限制")
    print()
    print("   - 如果机器人 URDF 定义 q4 ∈ [-180°, +180°] (可双向弯曲)")
    print("     那么 direction=-1 理论上可行，但物理意义变了:")
    print("     * direction=1: 人手弯曲 → 机器人正向弯曲")
    print("     * direction=-1: 人手弯曲 → 机器人负向弯曲")
    print()
    print("5. 可能的'卡死'原因:")
    print("   - 机器人肘部只能单向弯曲，direction=-1 让它反向弯曲")
    print("   - 或者，URDF 的关节限位实际上不允许负角度")
    print("   - 或者，电机控制器拒绝执行负角度命令")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_elbow_angle_calculation()
