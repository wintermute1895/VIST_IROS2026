#!/usr/bin/env python3
"""
测试 LinkerHand CAN 通信
检查是否真的在发送数据到 CAN 总线
"""

import sys
import os
import time

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.robot.hand.hand_driver import LinkerHandDriver

def test_can_communication():
    """测试 CAN 通信"""

    print("=" * 70)
    print("LinkerHand CAN 通信测试")
    print("=" * 70)

    # 提示用户在另一个终端运行 candump
    print("\n请在另一个终端运行以下命令来监控 CAN 数据:")
    print("  candump can0")
    print("\n按 Enter 继续...")
    input()

    # 初始化驱动
    print("\n初始化驱动...")
    driver = LinkerHandDriver(
        can_id=0x27,
        can_channel="can0",
        mock_mode=False,
        enable_filtering=False  # 禁用过滤，确保每次都发送
    )

    print("\n开始发送测试命令...")
    print("请观察 candump 输出是否有数据\n")

    # 测试 1: 发送全 0
    print("[测试 1] 发送全 0 (手应该完全张开)")
    test_cmd_1 = [0.0] * 10
    success = driver.move(test_cmd_1)
    print(f"  发送结果: {'成功' if success else '失败'}")
    time.sleep(2)

    # 测试 2: 发送全 255
    print("\n[测试 2] 发送全 255 (手应该完全闭合)")
    test_cmd_2 = [255.0] * 10
    success = driver.move(test_cmd_2)
    print(f"  发送结果: {'成功' if success else '失败'}")
    time.sleep(2)

    # 测试 3: 发送中间值
    print("\n[测试 3] 发送中间值 127.5")
    test_cmd_3 = [127.5] * 10
    success = driver.move(test_cmd_3)
    print(f"  发送结果: {'成功' if success else '失败'}")
    time.sleep(2)

    # 测试 4: 连续发送
    print("\n[测试 4] 连续发送 10 次")
    for i in range(10):
        value = i * 25.5  # 0, 25.5, 51, ..., 229.5
        test_cmd = [value] * 10
        success = driver.move(test_cmd)
        print(f"  第 {i+1} 次: 值={value:.1f}, 结果={'成功' if success else '失败'}")
        time.sleep(0.5)

    # 关闭驱动
    print("\n关闭驱动...")
    driver.close()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print("\n请检查:")
    print("1. candump 是否显示了 CAN 数据?")
    print("2. CAN ID 是否为 0x27?")
    print("3. 手是否有任何反应?")
    print("=" * 70)

if __name__ == "__main__":
    try:
        test_can_communication()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()