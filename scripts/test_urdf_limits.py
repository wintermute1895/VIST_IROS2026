#!/usr/bin/env python3
"""
测试 URDF 关节限位和轴方向
验证 Elbow_Pitch 关节的物理约束
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pinocchio as pin

def test_urdf_joint_limits():
    """测试 URDF 中的关节限位"""

    print("=" * 80)
    print("URDF 关节限位测试")
    print("=" * 80)

    # 加载 URDF
    urdf_path = os.path.join(os.path.dirname(__file__), '..', 'config',
                             'lkls73_o2_dual_arm_description.urdf')

    if not os.path.exists(urdf_path):
        print(f"❌ URDF 文件不存在: {urdf_path}")
        return

    model = pin.buildModelFromUrdf(urdf_path)

    # 查找 Right_Elbow_Pitch_Joint
    joint_name = 'Right_Elbow_Pitch_Joint'

    try:
        joint_id = model.getJointId(joint_name)
        print(f"\n✅ 找到关节: {joint_name} (ID: {joint_id})")
    except:
        print(f"\n❌ 未找到关节: {joint_name}")
        return

    # 获取关节信息
    print(f"\n关节信息:")
    print(f"  关节 ID: {joint_id}")
    print(f"  关节索引: {joint_id - 1}")  # Pinocchio 的索引从 1 开始

    # 获取关节限位
    idx = joint_id - 1
    lower_limit = model.lowerPositionLimit[idx]
    upper_limit = model.upperPositionLimit[idx]

    print(f"\n关节限位 (URDF 定义):")
    print(f"  下限: {lower_limit:.4f} rad = {np.degrees(lower_limit):.2f}°")
    print(f"  上限: {upper_limit:.4f} rad = {np.degrees(upper_limit):.2f}°")
    print(f"  范围: [{lower_limit:.4f}, {upper_limit:.4f}] rad")

    # 分析限位范围
    print(f"\n限位分析:")
    if lower_limit >= 0 and upper_limit > 0:
        print(f"  ✓ 限位为正值范围 [0, {upper_limit:.2f}]")
        print(f"  → 关节只能向正方向旋转（单向弯曲）")
        print(f"  → direction=-1 会产生负值，超出限位")
    elif lower_limit < 0 and upper_limit <= 0:
        print(f"  ✓ 限位为负值范围 [{lower_limit:.2f}, 0]")
        print(f"  → 关节只能向负方向旋转（单向弯曲）")
        print(f"  → direction=1 会产生正值，超出限位")
    else:
        print(f"  ✓ 限位为双向范围 [{lower_limit:.2f}, {upper_limit:.2f}]")
        print(f"  → 关节可以双向旋转")
        print(f"  → direction=±1 都可以工作")

    # 测试不同角度是否在限位内
    print(f"\n角度测试:")
    print(f"{'角度':<15} {'在限位内':<12} {'说明'}")
    print("-" * 60)

    test_angles = [
        ("0°", 0.0),
        ("30°", np.radians(30)),
        ("60°", np.radians(60)),
        ("90°", np.radians(90)),
        ("120°", np.radians(120)),
        ("-30°", np.radians(-30)),
        ("-60°", np.radians(-60)),
        ("-90°", np.radians(-90)),
    ]

    for name, angle in test_angles:
        within_limit = (angle >= lower_limit) and (angle <= upper_limit)
        status = "✓ 是" if within_limit else "✗ 否"

        if within_limit:
            desc = "可以执行"
        else:
            if angle < lower_limit:
                desc = f"超出下限 (差 {np.degrees(lower_limit - angle):.1f}°)"
            else:
                desc = f"超出上限 (差 {np.degrees(angle - upper_limit):.1f}°)"

        print(f"{name:<15} {status:<12} {desc}")

    # 结论
    print(f"\n" + "=" * 80)
    print("结论")
    print("=" * 80)

    if lower_limit >= 0:
        print("\n❌ 问题确认:")
        print(f"  1. URDF 限位为 [0, {upper_limit:.2f}] rad，只允许正值")
        print(f"  2. 几何计算 q4 = arccos(...) 给出 [0, π] rad")
        print(f"  3. direction=1: q4 ∈ [0, π]，部分在限位内")
        print(f"  4. direction=-1: q4 ∈ [-π, 0]，完全超出限位 ❌")
        print()
        print("💡 解决方案:")
        print("  方案 1: 修改 URDF 文件，翻转关节轴方向")
        print("    - 将 <axis xyz=\"0 1 0\" /> 改为 <axis xyz=\"0 -1 0\" />")
        print(f"    - 将 <limit lower=\"0\" upper=\"{upper_limit:.2f}\" />")
        print(f"      改为 <limit lower=\"{-upper_limit:.2f}\" upper=\"0\" />")
        print()
        print("  方案 2: 保持 URDF 不变，使用 direction=1")
        print("    - 在真机控制时，在电机驱动层面翻转方向")
        print("    - 不在运动学层面使用 direction=-1")
    else:
        print("\n✅ URDF 限位正常，支持双向旋转")

    print("=" * 80)

if __name__ == "__main__":
    test_urdf_joint_limits()
