#!/usr/bin/env python3
"""
完整的肘部角度计算调试脚本

展示从视觉数据到机械臂角度的每一步计算过程
"""
import numpy as np
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config

def calculate_human_elbow_angle(shoulder, elbow, wrist):
    """
    计算人体肘部角度（视觉坐标系）

    Args:
        shoulder: 肩部位置 [x, y, z] (视觉坐标系)
        elbow: 肘部位置 [x, y, z] (视觉坐标系)
        wrist: 腕部位置 [x, y, z] (视觉坐标系)

    Returns:
        angle_deg: 人体肘部角度（度）
    """
    print("\n" + "="*60)
    print("步骤1: 计算人体肘部角度（视觉坐标系）")
    print("="*60)

    print(f"输入坐标（视觉坐标系）:")
    print(f"  肩部: {shoulder}")
    print(f"  肘部: {elbow}")
    print(f"  腕部: {wrist}")

    # 计算向量
    v_shoulder_elbow = elbow - shoulder
    v_elbow_wrist = wrist - elbow

    print(f"\n向量计算:")
    print(f"  肩→肘向量: {v_shoulder_elbow}")
    print(f"  肘→腕向量: {v_elbow_wrist}")

    # 计算向量长度
    len_upper = np.linalg.norm(v_shoulder_elbow)
    len_forearm = np.linalg.norm(v_elbow_wrist)

    print(f"\n向量长度:")
    print(f"  上臂长度: {len_upper:.4f}m")
    print(f"  前臂长度: {len_forearm:.4f}m")

    # 计算向量夹角
    cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (len_upper * len_forearm)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    print(f"\n夹角计算:")
    print(f"  点积: {np.dot(v_shoulder_elbow, v_elbow_wrist):.6f}")
    print(f"  cos(θ): {cos_angle:.6f}")

    # 向量夹角
    vector_angle_rad = np.arccos(cos_angle)
    vector_angle_deg = np.degrees(vector_angle_rad)

    print(f"  向量夹角: {vector_angle_deg:.2f}°")

    # 人体肘部角度（补角）
    human_elbow_angle = 180 - vector_angle_deg

    print(f"\n人体肘部角度:")
    print(f"  肘部弯曲角度 = 180° - 向量夹角")
    print(f"  肘部弯曲角度 = 180° - {vector_angle_deg:.2f}°")
    print(f"  肘部弯曲角度 = {human_elbow_angle:.2f}°")

    return human_elbow_angle, vector_angle_rad

def transform_to_robot_frame(shoulder_vis, elbow_vis, wrist_vis, config):
    """
    坐标系转换：视觉坐标系 → 机器人坐标系

    视觉坐标系（肩部为原点）:
      X: 上（头顶方向）
      Y: 右（右手方向）
      Z: 前（前方）

    机器人坐标系（机器人基座为原点）:
      X: 前（前方）
      Y: 左（左手方向）
      Z: 上（天空方向）

    转换关系:
      X_robot = Z_vision
      Y_robot = -Y_vision
      Z_robot = X_vision
    """
    print("\n" + "="*60)
    print("步骤2: 坐标系转换（视觉 → 机器人）")
    print("="*60)

    print(f"视觉坐标系定义（肩部为原点）:")
    print(f"  X: 上（头顶方向）")
    print(f"  Y: 右（右手方向）")
    print(f"  Z: 前（前方）")

    print(f"\n机器人坐标系定义（基座为原点）:")
    print(f"  X: 前（前方）")
    print(f"  Y: 左（左手方向）")
    print(f"  Z: 上（天空方向）")

    # 机器人肩部位置（配置中的固定值）
    robot_shoulder_pos = config.robot_shoulder_position

    print(f"\n机器人肩部位置（机器人坐标系）: {robot_shoulder_pos}")

    # 转换公式
    def vision_to_robot(pos_vis):
        """视觉坐标系 → 机器人坐标系"""
        pos_robot = np.array([
            pos_vis[2],   # X_robot = Z_vision (前)
            -pos_vis[1],  # Y_robot = -Y_vision (左)
            pos_vis[0]    # Z_robot = X_vision (上)
        ])
        # 加上机器人肩部偏移
        pos_robot += robot_shoulder_pos
        return pos_robot

    shoulder_robot = vision_to_robot(shoulder_vis)
    elbow_robot = vision_to_robot(elbow_vis)
    wrist_robot = vision_to_robot(wrist_vis)

    print(f"\n转换结果（机器人坐标系）:")
    print(f"  肩部: {shoulder_robot}")
    print(f"  肘部: {elbow_robot}")
    print(f"  腕部: {wrist_robot}")

    return shoulder_robot, elbow_robot, wrist_robot

