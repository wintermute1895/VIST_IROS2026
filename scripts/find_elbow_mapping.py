#!/usr/bin/env python3
"""
找到人体肘部角度到机器人关节角度的正确映射

通过对比人体姿态和机器人姿态，找到正确的映射关系
"""
import numpy as np

def find_correct_mapping():
    """
    找到正确的映射关系

    人体肘部角度定义：
    - 180°：完全伸直
    - 90°：弯曲90度
    - 0°：完全折叠

    URDF关节角度定义（从测试结果）：
    - 0°：某个中间姿态
    - 正值：向上弯曲
    - 负值：向下伸直
    """

    print("="*80)
    print("寻找正确的映射关系")
    print("="*80)

    # 假设：URDF的180°对应人体的180°（完全伸直）
    # 那么URDF的0°对应人体的多少度？

    print("\n假设1：线性映射")
    print("-"*80)
    print("如果 URDF的180° = 人体的180°（伸直）")
    print("   URDF的0°   = 人体的0°（折叠）")
    print("\n那么映射关系是：")
    print("  q_robot = q_human")
    print("\n但这不对，因为URDF的限位是[-126°, 126°]")

    print("\n假设2：偏移映射")
    print("-"*80)
    print("如果 URDF的0° = 人体的90°（中间姿态）")
    print("   URDF的90° = 人体的180°（伸直）")
    print("   URDF的-90° = 人体的0°（折叠）")
    print("\n那么映射关系是：")
    print("  q_robot = q_human - 90°")

    print("\n假设3：反向映射")
    print("-"*80)
    print("如果 URDF的0° = 人体的90°（中间姿态）")
    print("   URDF的-90° = 人体的180°（伸直）")
    print("   URDF的90° = 人体的0°（折叠）")
    print("\n那么映射关系是：")
    print("  q_robot = 90° - q_human")
    print("  或者：q_robot = -(q_human - 90°)")

    # 测试不同的映射
    print("\n" + "="*80)
    print("测试不同映射关系")
    print("="*80)

    test_cases = [
        ("小臂下垂（接近伸直）", 161.57),
        ("小臂水平", 90.00),
        ("小臂向上抬", 47.87),
    ]

    for name, human_angle in test_cases:
        print(f"\n{name}（人体肘部角度 = {human_angle:.2f}°）:")

        # 方法1：直接使用
        robot1 = human_angle
        in_limit1 = -126 <= robot1 <= 126
        print(f"  方法1（直接）: q_robot = {robot1:.2f}° {'✓' if in_limit1 else '✗ 超出限位'}")

        # 方法2：偏移
        robot2 = human_angle - 90
        in_limit2 = -126 <= robot2 <= 126
        print(f"  方法2（偏移）: q_robot = {robot2:.2f}° {'✓' if in_limit2 else '✗ 超出限位'}")

        # 方法3：反向
        robot3 = 90 - human_angle
        in_limit3 = -126 <= robot3 <= 126
        print(f"  方法3（反向）: q_robot = {robot3:.2f}° {'✓' if in_limit3 else '✗ 超出限位'}")

        # 方法4：反向+偏移
        robot4 = -(human_angle - 90)
        in_limit4 = -126 <= robot4 <= 126
        print(f"  方法4（反向+偏移）: q_robot = {robot4:.2f}° {'✓' if in_limit4 else '✗ 超出限位'}")

    print("\n" + "="*80)
    print("推荐方案")
    print("="*80)
    print("\n方法3或方法4（它们是等价的）:")
    print("  q_robot = 90° - q_human")
    print("  或者：q_robot = -(q_human - 90°)")
    print("\n这样可以保证：")
    print("  - 人体180°（伸直）→ 机器人-90°")
    print("  - 人体90°（水平）→ 机器人0°")
    print("  - 人体0°（折叠）→ 机器人90°")
    print("  - 所有角度都在限位[-126°, 126°]内")

    print("\n实现方式：")
    print("  1. 在几何求解器中：q4 = π - arccos(cos_angle)")
    print("  2. 然后应用变换：q4_final = π/2 - q4")
    print("  3. 或者直接：q4_final = arccos(cos_angle) - π/2")

if __name__ == "__main__":
    find_correct_mapping()