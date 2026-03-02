#!/usr/bin/env python3
"""
检查控制指令关节顺序工具

目的：
1. 查看遥操配置文件中的关节顺序
2. 对比 URDF 中的关节顺序
3. 建立映射关系

使用方法：
    python3 scripts/check_control_joint_order.py
"""

import yaml
from pathlib import Path


def main():
    print("="*80)
    print("  控制指令关节顺序检查工具")
    print("="*80)

    # 1. URDF 中的关节顺序（已知）
    print("\n" + "="*80)
    print("  1️⃣ URDF 中的关节顺序（从基座到末端）")
    print("="*80)

    urdf_joints = [
        "Left_Shoulder_Pitch_Joint",
        "Left_Shoulder_Roll_Joint",
        "Left_Shoulder_Yaw_Joint",
        "Left_Elbow_Pitch_Joint",
        "Left_Wrist_Yaw_Joint",
        "Left_Wrist_Pitch_Joint",
        "Left_Wrist_Roll_Joint"
    ]

    for i, joint in enumerate(urdf_joints, 1):
        print(f"  {i}. {joint}")

    # 2. 遥操配置文件中的关节顺序
    print("\n" + "="*80)
    print("  2️⃣ 遥操配置文件中的关节映射")
    print("="*80)

    teleop_config_path = '/home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml'

    try:
        with open(teleop_config_path, 'r') as f:
            config = yaml.safe_load(f)

        print(f"\n✓ 已加载配置文件: {teleop_config_path}\n")

        # 查找关节映射相关的配置
        if 'teleop_bridge' in config and 'ros__parameters' in config['teleop_bridge']:
            params = config['teleop_bridge']['ros__parameters']

            # 打印 negation 映射
            if 'negation' in params:
                negation = params['negation']
                print(f"Negation 映射（14个关节）:")
                print(f"  {negation}")
                print(f"\n左臂（前7个）: {negation[:7]}")
                print(f"右臂（后7个）: {negation[7:]}")

            # 打印其他相关配置
            print(f"\n其他配置:")
            for key in ['joint_names', 'controlled_joints', 'joint_mapping']:
                if key in params:
                    print(f"  {key}: {params[key]}")

        else:
            print("⚠️  配置文件格式不符合预期")

    except FileNotFoundError:
        print(f"❌ 找不到配置文件: {teleop_config_path}")
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")

    # 3. 分析
    print("\n" + "="*80)
    print("  3️⃣ 分析与建议")
    print("="*80)

    print("\n💡 关键问题:")
    print("  1. 控制指令中的关节顺序是什么？")
    print("     - 是否与 URDF 顺序一致？")
    print("     - 如果不一致，需要建立映射关系")
    print("\n  2. Negation 映射的含义是什么？")
    print("     - 是否表示关节方向需要反向？")
    print("     - 对应的是哪个关节？")
    print("\n  3. 末端执行器的选择：")
    print("     - URDF 中：Left_Wrist_Roll_Link（Z = 0.713m，最末端）")
    print("     - 控制指令中：需要确认")

    print("\n📋 下一步:")
    print("  1. 查看实际的控制指令话题（如 /left_arm_joint_control）")
    print("  2. 确认控制指令中的关节顺序")
    print("  3. 建立 URDF 关节顺序 ↔ 控制指令顺序 的映射")
    print("  4. 更新 negation 映射以匹配正确的关节顺序")


if __name__ == '__main__':
    main()