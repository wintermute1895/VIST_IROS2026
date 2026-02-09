#!/usr/bin/env python3
"""
LinkerArm 机械臂接口测试脚本

使用此脚本测试 LinkerArm (LBot) SDK 集成是否正常工作
"""

from robot_interface import LinkerArmInterface
import numpy as np
from pathlib import Path


def test_connection():
    """测试机器人连接"""
    print("=" * 60)
    print("测试 1: 连接到 LinkerArm 机器人")
    print("=" * 60)

    try:
        # 计算 SDK 路径（相对于项目根目录）
        project_root = Path(__file__).parent.parent
        sdk_path = project_root / "src" / "robot" / "sdk" / "linkerarm"

        # 创建机器人接口
        # 请根据实际情况修改 IP 地址和机械臂选择
        robot = LinkerArmInterface(
            tcp_host="192.168.10.21",  # 修改为你的机器人 IP
            arm_side="right",            # 或 "right"
            sdk_path=str(sdk_path)  # 使用动态计算的路径
        )

        print("✓ 成功连接到机器人\n")
        return robot

    except Exception as e:
        print(f"✗ 连接失败: {e}\n")
        return None


def test_get_pose(robot):
    """测试获取当前位姿"""
    print("=" * 60)
    print("测试 2: 获取当前机械臂位姿")
    print("=" * 60)

    try:
        # 获取当前位姿（4x4 齐次变换矩阵）
        pose_matrix = robot.get_current_pose()

        print("当前位姿矩阵 (4x4):")
        print(pose_matrix)

        # 提取位置和欧拉角
        from robot_interface import RobotInterface
        x, y, z, rx, ry, rz = RobotInterface.matrix_to_pose(pose_matrix)

        print(f"\n位置 (米):")
        print(f"  x = {x:.4f}")
        print(f"  y = {y:.4f}")
        print(f"  z = {z:.4f}")

        print(f"\n欧拉角 (弧度):")
        print(f"  roll  = {rx:.4f}")
        print(f"  pitch = {ry:.4f}")
        print(f"  yaw   = {rz:.4f}")

        print(f"\n欧拉角 (度):")
        print(f"  roll  = {np.rad2deg(rx):.2f}°")
        print(f"  pitch = {np.rad2deg(ry):.2f}°")
        print(f"  yaw   = {np.rad2deg(rz):.2f}°")

        print("\n✓ 成功获取位姿\n")
        return pose_matrix

    except Exception as e:
        print(f"✗ 获取位姿失败: {e}\n")
        return None


def test_move(robot, current_pose):
    """测试移动机械臂"""
    print("=" * 60)
    print("测试 3: 移动机械臂")
    print("=" * 60)

    # 询问用户是否要测试移动
    response = input("是否要测试机械臂移动？这将使机械臂移动！(y/N): ")

    if response.lower() != 'y':
        print("跳过移动测试\n")
        return

    try:
        # 创建目标位姿：在当前位置基础上沿 Z 轴向上移动 5cm
        target_pose = current_pose.copy()
        target_pose[2, 3] += 0.05  # Z 轴移动 5cm

        print("目标位姿：当前位置 + Z轴向上 5cm")
        print(f"目标 Z 坐标: {target_pose[2, 3]:.4f} 米")

        # 移动到目标位姿
        print("\n开始移动...")
        success = robot.move_to(target_pose)

        if success:
            print("✓ 移动成功\n")

            # 验证位姿
            print("验证新位姿...")
            new_pose = robot.get_current_pose()
            print(f"新的 Z 坐标: {new_pose[2, 3]:.4f} 米")

            # 移动回原位
            response = input("是否移动回原位？(y/N): ")
            if response.lower() == 'y':
                print("\n移动回原位...")
                robot.move_to(current_pose)
                print("✓ 已返回原位\n")
        else:
            print("✗ 移动失败\n")

    except Exception as e:
        print(f"✗ 移动测试失败: {e}\n")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("LinkerArm (LBot) 机械臂接口测试")
    print("=" * 60 + "\n")

    # 测试 1: 连接
    robot = test_connection()
    if robot is None:
        print("无法连接到机器人，测试终止")
        return

    try:
        # 测试 2: 获取位姿
        current_pose = test_get_pose(robot)
        if current_pose is None:
            print("无法获取位姿，测试终止")
            return

        # 测试 3: 移动（可选）
        test_move(robot, current_pose)

        print("=" * 60)
        print("所有测试完成")
        print("=" * 60)

    finally:
        # 断开连接
        print("\n断开机器人连接...")
        robot.disconnect()
        print("✓ 已断开连接")


if __name__ == "__main__":
    main()
