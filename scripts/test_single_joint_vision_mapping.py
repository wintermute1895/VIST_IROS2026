#!/usr/bin/env python3
"""
单关节视觉映射测试脚本

功能：
1. 接收视觉节点的数据
2. 只更新指定的关节，其他关节保持不动
3. 验证视觉到关节的映射是否正确

使用方法：
python scripts/test_single_joint_vision_mapping.py --joint 0  # 测试第0个关节
"""

import os
import sys
import time
import argparse
import json
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.robot.robot_interface import RobotInterface
from src.control.vist_controller import VISTController

class SingleJointVisionTester:
    """单关节视觉映射测试器"""

    def __init__(self, joint_index):
        """
        初始化测试器

        Args:
            joint_index: 要测试的关节索引 (0-6)
        """
        self.joint_index = joint_index
        self.config = get_config()

        print("=" * 80)
        print(f"🎥 单关节视觉映射测试 - 关节 {joint_index}")
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

        # 初始化机器人接口
        print("\n🤖 初始化机器人接口...")
        self.robot = RobotInterface(self.config)

        # 初始化 VIST 控制器
        print("\n🧠 初始化 VIST 控制器...")
        self.controller = VISTController(self.config)

    def connect(self):
        """连接机器人"""
        print("\n🔌 连接机器人和视觉节点...")
        self.q_init = self.robot.connect()
        print(f"\n📊 初始关节角度（度）:")
        for i, q in enumerate(np.rad2deg(self.q_init)):
            marker = " ← 测试关节" if i == self.joint_index else ""
            print(f"   Joint {i}: {q:7.2f}°{marker}")

        return True

    def run_test(self, duration=60.0):
        """
        运行单关节视觉映射测试

        Args:
            duration: 测试时长（秒）
        """
        print("\n" + "=" * 80)
        print("🚀 开始单关节视觉映射测试")
        print("=" * 80)

        print(f"\n📝 测试说明:")
        print(f"   1. 确保视觉节点正在运行")
        print(f"   2. 移动你的手臂")
        print(f"   3. 只有关节 {self.joint_index} 会跟随你的运动")
        print(f"   4. 其他关节保持初始位置不动")
        print(f"   5. 观察关节 {self.joint_index} 的运动方向是否正确")

        print("\n⏱️  5秒后开始测试...")
        for i in range(5, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        print("   开始！\n")

        start_time = time.time()
        last_print_time = time.time()
        frame_count = 0
        success_count = 0

        try:
            while time.time() - start_time < duration:
                # 接收视觉数据
                packet = self.robot.receive_keypoints()
                if packet is None:
                    time.sleep(self.config.control_dt)
                    continue

                # 提取关键点
                if 'keypoints' in packet:
                    human_keypoints = packet['keypoints']
                else:
                    human_keypoints = packet

                # 检查关键点完整性
                if 'wrist' not in human_keypoints or 'elbow' not in human_keypoints:
                    time.sleep(self.config.control_dt)
                    continue

                # 使用 VIST 控制器计算关节角度
                q_solution, success, debug_info = self.controller.process(human_keypoints)

                if not success:
                    time.sleep(self.config.control_dt)
                    continue

                success_count += 1

                # 构建混合命令：只更新测试关节，其他保持初始位置
                q_command = self.q_init.copy()
                q_command[self.joint_index] = q_solution[self.joint_index]

                # 发送命令
                self.robot.send_command(q_command)

                frame_count += 1

                # 每秒打印一次状态
                if time.time() - last_print_time >= 1.0:
                    _, q_current, _ = self.robot.get_state()

                    init_angle = np.rad2deg(self.q_init[self.joint_index])
                    target_angle = np.rad2deg(q_solution[self.joint_index])
                    current_angle = np.rad2deg(q_current[self.joint_index])
                    offset = target_angle - init_angle

                    print(f"⏱️  {time.time() - start_time:5.1f}s | "
                          f"帧数: {frame_count:4d} | "
                          f"成功率: {success_count/frame_count*100:5.1f}% | "
                          f"偏移: {offset:+6.1f}° | "
                          f"目标: {target_angle:7.2f}° | "
                          f"当前: {current_angle:7.2f}°")

                    last_print_time = time.time()

                # 控制频率
                time.sleep(self.config.control_dt)

        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断测试")

        print("\n✅ 测试完成")
        print(f"\n📊 统计:")
        print(f"   总帧数: {frame_count}")
        print(f"   成功帧数: {success_count}")
        if frame_count > 0:
            print(f"   成功率: {success_count/frame_count*100:.1f}%")

    def disconnect(self):
        """断开连接"""
        print("\n🔌 断开连接...")
        self.robot.disconnect()
        print("✅ 已断开")


def main():
    parser = argparse.ArgumentParser(description="单关节视觉映射测试")
    parser.add_argument("--joint", type=int, required=True,
                       help="要测试的关节索引 (0-6)")
    parser.add_argument("--duration", type=float, default=60.0,
                       help="测试时长（秒），默认 60 秒")

    args = parser.parse_args()

    # 验证关节索引
    if args.joint < 0 or args.joint > 6:
        print("❌ 错误: 关节索引必须在 0-6 之间")
        return

    # 创建测试器
    tester = SingleJointVisionTester(args.joint)

    try:
        # 连接机器人
        tester.connect()

        # 运行测试
        tester.run_test(duration=args.duration)

    finally:
        # 断开连接
        tester.disconnect()


if __name__ == "__main__":
    main()