#!/usr/bin/env python3
"""
检查机械臂关节健康状态
"""
import os
import sys
import time
import numpy as np
import yaml

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver


def main():
    print("="*80)
    print("🔍 机械臂关节健康检查")
    print("="*80)

    # 加载配置
    config_path = os.path.join(project_root, "config", "hardware.yaml")
    with open(config_path, 'r') as f:
        hw_config = yaml.safe_load(f)

    arm_config = hw_config['arm']

    # 初始化驱动器
    print(f"\n🔌 连接机器人 ({arm_config['ip']})...")
    driver = RealArmDriver(
        ip=arm_config['ip'],
        dof=arm_config['dof'],
        arm_side=arm_config['side']
    )

    try:
        driver.connect()
        print("✅ 连接成功\n")

        # 关节限位
        joint_limits = np.array([
            [-2.9, 1.0],      # Shoulder_Pitch
            [-0.15, 3.14],    # Shoulder_Roll
            [-3.14, 3.14],    # Shoulder_Yaw
            [-2.35, 0.1],     # Elbow_Pitch
            [-3.14, 3.14],    # Wrist_Yaw
            [-1.57, 1.57],    # Wrist_Pitch
            [-3.14, 3.14]     # Wrist_Roll
        ])

        joint_names = [
            "Shoulder_Pitch",
            "Shoulder_Roll",
            "Shoulder_Yaw",
            "Elbow_Pitch",
            "Wrist_Yaw",
            "Wrist_Pitch",
            "Wrist_Roll"
        ]

        # 读取当前状态
        print("📊 当前关节状态:\n")
        timestamp, q_current, _ = driver.get_state()

        for i in range(7):
            angle_rad = q_current[i]
            angle_deg = np.rad2deg(angle_rad)
            min_deg = np.rad2deg(joint_limits[i][0])
            max_deg = np.rad2deg(joint_limits[i][1])

            # 计算距离限位的距离
            dist_to_min = angle_deg - min_deg
            dist_to_max = max_deg - angle_deg

            # 判断状态
            status = "✅"
            warning = ""
            if dist_to_min < 10:
                status = "⚠️"
                warning = f" (距下限仅 {dist_to_min:.1f}°)"
            elif dist_to_max < 10:
                status = "⚠️"
                warning = f" (距上限仅 {dist_to_max:.1f}°)"

            print(f"{status} 关节{i} ({joint_names[i]:15s}): {angle_deg:7.2f}° "
                  f"[限位: {min_deg:7.1f}° ~ {max_deg:7.1f}°]{warning}")

        print("\n" + "="*80)
        print("💡 提示:")
        print("  - 如果某个关节接近限位（<10°），可能会导致控制问题")
        print("  - 如果关节'变软'，可能是触碰了限位或过热保护")
        print("  - 建议手动将机械臂移动到中间位置后再开始遥操作")
        print("="*80)

    finally:
        driver.disconnect()
        print("\n✅ 已断开连接")


if __name__ == "__main__":
    main()
