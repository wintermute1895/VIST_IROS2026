#!/usr/bin/env python3
"""
简单测试 motion_mapper 的输入输出
"""

import numpy as np
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper

def test_mapper():
    # 禁用滤波器
    mapper = ArmMotionMapper()
    mapper.enable_filter = False  # 禁用滤波

    print("=" * 80)
    print("Motion Mapper 输入输出测试")
    print("=" * 80)
    print(f"机器人上臂长度: {mapper.L_upper:.3f}m")
    print(f"机器人前臂长度: {mapper.L_fore:.3f}m")
    print(f"机器人肩部位置: {mapper.P_base_shoulder}")
    print()

    # 测试：小臂水平向前（90度弯曲）
    # 肩部坐标系：X=up, Y=right, Z=forward
    human_kps = {
        "shoulder": [0, 0, 0],
        "elbow": [-0.3, 0, 0],      # 向下0.3米
        "wrist": [-0.3, 0, 0.25],   # 向下0.3米，向前0.25米
        "index_mcp": [-0.3, 0.05, 0.3],
        "pinky_mcp": [-0.3, -0.05, 0.3],
    }

    print("输入（肩部坐标系）:")
    print(f"  肩部: {human_kps['shoulder']}")
    print(f"  肘部: {human_kps['elbow']}")
    print(f"  腕部: {human_kps['wrist']}")
    print()

    # 计算人体手臂向量（在肩部坐标系中）
    v_upper_human = np.array(human_kps['elbow']) - np.array(human_kps['shoulder'])
    v_fore_human = np.array(human_kps['wrist']) - np.array(human_kps['elbow'])

    print("人体手臂向量（肩部坐标系）:")
    print(f"  大臂: {v_upper_human} (长度: {np.linalg.norm(v_upper_human):.3f}m)")
    print(f"  小臂: {v_fore_human} (长度: {np.linalg.norm(v_fore_human):.3f}m)")
    print()

    # 计算向量夹角
    cos_angle = np.dot(v_upper_human, v_fore_human) / (np.linalg.norm(v_upper_human) * np.linalg.norm(v_fore_human))
    angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
    print(f"人体肘部角度: {180 - angle_deg:.1f}° (向量夹角: {angle_deg:.1f}°)")
    print()

    # 调用 motion_mapper
    result = mapper.human_to_robot(human_kps)
    if result is None:
        print("❌ Motion Mapper 返回 None")
        return

    wrist_pos, wrist_quat, debug_info = result
    elbow_pos = debug_info['elbow_pos']

    print("输出（机器人坐标系）:")
    print(f"  肩部: {mapper.P_base_shoulder}")
    print(f"  肘部: {elbow_pos}")
    print(f"  腕部: {wrist_pos}")
    print()

    # 计算机器人手臂向量
    v_upper_robot = elbow_pos - mapper.P_base_shoulder
    v_fore_robot = wrist_pos - elbow_pos

    print("机器人手臂向量（机器人坐标系）:")
    print(f"  大臂: {v_upper_robot} (长度: {np.linalg.norm(v_upper_robot):.3f}m)")
    print(f"  小臂: {v_fore_robot} (长度: {np.linalg.norm(v_fore_robot):.3f}m)")
    print()

    # 计算向量夹角
    cos_angle_robot = np.dot(v_upper_robot, v_fore_robot) / (np.linalg.norm(v_upper_robot) * np.linalg.norm(v_fore_robot))
    angle_robot_deg = np.degrees(np.arccos(np.clip(cos_angle_robot, -1, 1)))
    print(f"机器人肘部角度: {angle_robot_deg:.1f}° (向量夹角)")
    print(f"对应人体肘部角度: {180 - angle_robot_deg:.1f}°")
    print()

    print("=" * 80)
    print("分析:")
    print("=" * 80)
    print(f"人体肘部角度: {180 - angle_deg:.1f}°")
    print(f"机器人计算的肘部角度: {angle_robot_deg:.1f}°")
    print(f"期望: 人体90° → 机器人90°")
    print()

    if abs(angle_robot_deg - angle_deg) < 1:
        print("✅ 角度映射正确！")
    else:
        print("❌ 角度映射错误！")
        print(f"   差异: {abs(angle_robot_deg - angle_deg):.1f}°")

if __name__ == "__main__":
    test_mapper()