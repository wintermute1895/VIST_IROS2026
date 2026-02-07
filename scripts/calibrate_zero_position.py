#!/usr/bin/env python3
"""
零位标定辅助脚本
帮助你在 Web 控制器中标定机器人零位

流程：
1. 连接真机
2. 读取当前关节角度
3. 提示你在 Web 控制器中调整到中立姿态
4. 在 Web 中设置零位
5. 验证零位是否正确

Author: VIST Project
Date: 2026-02-07
"""

import os
import sys
import time
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="零位标定辅助脚本")
    parser.add_argument("--ip", type=str, default="192.168.10.21",
                        help="机器人控制器 IP 地址")
    parser.add_argument("--arm", type=str, default="right", choices=["left", "right"],
                        help="使用哪个手臂")

    args = parser.parse_args()

    print("=" * 80)
    print("🎯 零位标定辅助脚本")
    print("=" * 80)

    print("\n📋 标定流程：")
    print("   1. 在 Web 控制器中调整机器人到中立姿态")
    print("      - 手臂自然下垂")
    print("      - Shoulder_Pitch = 0° (手臂垂直向下)")
    print("      - Shoulder_Roll = 0° (手臂不侧摆)")
    print("      - Shoulder_Yaw = 0° (手臂不旋转)")
    print("      - Elbow_Pitch = 0° (手臂伸直)")
    print("      - 腕部关节 = 0°")
    print()
    print("   2. 在 Web 控制器中点击'设置零位'按钮")
    print()
    print("   3. 运行此脚本验证零位是否正确")

    # 初始化驱动
    print(f"\n🦾 初始化真机驱动...")
    driver = RealArmDriver(
        ip=args.ip,
        dof=7,
        arm_side=args.arm
    )

    # 连接真机
    print(f"\n🔌 连接机器人 ({args.ip})...")
    success = driver.connect()
    if not success:
        print("❌ 连接失败！")
        return

    print("✅ 连接成功")

    try:
        # 读取当前状态
        print("\n📊 读取当前关节角度...")
        _, q_current, _ = driver.get_state()

        print("\n当前关节角度（弧度）:")
        joint_names = [
            "Shoulder_Pitch", "Shoulder_Roll", "Shoulder_Yaw",
            "Elbow_Pitch", "Wrist_Yaw", "Wrist_Pitch", "Wrist_Roll"
        ]
        for i, (name, angle) in enumerate(zip(joint_names, q_current)):
            print(f"   {i}. {name:15s}: {angle:+.4f} rad ({np.rad2deg(angle):+7.2f}°)")

        # 检查是否接近零位
        print("\n🔍 零位检查:")
        max_error = np.max(np.abs(q_current))
        max_error_deg = np.rad2deg(max_error)

        if max_error < 0.01:  # < 0.57°
            print(f"   ✅ 零位标定正确！最大偏差: {max_error_deg:.2f}°")
            print("\n💡 建议：")
            print("   在 config/system_config.yaml 中设置：")
            print("   joint_offsets: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]")
        elif max_error < 0.1:  # < 5.7°
            print(f"   ⚠️ 零位偏差较小: {max_error_deg:.2f}°")
            print("\n💡 建议：")
            print("   方案 1（推荐）：在 Web 控制器中重新标定零位")
            print("   方案 2：在配置文件中设置 joint_offsets 补偿")
            print("\n   如果选择方案 2，在 config/system_config.yaml 中设置：")
            print("   joint_offsets:")
            for i, angle in enumerate(q_current):
                print(f"     - {-angle:.6f}  # {joint_names[i]}")
        else:
            print(f"   ❌ 零位偏差较大: {max_error_deg:.2f}°")
            print("\n💡 建议：")
            print("   1. 在 Web 控制器中调整机器人到中立姿态")
            print("   2. 在 Web 控制器中点击'设置零位'")
            print("   3. 重新运行此脚本验证")

        # 显示当前配置文件中的 offset
        print("\n📄 当前配置文件中的 joint_offsets:")
        from src.config import get_config
        config = get_config()
        for i, offset in enumerate(config.robot_joint_offsets):
            print(f"   {i}. {joint_names[i]:15s}: {offset:+.6f} rad ({np.rad2deg(offset):+7.2f}°)")

        # 计算实际的关节角度（应用 offset 后）
        print("\n🔧 应用 offset 后的关节角度:")
        q_with_offset = q_current + np.array(config.robot_joint_offsets)
        for i, (name, angle) in enumerate(zip(joint_names, q_with_offset)):
            print(f"   {i}. {name:15s}: {angle:+.4f} rad ({np.rad2deg(angle):+7.2f}°)")

        # 检查应用 offset 后是否接近零位
        max_error_with_offset = np.max(np.abs(q_with_offset))
        max_error_with_offset_deg = np.rad2deg(max_error_with_offset)

        print(f"\n应用 offset 后的最大偏差: {max_error_with_offset_deg:.2f}°")

        if max_error_with_offset < 0.01:
            print("✅ 配置正确！")
        else:
            print("⚠️ 配置可能需要调整")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    finally:
        # 断开连接
        driver.disconnect()
        print("\n✅ 已断开连接")


if __name__ == "__main__":
    main()