def calculate_robot_elbow_angle(shoulder_robot, elbow_robot, wrist_robot):
    """
    计算机器人肘部关节角度（几何求解器的方法）
    """
    print("\n" + "="*60)
    print("步骤3: 计算机器人肘部关节角度")
    print("="*60)

    # 计算向量
    v_shoulder_elbow = elbow_robot - shoulder_robot
    v_elbow_wrist = wrist_robot - elbow_robot

    print(f"向量计算（机器人坐标系）:")
    print(f"  肩→肘向量: {v_shoulder_elbow}")
    print(f"  肘→腕向量: {v_elbow_wrist}")

    # 计算向量长度
    r1 = np.linalg.norm(v_shoulder_elbow)
    r2 = np.linalg.norm(v_elbow_wrist)

    print(f"\n向量长度:")
    print(f"  上臂长度: {r1:.4f}m")
    print(f"  前臂长度: {r2:.4f}m")

    # 计算向量夹角
    cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (r1 * r2)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    print(f"\n夹角计算:")
    print(f"  点积: {np.dot(v_shoulder_elbow, v_elbow_wrist):.6f}")
    print(f"  cos(θ): {cos_angle:.6f}")

    # 向量夹角
    vector_angle_rad = np.arccos(cos_angle)
    vector_angle_deg = np.degrees(vector_angle_rad)

    print(f"  向量夹角: {vector_angle_deg:.2f}°")

    # 方法1: 直接使用向量夹角
    q4_method1_rad = vector_angle_rad
    q4_method1_deg = vector_angle_deg

    # 方法2: 使用补角
    q4_method2_rad = np.pi - vector_angle_rad
    q4_method2_deg = 180 - vector_angle_deg

    print(f"\n机器人关节角度计算:")
    print(f"  方法1（直接使用向量夹角）:")
    print(f"    q4 = arccos(cos_angle)")
    print(f"    q4 = {q4_method1_deg:.2f}° ({q4_method1_rad:.4f} rad)")

    print(f"\n  方法2（使用补角）:")
    print(f"    q4 = π - arccos(cos_angle)")
    print(f"    q4 = 180° - {vector_angle_deg:.2f}°")
    print(f"    q4 = {q4_method2_deg:.2f}° ({q4_method2_rad:.4f} rad)")

    return q4_method1_rad, q4_method2_rad, vector_angle_deg

def apply_joint_direction(q4_rad, config):
    """
    应用关节方向和偏移
    """
    print("\n" + "="*60)
    print("步骤4: 应用关节方向和偏移")
    print("="*60)

    # 读取配置
    joint_directions = config.robot_joint_directions
    joint_offsets = config.robot_joint_offsets

    print(f"配置:")
    print(f"  关节3（肘部）方向: {joint_directions[3]}")
    print(f"  关节3（肘部）偏移: {joint_offsets[3]:.4f} rad ({np.degrees(joint_offsets[3]):.2f}°)")

    # 应用公式: q_final = q_calculated * direction + offset
    q4_final = q4_rad * joint_directions[3] + joint_offsets[3]

    print(f"\n最终关节角度:")
    print(f"  q4_final = q4 * direction + offset")
    print(f"  q4_final = {np.degrees(q4_rad):.2f}° * {joint_directions[3]} + {np.degrees(joint_offsets[3]):.2f}°")
    print(f"  q4_final = {np.degrees(q4_final):.2f}° ({q4_final:.4f} rad)")

    return q4_final

def test_arm_poses():
    """测试不同的手臂姿态"""

    # 加载配置
    config = get_config()

    print("\n" + "="*80)
    print("肘部角度计算完整调试")
    print("="*80)

    # 测试用例（视觉坐标系，肩部为原点）
    test_cases = [
        {
            "name": "小臂自然下垂（肘部约180°）",
            "shoulder": np.array([0.0, 0.0, 0.0]),
            "elbow": np.array([0.0, 0.1, 0.3]),  # 肘部在前下方
            "wrist": np.array([0.0, 0.1, 0.6]),  # 腕部在肘部正下方
        },
        {
            "name": "小臂水平（肘部约90°）",
            "shoulder": np.array([0.0, 0.0, 0.0]),
            "elbow": np.array([0.0, 0.1, 0.3]),  # 肘部在前下方
            "wrist": np.array([-0.3, 0.1, 0.3]),  # 腕部在肘部水平方向
        },
        {
            "name": "小臂向上抬（肘部约45°）",
            "shoulder": np.array([0.0, 0.0, 0.0]),
            "elbow": np.array([0.0, 0.1, 0.3]),  # 肘部在前下方
            "wrist": np.array([-0.21, 0.1, 0.09]),  # 腕部在肘部上方
        },
    ]

    for i, case in enumerate(test_cases):
        print("\n" + "="*80)
        print(f"测试用例 {i+1}: {case['name']}")
        print("="*80)

        shoulder_vis = case['shoulder']
        elbow_vis = case['elbow']
        wrist_vis = case['wrist']

        # 步骤1: 计算人体肘部角度
        human_angle, _ = calculate_human_elbow_angle(shoulder_vis, elbow_vis, wrist_vis)

        # 步骤2: 坐标系转换
        shoulder_robot, elbow_robot, wrist_robot = transform_to_robot_frame(
            shoulder_vis, elbow_vis, wrist_vis, config
        )

        # 步骤3: 计算机器人肘部角度
        q4_method1, q4_method2, vector_angle = calculate_robot_elbow_angle(
            shoulder_robot, elbow_robot, wrist_robot
        )

        # 步骤4: 应用关节方向（方法1）
        print("\n使用方法1（直接使用向量夹角）:")
        q4_final_method1 = apply_joint_direction(q4_method1, config)

        # 步骤4: 应用关节方向（方法2）
        print("\n使用方法2（使用补角）:")
        q4_final_method2 = apply_joint_direction(q4_method2, config)

        # 总结
        print("\n" + "="*60)
        print("总结")
        print("="*60)
        print(f"人体肘部角度: {human_angle:.2f}°")
        print(f"机器人关节角度（方法1）: {np.degrees(q4_final_method1):.2f}°")
        print(f"机器人关节角度（方法2）: {np.degrees(q4_final_method2):.2f}°")

        # 判断哪个方法更接近人体角度
        diff1 = abs(np.degrees(q4_final_method1) - human_angle)
        diff2 = abs(np.degrees(q4_final_method2) - human_angle)

        print(f"\n与人体角度的差异:")
        print(f"  方法1: {diff1:.2f}°")
        print(f"  方法2: {diff2:.2f}°")

        if diff1 < diff2:
            print(f"  ✅ 方法1更接近人体角度")
        else:
            print(f"  ✅ 方法2更接近人体角度")

if __name__ == "__main__":
    test_arm_poses()