#!/usr/bin/env python3
"""
测试VIST卡尔曼滤波器是否真正工作
验证输入和输出是否有差异
"""

import sys
import os

# 添加正确的路径
project_root = os.path.dirname(os.path.abspath(__file__))
ros2_ws_src = os.path.join(project_root, 'ros2_ws', 'src')
sys.path.insert(0, ros2_ws_src)

import numpy as np
from config.config_loader import get_config
from core.ik_solver import PinocchioIKSolver
from core.vist_kalman_filter import VISTKalmanFilter

def main():
    print("=" * 60)
    print("VIST卡尔曼滤波器功能测试")
    print("=" * 60)

    # 加载配置（显式指定路径）
    config_path = os.path.join(project_root, 'config', 'system_config.yaml')
    config = get_config(config_path)
    print("✅ 配置加载完成")

    # 初始化IK求解器（使用默认参数）
    ik_solver = PinocchioIKSolver()
    print("✅ IK求解器初始化完成")

    # 初始化VIST滤波器
    vist_filter = VISTKalmanFilter(ik_solver, config)
    print("✅ VIST滤波器初始化完成\n")

    # 测试数据：模拟带噪声的关节角度输入
    print("测试场景：输入带噪声的关节角度，观察滤波效果")
    print("-" * 60)

    # 基准关节角度
    base_joints = np.array([0.0, 0.5, -0.5, 1.0, 0.0, 0.5, 0.0])

    # 目标位姿（固定）
    target_pose = np.array([0.5, 0.0, 0.3, 0.0, 0.0, 0.0, 1.0])

    print(f"基准关节角度: {base_joints}")
    print(f"目标位姿: {target_pose[:3]} (XYZ)\n")

    # 运行10次迭代
    for i in range(10):
        # 添加随机噪声（模拟真实传感器噪声）
        noise = np.random.normal(0, 0.01, 7)  # 标准差0.01弧度
        noisy_joints = base_joints + noise

        # 通过VIST滤波
        filtered_joints = vist_filter.update(
            shadow_joints=noisy_joints,
            target_pose=target_pose,
            virtual_joints=None
        )

        # 计算差异
        input_noise_norm = np.linalg.norm(noise)
        output_diff_norm = np.linalg.norm(filtered_joints - base_joints)
        filtering_effect = np.linalg.norm(filtered_joints - noisy_joints)

        print(f"迭代 {i+1}:")
        print(f"  输入噪声范数: {input_noise_norm:.6f} rad")
        print(f"  输出偏差范数: {output_diff_norm:.6f} rad")
        print(f"  滤波效果: {filtering_effect:.6f} rad")
        print(f"  噪声抑制率: {(1 - output_diff_norm/input_noise_norm)*100:.2f}%")
        print()

    print("=" * 60)
    print("测试完成！")
    print("如果'滤波效果'不为0，说明卡尔曼滤波器正在工作")
    print("如果'噪声抑制率'为正，说明滤波器有效降低了噪声")
    print("=" * 60)

if __name__ == "__main__":
    main()