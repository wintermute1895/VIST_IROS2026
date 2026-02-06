#!/usr/bin/env python3
"""
简单的坐标变换测试 - 快速验证

使用方法：
1. 运行此脚本
2. 输入视觉坐标系中的点
3. 查看转换后的机器人坐标
"""

import os
import sys
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.coordinate_transform import get_vision_to_robot_transform, vision_to_robot_coords


def print_coordinate_systems():
    """打印坐标系定义"""
    print("\n" + "="*80)
    print("坐标系定义")
    print("="*80)
    print("\n视觉坐标系 (Shoulder Frame):")
    print("  X轴: 向上 (↑)")
    print("  Y轴: 向右 (→)")
    print("  Z轴: 向前 (⊙)")
    print("  原点: 肩部位置")

    print("\n机器人坐标系 (body_base_link):")
    print("  X轴: 向前 (⊙)")
    print("  Y轴: 向左 (←)")
    print("  Z轴: 向上 (↑)")
    print("  原点: 机器人基座")

    print("\n旋转矩阵 R:")
    R = get_vision_to_robot_transform()
    print(R)
    print("\n含义:")
    print("  第1行 [0, 0,-1]: X_robot = -Z_vision (机器人向前 = 视觉向后)")
    print("  第2行 [0,-1, 0]: Y_robot = -Y_vision (机器人向左 = 视觉向左)")
    print("  第3行 [1, 0, 0]: Z_robot = X_vision (机器人向上 = 视觉向上)")


def quick_test():
    """快速测试常见位置"""
    print("\n" + "="*80)
    print("快速测试 - 常见手部位置")
    print("="*80)

    T_shoulder = np.array([0.0, -0.096, 1.217])
    print(f"\n肩部位置 (机器人坐标): {T_shoulder}")

    test_cases = [
        ("肩部位置 (原点)", [0.0, 0.0, 0.0]),
        ("向前伸手 50cm", [0.0, 0.0, 0.5]),
        ("向右移动 30cm", [0.0, 0.3, 0.0]),
        ("向上抬手 40cm", [0.4, 0.0, 0.0]),
        ("右前上方", [0.3, 0.2, 0.4]),
        ("自然下垂", [0.0, 0.2, -0.5]),
    ]

    for name, P_vision in test_cases:
        P_robot = vision_to_robot_coords(P_vision, T_shoulder)
        print(f"\n{name}:")
        print(f"  视觉坐标: X={P_vision[0]:+.2f}, Y={P_vision[1]:+.2f}, Z={P_vision[2]:+.2f}")
        print(f"  机器人坐标: X={P_robot[0]:+.2f}, Y={P_robot[1]:+.2f}, Z={P_robot[2]:+.2f}")

        # 距离检查
        dist = np.linalg.norm(P_robot - T_shoulder)
        print(f"  距肩部: {dist:.3f}m", end='')

        # 合理性检查
        arm_length = 0.2908 + 0.2366  # 大臂 + 小臂
        if dist > arm_length * 1.2:
            print(" ⚠️ 超出臂长")
        elif P_robot[2] < 0.5:
            print(" ⚠️ 高度过低")
        else:
            print(" ✓")


def interactive_test():
    """交互式测试"""
    print("\n" + "="*80)
    print("交互式测试")
    print("="*80)
    print("\n输入视觉坐标系中的点，查看转换结果")
    print("格式: x y z (用空格分隔)")
    print("示例: 0.3 0.2 0.5")
    print("输入 'q' 退出\n")

    T_shoulder = np.array([0.0, -0.096, 1.217])

    while True:
        try:
            user_input = input("视觉坐标 (x y z): ").strip()
            if user_input.lower() == 'q':
                break

            coords = [float(x) for x in user_input.split()]
            if len(coords) != 3:
                print("❌ 请输入3个数字")
                continue

            P_vision = np.array(coords)
            P_robot = vision_to_robot_coords(P_vision, T_shoulder)

            print(f"\n结果:")
            print(f"  视觉坐标: X={P_vision[0]:+.3f}, Y={P_vision[1]:+.3f}, Z={P_vision[2]:+.3f}")
            print(f"  机器人坐标: X={P_robot[0]:+.3f}, Y={P_robot[1]:+.3f}, Z={P_robot[2]:+.3f}")

            # 距离和合理性
            dist = np.linalg.norm(P_robot - T_shoulder)
            arm_length = 0.2908 + 0.2366
            print(f"  距肩部: {dist:.3f}m (臂长: {arm_length:.3f}m)")

            if dist > arm_length * 1.2:
                print("  ⚠️ 警告: 超出臂长范围")
            elif P_robot[2] < 0.5:
                print("  ⚠️ 警告: 高度过低 (可能碰到地面)")
            elif abs(P_robot[1]) > 0.5:
                print("  ⚠️ 警告: 左右偏移过大")
            else:
                print("  ✓ 位置合理")

            print()

        except ValueError:
            print("❌ 输入格式错误，请输入3个数字\n")
        except KeyboardInterrupt:
            print("\n")
            break


def main():
    print("="*80)
    print("坐标变换简单测试")
    print("="*80)

    print_coordinate_systems()
    quick_test()

    print("\n" + "="*80)
    choice = input("\n是否进行交互式测试？(y/n): ").strip().lower()
    if choice == 'y':
        interactive_test()

    print("\n测试完成！")


if __name__ == "__main__":
    main()
