#!/usr/bin/env python3
"""
测试在掉使能状态下是否能实时获取位姿更新
"""
import sys
import time
from pathlib import Path

# 添加 SDK 路径
project_root = Path(__file__).parent.parent
sdk_path = project_root / "src" / "robot" / "sdk" / "linkerarm"
sys.path.insert(0, str(sdk_path))

from lbot.lbot_api import LbotAPI, LbotArm

def test_realtime_pose():
    """测试实时位姿获取"""

    # 连接机器人
    api = LbotAPI()
    print("正在连接到机器人...")
    if not api.init("192.168.10.21"):
        print("连接失败")
        return

    print("正在启动状态监控...")
    if not api.start_state_monitor():
        print("启动状态监控失败")
        return

    time.sleep(0.5)

    print("\n开始监控位姿变化...")
    print("请手动移动机械臂（可以掉使能），观察位姿是否实时更新")
    print("按 Ctrl+C 停止\n")

    try:
        last_pos = None
        count = 0

        while True:
            # 获取当前状态
            state = api.get_current_state()

            if state is None:
                print("无法获取状态")
                time.sleep(0.5)
                continue

            # 获取右臂位姿
            arm_state = state.right_arm
            pos = arm_state.end_effector_position
            euler = arm_state.euler

            current_pos = [pos.x, pos.y, pos.z, euler.x, euler.y, euler.z]

            # 检查是否有变化
            if last_pos is not None:
                diff = [abs(c - l) for c, l in zip(current_pos, last_pos)]
                max_diff = max(diff)

                if max_diff > 0.0001:  # 如果有明显变化
                    count += 1
                    print(f"\n[{count}] 检测到位姿变化:")
                    print(f"  位置: x={pos.x:.4f}, y={pos.y:.4f}, z={pos.z:.4f}")
                    print(f"  姿态: rx={euler.x:.4f}, ry={euler.y:.4f}, rz={euler.z:.4f}")
                    print(f"  最大变化: {max_diff:.6f}")

            last_pos = current_pos
            time.sleep(0.1)  # 100ms 采样间隔

    except KeyboardInterrupt:
        print("\n\n停止监控")

    finally:
        api.stop_state_monitor()
        api.cleanup()
        print("已断开连接")


if __name__ == "__main__":
    test_realtime_pose()