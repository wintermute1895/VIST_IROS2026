#!/usr/bin/env python3
"""
测试 direction=1 和 direction=-1 在双向 URDF 下的行为
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.config_loader import VISTConfig

def test_both_directions():
    """测试两种 direction 设置"""

    print("=" * 80)
    print("双向 URDF 测试：direction=1 vs direction=-1")
    print("=" * 80)

    # 加载配置
    config = VISTConfig()

    # 获取当前配置
    current_direction = config.robot_joint_directions[3]
    current_offset = config.robot_joint_offsets[3]

    print(f"\n当前配置:")
    print(f"  direction: {current_direction}")
    print(f"  offset: {current_offset}")

    # 测试场景
    test_cases = [
        ("手臂伸直", 0.0),
        ("弯曲 60°", 60.0),
        ("弯曲 90°", 90.0),
        ("弯曲 120°", 120.0),
    ]

    # 测试 direction=1
    print("\n" + "=" * 80)
    print("测试 direction=1 (正向)")
    print("=" * 80)
    print(f"{'场景':<15} {'计算角度':<15} {'最终角度':<15} {'物理意义'}")
    print("-" * 80)

    direction = 1
    offset = 0
    for scene, angle_deg in test_cases:
        q_calc = np.radians(angle_deg)
        q_final = q_calc * direction + offset

        meaning = f"肘部弯曲 {np.degrees(q_final):.0f}°"
        if q_final == 0:
            meaning = "手臂伸直（零位）"

        print(f"{scene:<15} {angle_deg:>6.0f}° ({q_calc:>5.2f})  "
              f"{np.degrees(q_final):>6.0f}° ({q_final:>5.2f})  "
              f"{meaning}")

    # 测试 direction=-1
    print("\n" + "=" * 80)
    print("测试 direction=-1 (反向)")
    print("=" * 80)
    print(f"{'场景':<15} {'计算角度':<15} {'最终角度':<15} {'物理意义'}")
    print("-" * 80)

    direction = -1
    offset = 0
    for scene, angle_deg in test_cases:
        q_calc = np.radians(angle_deg)
        q_final = q_calc * direction + offset

        meaning = f"肘部弯曲 {np.degrees(q_final):.0f}°"
        if q_final == 0:
            meaning = "手臂伸直（零位）"

        print(f"{scene:<15} {angle_deg:>6.0f}° ({q_calc:>5.2f})  "
              f"{np.degrees(q_final):>6.0f}° ({q_final:>5.2f})  "
              f"{meaning}")

    # 结论
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    print("\n✅ URDF 现在支持双向旋转 [-126°, +126°]")
    print()
    print("direction=1 (正向):")
    print("  - 计算范围: [0°, 180°]")
    print("  - 最终范围: [0°, 180°]")
    print("  - 物理意义: 肘部向正方向弯曲")
    print("  - 适用场景: URDF 轴方向与真机一致")
    print()
    print("direction=-1 (反向):")
    print("  - 计算范围: [0°, 180°]")
    print("  - 最终范围: [-180°, 0°]")
    print("  - 物理意义: 肘部向负方向弯曲")
    print("  - 适用场景: URDF 轴方向与真机相反")
    print()
    print("💡 使用建议:")
    print("  1. 在仿真中测试，确定哪个 direction 的运动方向正确")
    print("  2. 如果 direction=1 正确，保持配置不变")
    print("  3. 如果 direction=-1 正确，修改配置文件")
    print("  4. 真机测试时，根据实际电机方向调整 direction")
    print("=" * 80)

if __name__ == "__main__":
    test_both_directions()
