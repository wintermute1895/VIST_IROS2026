#!/usr/bin/env python3
"""
坐标变换综合测试脚本

测试内容：
1. 基础坐标轴变换
2. 逆变换验证
3. 实际手部位置测试
4. 与真机对比验证
"""

import os
import sys
import numpy as np
import socket
import json
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.coordinate_transform import get_vision_to_robot_transform, vision_to_robot_coords
from src.core.motion_mapper import ArmMotionMapper


def test_basic_transform():
    """测试1: 基础坐标轴变换"""
    print("\n" + "="*80)
    print("测试1: 基础坐标轴变换")
    print("="*80)

    R = get_vision_to_robot_transform()
    T_shoulder = np.array([0.0, -0.096, 1.217])

    print("\n旋转矩阵 R:")
    print(R)
    print("\n肩部位置 T_shoulder (机器人坐标系):")
    print(f"  X={T_shoulder[0]:.3f} (前), Y={T_shoulder[1]:.3f} (左), Z={T_shoulder[2]:.3f} (上)")

    # 测试单位向量
    test_cases = [
        ("视觉X轴 (向上)", np.array([1.0, 0.0, 0.0]), "应该映射到机器人Z轴 (向上)"),
        ("视觉Y轴 (向右)", np.array([0.0, 1.0, 0.0]), "应该映射到机器人-Y轴 (向左)"),
        ("视觉Z轴 (向前)", np.array([0.0, 0.0, 1.0]), "应该映射到机器人X轴 (向前)"),
    ]

    print("\n单位向量测试:")
    for name, P_vision, expected in test_cases:
        P_robot = vision_to_robot_coords(P_vision, T_shoulder)
        P_robot_relative = P_robot - T_shoulder  # 相对于肩部的位置
        print(f"\n  {name}:")
        print(f"    视觉坐标: {P_vision}")
        print(f"    机器人坐标(相对): {P_robot_relative}")
        print(f"    预期: {expected}")

        # 验证
        if "X轴" in name:
            assert abs(P_robot_relative[2] - 1.0) < 0.01, "应该是Z=1"
            print("    ✓ 验证通过")
        elif "Y轴" in name:
            assert abs(P_robot_relative[1] + 1.0) < 0.01, "应该是Y=-1"
            print("    ✓ 验证通过")
        elif "Z轴" in name:
            assert abs(P_robot_relative[0] - 1.0) < 0.01, "应该是X=1"
            print("    ✓ 验证通过")


def test_inverse_transform():
    """测试2: 逆变换验证"""
    print("\n" + "="*80)
    print("测试2: 逆变换验证")
    print("="*80)

    R = get_vision_to_robot_transform()
    R_inv = R.T  # 旋转矩阵的逆 = 转置
    T_shoulder = np.array([0.0, -0.096, 1.217])

    print("\n验证 R @ R^T = I:")
    identity = R @ R_inv
    print(identity)
    assert np.allclose(identity, np.eye(3)), "R @ R^T 应该等于单位矩阵"
    print("✓ 旋转矩阵正交性验证通过")

    # 测试往返变换
    print("\n往返变换测试:")
    test_points = [
        np.array([0.3, 0.2, 0.5]),
        np.array([-0.1, 0.4, 0.3]),
        np.array([0.5, -0.2, 0.6]),
    ]

    for i, P_vision_orig in enumerate(test_points):
        # 正向变换
        P_robot = vision_to_robot_coords(P_vision_orig, T_shoulder)
        # 逆向变换
        P_vision_back = R_inv @ (P_robot - T_shoulder)

        print(f"\n  测试点 {i+1}:")
        print(f"    原始视觉坐标: {P_vision_orig}")
        print(f"    机器人坐标: {P_robot}")
        print(f"    逆变换回视觉坐标: {P_vision_back}")
        print(f"    误差: {np.linalg.norm(P_vision_orig - P_vision_back):.6f}")

        assert np.allclose(P_vision_orig, P_vision_back), "往返变换应该恢复原始坐标"
        print("    ✓ 验证通过")


