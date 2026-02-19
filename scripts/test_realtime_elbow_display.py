#!/usr/bin/env python3
"""
测试肘部角度实时显示功能

这个脚本会：
1. 初始化 motion_mapper
2. 模拟不同的手臂姿态
3. 显示计算出的肘部角度信息
"""

import numpy as np
import sys
import os
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper

def test_realtime_display():
    """测试实时显示肘部角度"""

    print("=" * 80)
    print("肘部角度实时显示测试")
    print("=" * 80)

    # 初始化 mapper（禁用滤波以便测试）
    mapper = ArmMotionMapper()
    mapper.enable_filter = False

    # 测试用例：模拟手臂从伸直到弯曲的过程
    print("\n模拟手臂从伸直到弯曲的过程...")
    print("按 Ctrl+C 停止\n")

    try:
        for angle in range(0, 181, 10):
            # 计算小臂位置（在肩部坐标系中）
            # 肩部坐标系：X=up, Y=right, Z=forward
            angle_rad = np.radians(angle)

            # 大臂向下
            elbow = [-0.3, 0, 0]

            # 小臂方向：从向下逐渐转到向前
            # angle=0: 向下 [-0.25, 0, 0]
            # angle=90: 向前 [0, 0, 0.25]
            # angle=180: 向上 [0.25, 0, 0]
            wrist_x = -0.3 + 0.25 * np.sin(angle_rad)
            wrist_z = 0.25 * (1 - np.cos(angle_rad))
            wrist = [wrist_x, 0, wrist_z]

            human_kps = {
                "shoulder": [0, 0, 0],
                "elbow": elbow,
                "wrist": wrist,
                "index_mcp": [wrist[0], 0.05, wrist[2] + 0.05],
                "pinky_mcp": [wrist[0], -0.05, wrist[2] + 0.05],
            }

            # 调用 mapper
            result = mapper.human_to_robot(human_kps)
            if result is None:
                print(f"❌ angle={angle}° 映射失败")
                continue

            _, _, debug_info = result

            # 显示调试信息
            print(f"\r人体肘部角度: {180-angle:3.0f}° | "
                  f"向量夹角: {debug_info['vector_angle']:5.1f}° | "
                  f"电机角度: {debug_info['elbow_angle_motor']:5.1f}°",
                  end="", flush=True)

            time.sleep(0.2)

        print("\n\n测试完成！")

    except KeyboardInterrupt:
        print("\n\n测试中断")

if __name__ == "__main__":
    test_realtime_display()