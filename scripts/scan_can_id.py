#!/usr/bin/env python3
"""
测试不同的 CAN ID
帮助找到正确的硬件 CAN ID
"""

import sys
import os
import time

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

SDK_LINKERHAND_PATH = os.path.join(PROJECT_ROOT, "external_sdk", "linkerhand-ros2-sdk",
                                   "linker_hand_ros2_sdk", "linker_hand_ros2_sdk", "LinkerHand")
sys.path.insert(0, SDK_LINKERHAND_PATH)

from core.can.linker_hand_l10_can import LinkerHandL10Can

def test_can_id(can_id):
    """测试指定的 CAN ID"""
    print(f"\n测试 CAN ID: 0x{can_id:02X} (十进制: {can_id})")
    print("-" * 50)

    try:
        # 初始化
        hand = LinkerHandL10Can(can_id=can_id, can_channel='can0')

        # 获取版本
        version = hand.version
        if version:
            print(f"✅ 成功! 固件版本: {version}")

            # 发送测试命令
            print("  发送测试命令 (全 255)...")
            test_angles = [255.0] * 10
            hand.set_joint_positions(test_angles)
            time.sleep(2)

            print("  发送复位命令 (全 0)...")
            test_angles = [0.0] * 10
            hand.set_joint_positions(test_angles)
            time.sleep(1)

            return True
        else:
            print("❌ 无法获取版本信息")
            return False

    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("LinkerHand CAN ID 扫描工具")
    print("=" * 70)

    print("\n此工具将尝试常见的 CAN ID，帮助找到正确的硬件配置")
    print("\n常见的 CAN ID:")

    # 常见的 CAN ID 列表
    common_ids = [
        0x01,  # 1
        0x10,  # 16
        0x20,  # 32
        0x27,  # 39 (默认)
        0x30,  # 48
        0x40,  # 64
    ]

    print("\n将测试以下 CAN ID:")
    for can_id in common_ids:
        print(f"  - 0x{can_id:02X} (十进制: {can_id})")

    print("\n按 Enter 开始扫描...")
    input()

    # 测试每个 ID
    successful_ids = []

    for can_id in common_ids:
        if test_can_id(can_id):
            successful_ids.append(can_id)
            print(f"\n✅ CAN ID 0x{can_id:02X} 工作正常!")
            print("\n是否继续测试其他 ID? (y/n): ", end='')
            response = input().strip().lower()
            if response != 'y':
                break
        time.sleep(0.5)

    # 总结
    print("\n" + "=" * 70)
    print("扫描结果")
    print("=" * 70)

    if successful_ids:
        print(f"\n✅ 找到 {len(successful_ids)} 个工作的 CAN ID:")
        for can_id in successful_ids:
            print(f"  - 0x{can_id:02X} (十进制: {can_id})")

        print("\n建议:")
        print(f"  在 hand_control.py 中设置 CAN_ID = 0x{successful_ids[0]:02X}")
    else:
        print("\n❌ 没有找到工作的 CAN ID")
        print("\n可能的原因:")
        print("  1. 手没有正确供电")
        print("  2. CAN 线连接错误")
        print("  3. CAN 终端电阻配置错误")
        print("  4. 手的 DIP 开关设置了不常见的 ID")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n扫描被中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()