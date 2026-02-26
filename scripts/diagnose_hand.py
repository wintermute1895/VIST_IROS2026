#!/usr/bin/env python3
"""
LinkerHand L10 诊断工具
检查 CAN 通信和硬件连接问题
"""

import sys
import os
import time
import subprocess

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

SDK_LINKERHAND_PATH = os.path.join(PROJECT_ROOT, "external_sdk", "linkerhand-ros2-sdk",
                                   "linker_hand_ros2_sdk", "linker_hand_ros2_sdk", "LinkerHand")
sys.path.insert(0, SDK_LINKERHAND_PATH)

from core.can.linker_hand_l10_can import LinkerHandL10Can

def check_can_interface():
    """检查 CAN 接口状态"""
    print("\n" + "=" * 70)
    print("1. 检查 CAN 接口状态")
    print("=" * 70)

    try:
        # 检查接口是否存在
        result = subprocess.run(['ip', 'link', 'show', 'can0'],
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ CAN 接口 can0 不存在")
            return False

        print("✅ CAN 接口 can0 存在")

        # 检查接口状态
        if 'UP' in result.stdout:
            print("✅ CAN 接口已启动 (UP)")
        else:
            print("❌ CAN 接口未启动")
            print("   请运行: sudo ip link set can0 up type can bitrate 1000000")
            return False

        # 检查波特率
        result = subprocess.run(['ip', '-details', 'link', 'show', 'can0'],
                              capture_output=True, text=True)
        if '1000000' in result.stdout:
            print("✅ 波特率: 1000000 (1Mbps)")
        else:
            print("⚠️  波特率可能不正确")
            print(result.stdout)

        return True

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

def check_can_traffic():
    """检查 CAN 总线流量"""
    print("\n" + "=" * 70)
    print("2. 检查 CAN 总线流量")
    print("=" * 70)

    try:
        result = subprocess.run(['ifconfig', 'can0'],
                              capture_output=True, text=True, timeout=2)

        lines = result.stdout.split('\n')
        for line in lines:
            if 'RX packets' in line or 'TX packets' in line:
                print(f"  {line.strip()}")

        print("\n✅ CAN 接口有数据流量")
        return True

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

def test_sdk_direct():
    """直接测试 SDK"""
    print("\n" + "=" * 70)
    print("3. 直接测试 SDK")
    print("=" * 70)

    try:
        print("\n初始化 SDK...")
        print("  CAN ID: 0x27")
        print("  CAN Channel: can0")

        hand = LinkerHandL10Can(can_id=0x27, can_channel='can0')

        print("✅ SDK 初始化成功")

        # 获取版本信息
        print("\n获取固件版本...")
        version = hand.version
        if version:
            print(f"✅ 固件版本: {version}")
        else:
            print("⚠️  无法获取固件版本（可能是通信问题）")

        # 测试发送命令
        print("\n发送测试命令...")

        # 测试 1: 全 0 (完全张开)
        print("\n[测试 1] 发送全 0 (手应该完全张开)")
        test_angles = [0.0] * 10
        hand.set_joint_positions(test_angles)
        print("  命令已发送，等待 3 秒...")
        time.sleep(3)

        # 测试 2: 全 255 (完全闭合)
        print("\n[测试 2] 发送全 255 (手应该完全闭合)")
        test_angles = [255.0] * 10
        hand.set_joint_positions(test_angles)
        print("  命令已发送，等待 3 秒...")
        time.sleep(3)

        # 测试 3: 中间值
        print("\n[测试 3] 发送中间值 127")
        test_angles = [127.0] * 10
        hand.set_joint_positions(test_angles)
        print("  命令已发送，等待 3 秒...")
        time.sleep(3)

        # 测试 4: 单个关节
        print("\n[测试 4] 只移动拇指 (索引 0 和 1)")
        test_angles = [0.0] * 10
        test_angles[0] = 180.0  # 拇指俯仰
        test_angles[1] = 180.0  # 拇指偏航
        hand.set_joint_positions(test_angles)
        print("  命令已发送，等待 3 秒...")
        time.sleep(3)

        # 复位
        print("\n[复位] 发送全 0")
        test_angles = [0.0] * 10
        hand.set_joint_positions(test_angles)
        time.sleep(1)

        print("\n✅ SDK 测试完成")
        return True

    except Exception as e:
        print(f"❌ SDK 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_can_id():
    """检查 CAN ID 配置"""
    print("\n" + "=" * 70)
    print("4. CAN ID 配置检查")
    print("=" * 70)

    print("\n当前配置的 CAN ID: 0x27 (十进制: 39)")
    print("\n请确认:")
    print("  1. 手的硬件 DIP 开关设置是否为 0x27")
    print("  2. 如果不确定，请尝试其他常见 ID:")
    print("     - 0x01 (十进制: 1)")
    print("     - 0x10 (十进制: 16)")
    print("     - 0x20 (十进制: 32)")
    print("     - 0x27 (十进制: 39) ← 当前使用")

def print_troubleshooting():
    """打印故障排除建议"""
    print("\n" + "=" * 70)
    print("故障排除建议")
    print("=" * 70)

    print("\n如果手仍然没有反应，请检查:")
    print("\n1. 硬件连接:")
    print("   - 手是否正确供电（电源指示灯是否亮）")
    print("   - CAN 线是否正确连接（CAN_H 和 CAN_L）")
    print("   - CAN 终端电阻是否正确配置（120Ω）")

    print("\n2. CAN ID 配置:")
    print("   - 检查手的 DIP 开关设置")
    print("   - 尝试使用 candump 查看实际的 CAN ID:")
    print("     candump can0")

    print("\n3. 固件状态:")
    print("   - 手的固件是否正常")
    print("   - 是否需要重启手的电源")

    print("\n4. 监控 CAN 数据:")
    print("   - 在另一个终端运行: candump can0")
    print("   - 观察是否有数据发送")
    print("   - 检查 CAN ID 是否匹配")

    print("\n5. 尝试不同的 CAN ID:")
    print("   - 修改 hand_control.py 中的 CAN_ID 配置")
    print("   - 或使用环境变量: export CAN_ID=0x01")

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("LinkerHand L10 诊断工具")
    print("=" * 70)

    # 检查 CAN 接口
    if not check_can_interface():
        print("\n❌ CAN 接口检查失败，请先解决接口问题")
        return

    # 检查 CAN 流量
    check_can_traffic()

    # 检查 CAN ID
    check_can_id()

    # 测试 SDK
    print("\n" + "=" * 70)
    print("准备测试 SDK 通信")
    print("=" * 70)
    print("\n建议:")
    print("1. 在另一个终端运行: candump can0")
    print("2. 观察手是否有反应")
    print("3. 观察 candump 输出的 CAN 数据")
    print("\n按 Enter 继续测试...")
    input()

    test_sdk_direct()

    # 打印故障排除建议
    print_troubleshooting()

    print("\n" + "=" * 70)
    print("诊断完成")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n诊断被中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()