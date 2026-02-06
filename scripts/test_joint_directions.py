#!/usr/bin/env python3
"""
测试机械臂关节运动方向
逐个测试每个关节，验证电机转动方向是否正确
"""

import sys
import os
import time
import numpy as np

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver
import yaml


def test_joint_direction(driver, joint_idx, joint_name, delta_angle_deg=10.0):
    """
    测试单个关节的运动方向

    Args:
        driver: 机器人驱动器
        joint_idx: 关节索引 (0-6)
        joint_name: 关节名称
        delta_angle_deg: 测试移动角度（度）
    """
    print(f"\n{'='*80}")
    print(f"🔍 测试关节 {joint_idx}: {joint_name}")
    print(f"{'='*80}")

    # 1. 获取当前位置
    timestamp, q_current, _ = driver.get_state()
    print(f"📊 当前关节角度: {np.round(np.rad2deg(q_current), 2)}°")

    # 2. 创建目标位置（只改变当前关节）
    q_target = q_current.copy()
    delta_rad = np.deg2rad(delta_angle_deg)
    q_target[joint_idx] += delta_rad

    print(f"\n📍 测试计划:")
    print(f"  关节 {joint_idx} ({joint_name}): {np.rad2deg(q_current[joint_idx]):.2f}° → {np.rad2deg(q_target[joint_idx]):.2f}°")
    print(f"  增量: +{delta_angle_deg}°")

    # 3. 询问用户预期的运动方向
    print(f"\n❓ 预期运动方向:")
    if joint_idx == 0:  # Shoulder_Pitch
        print(f"  正值应该: 手臂向前抬起（pitch up）")
    elif joint_idx == 1:  # Shoulder_Roll
        print(f"  正值应该: 手臂向外展开（roll out）")
    elif joint_idx == 2:  # Shoulder_Yaw
        print(f"  正值应该: 手臂向左旋转（yaw left）")
    elif joint_idx == 3:  # Elbow_Pitch
        print(f"  正值应该: 肘部弯曲（bend）")
    elif joint_idx == 4:  # Wrist_Yaw
        print(f"  正值应该: 手腕向左旋转（yaw left）")
    elif joint_idx == 5:  # Wrist_Pitch
        print(f"  正值应该: 手腕向上抬起（pitch up）")
    elif joint_idx == 6:  # Wrist_Roll
        print(f"  正值应该: 手腕向内旋转（roll in）")

    # 4. 等待用户确认
    input(f"\n⏸️  按 Enter 开始测试...")

    # 5. 缓慢移动到目标位置
    print(f"\n🚀 开始移动...")
    steps = 50  # 50步，每步0.02秒，总共1秒
    for i in range(steps + 1):
        alpha = i / steps
        q_cmd = q_current + alpha * (q_target - q_current)
        driver.send_command(q_cmd)
        time.sleep(0.02)

    print(f"✅ 移动完成")

    # 6. 获取最终位置
    timestamp, q_final, _ = driver.get_state()
    actual_delta = np.rad2deg(q_final[joint_idx] - q_current[joint_idx])
    print(f"\n📊 实际移动:")
    print(f"  关节 {joint_idx}: {np.rad2deg(q_current[joint_idx]):.2f}° → {np.rad2deg(q_final[joint_idx]):.2f}°")
    print(f"  实际增量: {actual_delta:+.2f}°")

    # 7. 询问用户观察结果
    print(f"\n❓ 请观察机械臂的实际运动方向:")
    response = input(f"  运动方向是否符合预期？(y/n): ").strip().lower()

    if response == 'y':
        print(f"✅ 关节 {joint_idx} ({joint_name}) 方向正确")
        result = "✅ 正确"
    else:
        print(f"❌ 关节 {joint_idx} ({joint_name}) 方向错误！需要反转")
        result = "❌ 需要反转"

    # 8. 返回初始位置
    print(f"\n🔙 返回初始位置...")
    for i in range(steps + 1):
        alpha = i / steps
        q_cmd = q_final + alpha * (q_current - q_final)
        driver.send_command(q_cmd)
        time.sleep(0.02)

    print(f"✅ 已返回初始位置")
    time.sleep(0.5)

    return result


def main():
    print("="*80)
    print("🔍 机械臂关节方向测试")
    print("="*80)
    print("\n📝 测试说明:")
    print("  1. 逐个测试每个关节")
    print("  2. 每次只移动一个关节，其他关节保持不动")
    print("  3. 观察实际运动方向是否符合预期")
    print("  4. 记录需要反转的关节")

    # 1. 加载配置
    config_path = os.path.join(project_root, "config", "hardware.yaml")
    print(f"\n📁 加载配置: {config_path}")

    with open(config_path, 'r') as f:
        hw_config = yaml.safe_load(f)

    arm_config = hw_config['arm']
    print(f"  IP: {arm_config['ip']}")
    print(f"  Side: {arm_config['side']}")
    print(f"  DoF: {arm_config['dof']}")

    # 2. 初始化驱动器
    print("\n🦾 初始化真机驱动器...")
    driver = RealArmDriver(
        ip=arm_config['ip'],
        dof=arm_config['dof'],
        arm_side=arm_config['side']
    )

    # 3. 连接机器人
    print("\n🔌 连接机器人...")
    driver.connect()
    print("✅ 连接成功")

    # 4. 关节名称
    joint_names = [
        "Shoulder_Pitch",
        "Shoulder_Roll",
        "Shoulder_Yaw",
        "Elbow_Pitch",
        "Wrist_Yaw",
        "Wrist_Pitch",
        "Wrist_Roll"
    ]

    # 5. 测试每个关节
    results = {}

    try:
        for joint_idx in range(7):
            result = test_joint_direction(
                driver,
                joint_idx,
                joint_names[joint_idx],
                delta_angle_deg=15.0  # 测试移动15度
            )
            results[joint_idx] = result

            # 询问是否继续
            if joint_idx < 6:
                response = input(f"\n继续测试下一个关节？(y/n): ").strip().lower()
                if response != 'y':
                    break

        # 6. 显示测试结果
        print(f"\n{'='*80}")
        print(f"📊 测试结果汇总")
        print(f"{'='*80}")

        for joint_idx, result in results.items():
            print(f"  关节 {joint_idx} ({joint_names[joint_idx]:20s}): {result}")

        # 7. 生成修复建议
        needs_flip = [idx for idx, result in results.items() if "需要反转" in result]

        if needs_flip:
            print(f"\n⚠️ 需要反转的关节: {needs_flip}")
            print(f"\n💡 修复方法:")
            print(f"  在驱动器代码中，对这些关节的指令取反：")
            print(f"  q_cmd[{needs_flip}] = -q_cmd[{needs_flip}]")
        else:
            print(f"\n✅ 所有关节方向都正确！")

    except KeyboardInterrupt:
        print(f"\n\n⏹️ 用户中断")
    finally:
        driver.disconnect()
        print(f"\n✅ 已断开连接")


if __name__ == "__main__":
    main()
