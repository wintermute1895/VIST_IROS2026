#!/usr/bin/env python3
"""
测试 SDK 关节顺序映射
通过单独控制每个关节来验证 SDK 的实际关节顺序

使用方法：
1. 连接真机
2. 运行此脚本
3. 观察每个关节的运动，确认 SDK 索引对应的物理关节

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


def test_single_joint(driver, joint_index, angle_deg=10.0, duration=2.0):
    """
    测试单个关节运动

    Args:
        driver: 真机驱动
        joint_index: 关节索引 (0-6)
        angle_deg: 运动角度（度）
        duration: 运动持续时间（秒）
    """
    print(f"\n{'='*80}")
    print(f"测试 SDK 关节 [{joint_index}]")
    print(f"{'='*80}")

    # 读取当前位置
    _, q_current, _ = driver.get_state()
    print(f"当前位置（度）: {np.round(np.rad2deg(q_current), 2)}")

    # 创建目标位置（只改变一个关节）
    q_target = q_current.copy()
    q_target[joint_index] += np.radians(angle_deg)

    print(f"\n目标位置（度）: {np.round(np.rad2deg(q_target), 2)}")
    print(f"变化: SDK[{joint_index}] 增加 {angle_deg}°")

    # 询问用户
    print(f"\n⚠️  即将移动 SDK 关节 [{joint_index}]")
    print(f"   预期运动: {angle_deg}° (约 {np.radians(angle_deg):.3f} rad)")
    response = input("   确认执行？(y/n): ")

    if response.lower() != 'y':
        print("   跳过此关节")
        return

    # 发送命令
    print(f"\n🚀 开始运动...")
    driver.send_command(q_target)

    # 等待运动完成
    time.sleep(duration)

    # 读取最终位置
    _, q_final, _ = driver.get_state()
    print(f"\n最终位置（度）: {np.round(np.rad2deg(q_final), 2)}")

    # 计算实际变化
    delta = q_final - q_current
    print(f"\n实际变化（度）:")
    for i, d in enumerate(delta):
        if abs(d) > 0.01:  # 只显示有明显变化的关节
            print(f"   SDK[{i}]: {np.rad2deg(d):+.2f}°")

    # 询问用户观察结果
    print(f"\n❓ 请观察机器人，哪个物理关节移动了？")
    print("   选项:")
    print("   0 - Shoulder Pitch (肩部俯仰)")
    print("   1 - Shoulder Roll (肩部侧摆)")
    print("   2 - Shoulder Yaw (肩部旋转)")
    print("   3 - Elbow Pitch (肘部俯仰)")
    print("   4 - Wrist Yaw (腕部旋转)")
    print("   5 - Wrist Pitch (腕部俯仰)")
    print("   6 - Wrist Roll (腕部翻转)")

    physical_joint = input(f"   SDK[{joint_index}] 对应的物理关节编号: ")

    try:
        physical_joint = int(physical_joint)
        joint_names = [
            "Shoulder Pitch", "Shoulder Roll", "Shoulder Yaw",
            "Elbow Pitch", "Wrist Yaw", "Wrist Pitch", "Wrist Roll"
        ]
        print(f"\n✅ 记录: SDK[{joint_index}] → {joint_names[physical_joint]}")
    except:
        print("   输入无效，跳过记录")

    # 返回初始位置
    print(f"\n🔙 返回初始位置...")
    driver.send_command(q_current)
    time.sleep(duration)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="测试 SDK 关节顺序映射")
    parser.add_argument("--ip", type=str, default="192.168.1.183",
                        help="机器人控制器 IP 地址")
    parser.add_argument("--arm", type=str, default="right", choices=["left", "right"],
                        help="使用哪个手臂")
    parser.add_argument("--angle", type=float, default=10.0,
                        help="测试角度（度）")
    parser.add_argument("--start", type=int, default=0,
                        help="起始关节索引 (0-6)")
    parser.add_argument("--end", type=int, default=6,
                        help="结束关节索引 (0-6)")

    args = parser.parse_args()

    print("=" * 80)
    print("🧪 SDK 关节顺序映射测试")
    print("=" * 80)
    print("\n⚠️  重要提示：")
    print("   1. 确保机器人周围无障碍物")
    print("   2. 准备好紧急停止按钮")
    print("   3. 仔细观察每个关节的运动")
    print("   4. 记录 SDK 索引与物理关节的对应关系")

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

    # 读取初始状态
    print("\n📊 读取初始状态...")
    _, q_init, _ = driver.get_state()
    print(f"初始关节角度（度）: {np.round(np.rad2deg(q_init), 2)}")

    # 测试每个关节
    try:
        for joint_idx in range(args.start, args.end + 1):
            test_single_joint(driver, joint_idx, args.angle, duration=2.0)

            # 询问是否继续
            if joint_idx < args.end:
                response = input(f"\n继续测试下一个关节？(y/n): ")
                if response.lower() != 'y':
                    break

        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)
        print("\n📝 请根据观察结果，更新 arm_driver.py 中的映射关系：")
        print("   - URDF_TO_SDK: URDF索引 → SDK索引")
        print("   - SDK_TO_URDF: SDK索引 → URDF索引")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    finally:
        # 返回初始位置
        print("\n🔙 返回初始位置...")
        driver.send_command(q_init)
        time.sleep(2.0)

        # 断开连接
        driver.disconnect()
        print("\n✅ 已断开连接")


if __name__ == "__main__":
    main()
