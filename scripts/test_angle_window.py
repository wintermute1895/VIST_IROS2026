#!/usr/bin/env python3
"""
测试角度显示窗口
"""

import sys
import os
import time
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.utils.angle_display_window import get_angle_window

def test_window():
    """测试角度显示窗口"""

    print("=" * 60)
    print("角度显示窗口测试")
    print("=" * 60)
    print("\n启动窗口...")

    # 获取窗口实例
    window = get_angle_window()
    window.start()

    print("窗口已启动！")
    print("模拟角度变化...")
    print("按 Ctrl+C 停止\n")

    try:
        # 模拟角度从0到180度变化
        angle = 0
        direction = 1

        while True:
            # 更新角度
            angle += direction * 2
            if angle >= 180:
                angle = 180
                direction = -1
            elif angle <= 0:
                angle = 0
                direction = 1

            # 计算相关角度
            vector_angle = 180 - angle  # 向量夹角
            human_angle = angle  # 人体肘部角度
            motor_angle = vector_angle  # 电机角度
            q4_raw = np.radians(motor_angle)  # 弧度

            # 更新窗口
            debug_info = {
                'vector_angle': vector_angle,
                'elbow_angle_human': human_angle,
                'elbow_angle_motor': motor_angle,
                'q4_raw': q4_raw,
            }
            window.update(debug_info)

            # 同时在终端显示
            print(f"\r人体肘部角度: {human_angle:3.0f}° | "
                  f"向量夹角: {vector_angle:3.0f}° | "
                  f"电机角度: {motor_angle:3.0f}°",
                  end="", flush=True)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\n测试中断")
        window.stop()

if __name__ == "__main__":
    test_window()