def test_hand_positions():
    """测试3: 实际手部位置测试"""
    print("\n" + "="*80)
    print("测试3: 实际手部位置测试")
    print("="*80)

    mapper = ArmMotionMapper(
        robot_shoulder_pos=[0.0, -0.096, 1.217],
        arm_lengths={'upper': 0.2908, 'fore': 0.2366}
    )

    # 模拟典型手部姿态
    test_poses = [
        {
            "name": "自然下垂",
            "wrist": [0.0, 0.2, -0.5],  # 视觉坐标：右下方
            "elbow": [0.0, 0.15, -0.25],
        },
        {
            "name": "前伸",
            "wrist": [0.0, 0.2, 0.5],  # 视觉坐标：右前方
            "elbow": [0.0, 0.15, 0.25],
        },
        {
            "name": "上举",
            "wrist": [0.5, 0.2, 0.0],  # 视觉坐标：右上方
            "elbow": [0.25, 0.15, 0.0],
        },
    ]

    for pose in test_poses:
        print(f"\n姿态: {pose['name']}")
        print(f"  手腕 (视觉): {pose['wrist']}")
        print(f"  肘部 (视觉): {pose['elbow']}")

        # 构造关键点数据
        human_kps = {
            'wrist': {'x': pose['wrist'][1], 'y': pose['wrist'][0], 'z': pose['wrist'][2]},
            'elbow': {'x': pose['elbow'][1], 'y': pose['elbow'][0], 'z': pose['elbow'][2]},
            'shoulder': {'x': 0.0, 'y': 0.0, 'z': 0.0},
        }

        result = mapper.human_to_robot(human_kps)
        if result is not None:
            target_pos, target_quat, debug_info = result
            print(f"  手腕 (机器人): {target_pos}")
            print(f"  肘部 (机器人): {debug_info.get('elbow_pos', 'N/A')}")

            # 验证合理性
            arm_length = mapper.arm_lengths['upper'] + mapper.arm_lengths['fore']
            dist_from_shoulder = np.linalg.norm(target_pos - mapper.robot_shoulder_pos)
            print(f"  距肩部距离: {dist_from_shoulder:.3f}m (臂长: {arm_length:.3f}m)")

            if dist_from_shoulder > arm_length * 1.2:
                print(f"  ⚠️ 警告: 距离超出臂长范围")
            else:
                print(f"  ✓ 距离合理")
        else:
            print(f"  ❌ 映射失败")


def test_with_real_data():
    """测试4: 使用真实视觉数据测试"""
    print("\n" + "="*80)
    print("测试4: 使用真实视觉数据测试")
    print("="*80)
    print("正在监听 UDP 端口 6001...")
    print("请启动 vision_node 并做出以下动作:")
    print("  1. 手臂自然下垂")
    print("  2. 向前伸手")
    print("  3. 向上举手")
    print("  4. 向右移动手")
    print("\n按 Ctrl+C 停止\n")

    mapper = ArmMotionMapper(
        robot_shoulder_pos=[0.0, -0.096, 1.217],
        arm_lengths={'upper': 0.2908, 'fore': 0.2366}
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 6001))
    sock.settimeout(1.0)

    frame_count = 0
    try:
        while True:
            try:
                data, _ = sock.recvfrom(65536)
                packet = json.loads(data.decode('utf-8'))

                if 'keypoints' in packet:
                    human_kps = packet['keypoints']
                else:
                    human_kps = packet

                if 'wrist' not in human_kps or 'elbow' not in human_kps:
                    continue

                frame_count += 1
                if frame_count % 30 != 0:  # 每30帧显示一次
                    continue

                result = mapper.human_to_robot(human_kps)
                if result is not None:
                    target_pos, target_quat, debug_info = result
                    elbow_pos = debug_info.get('elbow_pos', None)

                    print(f"\n帧 {frame_count}:")
                    print(f"  手腕 (机器人): [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]")
                    if elbow_pos is not None:
                        print(f"  肘部 (机器人): [{elbow_pos[0]:.3f}, {elbow_pos[1]:.3f}, {elbow_pos[2]:.3f}]")

                    # 检查合理性
                    dist = np.linalg.norm(target_pos - mapper.robot_shoulder_pos)
                    arm_length = mapper.arm_lengths['upper'] + mapper.arm_lengths['fore']

                    if dist > arm_length * 1.2:
                        print(f"  ⚠️ 距离异常: {dist:.3f}m > {arm_length*1.2:.3f}m")
                    elif target_pos[2] < 0.5:  # Z坐标过低
                        print(f"  ⚠️ 高度异常: Z={target_pos[2]:.3f}m < 0.5m")
                    elif abs(target_pos[1]) > 0.5:  # Y坐标偏移过大
                        print(f"  ⚠️ 左右偏移异常: Y={target_pos[1]:.3f}m")
                    else:
                        print(f"  ✓ 位置合理 (距离: {dist:.3f}m)")

            except socket.timeout:
                continue

    except KeyboardInterrupt:
        print("\n\n测试结束")
    finally:
        sock.close()


def main():
    print("="*80)
    print("坐标变换综合测试")
    print("="*80)

    # 运行所有测试
    test_basic_transform()
    test_inverse_transform()
    test_hand_positions()

    print("\n" + "="*80)
    print("基础测试完成！")
    print("="*80)

    # 询问是否进行实时测试
    print("\n是否进行实时视觉数据测试？(y/n): ", end='')
    choice = input().strip().lower()
    if choice == 'y':
        test_with_real_data()


if __name__ == "__main__":
    main()
