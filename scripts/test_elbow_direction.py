#!/usr/bin/env python3
"""
测试 Elbow_Pitch 方向反转后的角度范围
验证 direction=-1, offset=π/2 的配置是否正确
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.config_loader import VISTConfig

def test_elbow_range():
    """测试肘关节在不同弯曲角度下的最终输出"""

    # 加载配置
    config = VISTConfig()

    # 获取 Elbow_Pitch 的配置
    direction = config.robot_joint_directions[3]
    offset = config.robot_joint_offsets[3]
    joint_limit = config.robot_joint_limits[3]

    print("=" * 60)
    print("Elbow_Pitch 配置测试")
    print("=" * 60)
    print(f"方向系数 (direction): {direction}")
    print(f"零位偏移 (offset): {offset:.4f} rad = {np.degrees(offset):.1f}°")
    print(f"关节限位: [{joint_limit[0]:.2f}, {joint_limit[1]:.2f}] rad")
    print(f"           = [{np.degrees(joint_limit[0]):.1f}°, {np.degrees(joint_limit[1]):.1f}°]")
    print()

    # 测试不同的肘部弯曲角度
    test_angles = [0, 30, 60, 90, 120, 150, 180]  # 度

    print("肘部弯曲角度测试:")
    print("-" * 60)
    print(f"{'计算角度':<12} {'最终角度':<12} {'是否超限':<10}")
    print("-" * 60)

    for angle_deg in test_angles:
        # 几何计算给出的角度（弧度）
        q_calc = np.radians(angle_deg)

        # 应用方向和偏移
        q_final = q_calc * direction + offset

        # 检查是否超限
        within_limit = (q_final >= joint_limit[0]) and (q_final <= joint_limit[1])
        status = "✓ 正常" if within_limit else "✗ 超限"

        print(f"{angle_deg:>3}° ({q_calc:>5.2f}) → "
              f"{np.degrees(q_final):>6.1f}° ({q_final:>6.2f}) "
              f"{status}")

    print("-" * 60)

    # 计算理论范围
    q_calc_min = 0
    q_calc_max = np.pi
    q_final_min = q_calc_max * direction + offset  # 注意：direction=-1时最小值来自最大计算值
    q_final_max = q_calc_min * direction + offset

    print()
    print("理论角度范围:")
    print(f"  计算范围: [0°, 180°] = [0, {np.pi:.2f}] rad")
    print(f"  最终范围: [{np.degrees(q_final_min):.1f}°, {np.degrees(q_final_max):.1f}°]")
    print(f"           = [{q_final_min:.2f}, {q_final_max:.2f}] rad")
    print(f"  限位范围: [{np.degrees(joint_limit[0]):.1f}°, {np.degrees(joint_limit[1]):.1f}°]")
    print(f"           = [{joint_limit[0]:.2f}, {joint_limit[1]:.2f}] rad")

    # 判断是否完全在限位内
    if q_final_min >= joint_limit[0] and q_final_max <= joint_limit[1]:
        print()
        print("✓ 配置正确：整个运动范围都在关节限位内")
    else:
        print()
        print("✗ 配置错误：部分运动范围超出关节限位")
        print(f"  建议调整 offset 到 {(joint_limit[0] + joint_limit[1]) / 2:.4f} rad")

    print("=" * 60)

if __name__ == "__main__":
    test_elbow_range()
