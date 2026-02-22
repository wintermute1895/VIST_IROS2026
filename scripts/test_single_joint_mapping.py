#!/usr/bin/env python3
"""
单关节映射测试脚本

功能：
1. 固定其他关节，只测试一个关节
2. 通过简单的正弦波运动测试关节方向
3. 验证关节方向配置是否正确

使用方法：
python scripts/test_single_joint_mapping.py --joint 0  # 测试第0个关节
"""

import os
import sys
import time
import argparse
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.robot.arm_driver import RealArmDriver

class SingleJointTester:
    """单关节测试器"""

    def __init__(self, joint_index):
        """
        初始化测试器

        Args:
            joint_index: 要测试的关节索引 (0-6)
        """
        self.joint_index = joint_index
        self.config = get_config()

        print("=" * 80)
        print(f"🔧 单关节映射测试 - 关节 {joint_index}")
        print("=" * 80)

        # 关节名称
        self.joint_names = [
            "Joint 0: Shoulder_Pitch",
            "Joint 1: Shoulder_Roll",
            "Joint 2: Shoulder_Yaw",
            "Joint 3: Elbow_Pitch",
            "Joint 4: Wrist_Yaw",
            "Joint 5: Wrist_Pitch",
            "Joint 6: Wrist_Roll"
        ]

        print(f"\n📍 测试关节: {self.joint_names[joint_index]}")
        print(f"   关节方向配置: {self.config.robot_joint_directions[joint_index]}")
        print(f"   关节偏移: {self.config.robot_joint_offsets[joint_index]}")

        # 初始化驱动器
        print("\n🤖 初始化机器人驱动器...")
        self.driver = RealArmDriver(self.config)

    def connect(self):
        """连接机器人"""
        print("\n🔌 连接机器人...")
        success = self.driver.connect()
        if not success:
            raise RuntimeError("连接失败")

        # 读取初始位置
        _, self.q_init, _ = self.driver.get_state()
        print(f"\n📊 初始关节角度（度）:")
        for i, q in enumerate(np.rad2deg(self.q_init)):
            marker = " ← 测试关节" if i == self.joint_index else ""
            print(f"   Joint {i}: {q:7.2f}°{marker}")

        return True

    def run_test(self, amplitude=0.3, frequency=0.2, duration=20.0):
        """
        运行单关节测试

        Args:
            amplitude: 运动幅度（弧度）
            frequency: 运动频率（Hz）
            duration: 测试时长（秒）
        """
        print("\n" + "=" * 80)
        print("🚀 开始单关节测试")
        print("=" * 80)
        print(f"\n⚙️  测试参数:")
        print(f"   运动幅度: ±{np.rad2deg(amplitude):.1f}°")
        print(f"   运动频率: {frequency:.2f} Hz")
        print(f"   测试时长: {duration:.1f} 秒")

        print("\n📝 观察要点:")
        print(f"   1. 关节 {self.joint_index} 应该做正弦波运动")
        print(f"   2. 其他关节应该保持静止")
        print(f"   3. 运动方向应该符合预期")
        print(f"   4. 运动应该平滑，无抖动")

        print("\n⏱️  5秒后开始测试...")
        for i in range(5, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        print("   开始！\n")

        start_time = time.time()
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                # 计算当前时间
                t = time.time() - start_time

                # 生成正弦波运动
                angle_offset = amplitude * np.sin(2 * np.pi * frequency * t)

                # 构建目标关节角度
                q_target = self.q_init.copy()
                q_target[self.joint_index] = self.q_init[self.joint_index] + angle_offset

                # 发送命令
                self.driver.send_command(q_target)

                # 每秒打印一次状态
                if time.time() - last_print_time >= 1.0:
                    _, q_current, _ = self.driver.get_state()
                    current_angle = np.rad2deg(q_current[self.joint_index])
                    target_angle = np.rad2deg(q_target[self.joint_index])
                    offset_angle = np.rad2deg(angle_offset)

                    print(f"⏱️  {t:5.1f}s | "
                          f"目标偏移: {offset_angle:+6.1f}° | "
                          f"目标角度: {target_angle:7.2f}° | "
                          f"当前角度: {current_angle:7.2f}°")

                    last_print_time = time.time()

                # 控制频率
                time.sleep(self.config.control_dt)

        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断测试")

        print("\n✅ 测试完成")

    def disconnect(self):
        """断开连接"""
        print("\n🔌 断开连接...")
        self.driver.disconnect()
        print("✅ 已断开")


def main():
    parser = argparse.ArgumentParser(description="单关节映射测试")
    parser.add_argument("--joint", type=int, required=True,
                       help="要测试的关节索引 (0-6)")
    parser.add_argument("--amplitude", type=float, default=0.3,
                       help="运动幅度（弧度），默认 0.3 rad (约17度)")
    parser.add_argument("--frequency", type=float, default=0.2,
                       help="运动频率（Hz），默认 0.2 Hz")
    parser.add_argument("--duration", type=float, default=20.0,
                       help="测试时长（秒），默认 20 秒")

    args = parser.parse_args()

    # 验证关节索引
    if args.joint < 0 or args.joint > 6:
        print("❌ 错误: 关节索引必须在 0-6 之间")
        return

    # 创建测试器
    tester = SingleJointTester(args.joint)

    try:
        # 连接机器人
        tester.connect()

        # 运行测试
        tester.run_test(
            amplitude=args.amplitude,
            frequency=args.frequency,
            duration=args.duration
        )

    finally:
        # 断开连接
        tester.disconnect()


if __name__ == "__main__":
    main()