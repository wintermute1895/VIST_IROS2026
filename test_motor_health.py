#!/usr/bin/env python3
"""
电机健康检查脚本
测试每个关节是否正常工作
"""

import sys
import time
from lbot import api as lbot_api
from lbot.robot import ArmType

def test_motor_health(arm_type=ArmType.RIGHT):
    """测试电机健康状态"""

    print("🔧 电机健康检查")
    print("=" * 50)

    # 1. 连接机器人
    print("\n1️⃣ 连接机器人...")
    try:
        success = lbot_api.connect("192.168.10.21", timeout=10.0)
        if not success:
            print("❌ 连接失败")
            return False
        print("✅ 连接成功")
    except Exception as e:
        print(f"❌ 连接异常: {e}")
        return False

    # 2. 读取当前状态
    print("\n2️⃣ 读取关节状态...")
    try:
        q_current = lbot_api.get_joint_state(arm_type)
        if q_current is None:
            print("❌ 无法读取关节状态")
            return False
        print(f"✅ 当前关节角度: {[f'{q:.3f}' for q in q_current]}")
    except Exception as e:
        print(f"❌ 读取状态异常: {e}")
        return False

    # 3. 逐个测试关节
    print("\n3️⃣ 测试各关节运动...")
    joint_names = ["J0_Shoulder_Pitch", "J1_Shoulder_Roll", "J2_Shoulder_Yaw",
                   "J3_Elbow_Pitch", "J4_Wrist_Yaw", "J5_Wrist_Pitch", "J6_Wrist_Roll"]

    all_healthy = True

    for i in range(7):
        print(f"\n   测试 {joint_names[i]} (关节{i})...")

        # 读取当前位置
        q_start = lbot_api.get_joint_state(arm_type)
        if q_start is None:
            print(f"   ❌ 无法读取关节{i}状态")
            all_healthy = False
            continue

        # 小幅度移动测试（±0.1 rad = ±5.7°）
        q_test = list(q_start)
        q_test[i] += 0.1  # 向正方向移动

        print(f"   → 移动到 {q_test[i]:.3f} rad...")
        success = lbot_api.move_joint(arm_type, q_test, speed=0.05, accel=0.05, block=True)

        if not success:
            print(f"   ❌ 关节{i}移动失败")
            all_healthy = False
            continue

        time.sleep(0.5)

        # 检查是否到达
        q_end = lbot_api.get_joint_state(arm_type)
        if q_end is None:
            print(f"   ❌ 无法读取关节{i}最终状态")
            all_healthy = False
            continue

        error = abs(q_end[i] - q_test[i])
        if error > 0.05:  # 误差大于2.8°
            print(f"   ⚠️ 关节{i}精度异常: 误差 {error:.3f} rad ({error*57.3:.1f}°)")
            all_healthy = False
        else:
            print(f"   ✅ 关节{i}正常 (误差 {error:.3f} rad)")

        # 返回原位
        lbot_api.move_joint(arm_type, q_start, speed=0.05, accel=0.05, block=True)
        time.sleep(0.5)

    # 4. 总结
    print("\n" + "=" * 50)
    if all_healthy:
        print("✅ 所有关节健康")
    else:
        print("⚠️ 部分关节异常，请检查")

    # 5. 断开连接
    lbot_api.disconnect()
    print("✅ 已断开连接")

    return all_healthy


if __name__ == "__main__":
    test_motor_health()
