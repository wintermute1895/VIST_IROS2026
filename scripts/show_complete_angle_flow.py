#!/usr/bin/env python3
"""
展示从视觉数据到肘部角度计算的完整流程

这个脚本模拟整个数据流：
1. 视觉节点输出：肩、肘、腕的3D坐标（视觉坐标系）
2. Motion Mapper：坐标转换（视觉坐标系 → 机器人坐标系）
3. 几何求解器：计算肘部角度
"""
import numpy as np
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config

def calculate_vector_angle(v1, v2):
    """
    计算两个向量之间的夹角

    Args:
        v1: 向量1
        v2: 向量2

    Returns:
        angle_rad: 夹角（弧度）
        angle_deg: 夹角（度）
    """
    # 计算向量长度
    len1 = np.linalg.norm(v1)
    len2 = np.linalg.norm(v2)

    # 计算点积
    dot_product = np.dot(v1, v2)

    # 计算cos(θ)
    cos_angle = dot_product / (len1 * len2)

    # 限制在[-1, 1]范围内（防止数值误差）
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    # 计算夹角
    angle_rad = np.arccos(cos_angle)
    angle_deg = np.degrees(angle_rad)

    return angle_rad, angle_deg

def show_complete_flow():
    """展示完整的数据流"""

    config = get_config()

    print("="*80)
    print("从视觉数据到肘部角度计算的完整流程")
    print("="*80)

    # 模拟视觉节点输出（视觉坐标系，肩部为原点）
    print("\n" + "="*80)
    print("步骤1: 视觉节点输出（视觉坐标系）")
    print("="*80)

    # 视觉坐标系定义：
    # X: 上（头顶方向）
    # Y: 右（右手方向）
    # Z: 前（前方）

    # 示例：小臂水平
    shoulder_vis = np.array([0.0, 0.0, 0.0])  # 肩部（原点）
    elbow_vis = np.array([0.0, 0.1, 0.3])     # 肘部（前下方）
    wrist_vis = np.array([-0.3, 0.1, 0.3])    # 腕部（肘部左侧）

    print(f"视觉坐标系定义:")
    print(f"  X: 上（头顶方向）")
    print(f"  Y: 右（右手方向）")
    print(f"  Z: 前（前方）")

    print(f"\n关键点坐标（视觉坐标系）:")
    print(f"  肩部: {shoulder_vis}")
    print(f"  肘部: {elbow_vis}")
    print(f"  腕部: {wrist_vis}")

    # 计算向量
    v_shoulder_elbow_vis = elbow_vis - shoulder_vis
    v_elbow_wrist_vis = wrist_vis - elbow_vis

    print(f"\n向量计算:")
    print(f"  肩→肘向量: {v_shoulder_elbow_vis}")
    print(f"  肘→腕向量: {v_elbow_wrist_vis}")

    # 计算夹角（视觉坐标系）
    angle_rad_vis, angle_deg_vis = calculate_vector_angle(
        v_shoulder_elbow_vis, v_elbow_wrist_vis
    )

    print(f"\n向量夹角（视觉坐标系）:")
    print(f"  夹角 = arccos(v1·v2 / (|v1|·|v2|))")
    print(f"  夹角 = {angle_deg_vis:.2f}°")

    # 人体肘部角度（补角）
    human_elbow_angle = 180 - angle_deg_vis

    print(f"\n人体肘部角度:")
    print(f"  肘部弯曲角度 = 180° - 向量夹角")
    print(f"  肘部弯曲角度 = {human_elbow_angle:.2f}°")

    # 步骤2: 坐标转换
    print("\n" + "="*80)
    print("步骤2: Motion Mapper坐标转换")
    print("="*80)

    print(f"转换关系:")
    print(f"  X_robot = Z_vision  (前)")
    print(f"  Y_robot = -Y_vision (左)")
    print(f"  Z_robot = X_vision  (上)")

    # 机器人肩部位置
    robot_shoulder_pos = config.robot_shoulder_position

    def vision_to_robot(pos_vis):
        """视觉坐标系 → 机器人坐标系"""
        pos_robot = np.array([
            pos_vis[2],   # X_robot = Z_vision
            -pos_vis[1],  # Y_robot = -Y_vision
            pos_vis[0]    # Z_robot = X_vision
        ])
        pos_robot += robot_shoulder_pos
        return pos_robot

    shoulder_robot = vision_to_robot(shoulder_vis)
    elbow_robot = vision_to_robot(elbow_vis)
    wrist_robot = vision_to_robot(wrist_vis)

    print(f"\n转换后坐标（机器人坐标系）:")
    print(f"  肩部: {shoulder_robot}")
    print(f"  肘部: {elbow_robot}")
    print(f"  腕部: {wrist_robot}")

    # 计算向量（机器人坐标系）
    v_shoulder_elbow_robot = elbow_robot - shoulder_robot
    v_elbow_wrist_robot = wrist_robot - elbow_robot

    print(f"\n向量计算（机器人坐标系）:")
    print(f"  肩→肘向量: {v_shoulder_elbow_robot}")
    print(f"  肘→腕向量: {v_elbow_wrist_robot}")

    # 计算夹角（机器人坐标系）
    angle_rad_robot, angle_deg_robot = calculate_vector_angle(
        v_shoulder_elbow_robot, v_elbow_wrist_robot
    )

    print(f"\n向量夹角（机器人坐标系）:")
    print(f"  夹角 = {angle_deg_robot:.2f}°")

    # 步骤3: 几何求解器计算关节角度
    print("\n" + "="*80)
    print("步骤3: 几何求解器计算关节角度")
    print("="*80)

    print(f"当前代码中的计算:")
    print(f"  q4 = π - arccos(cos_angle)")
    print(f"  q4 = π - {angle_rad_robot:.4f}")
    q4_current = np.pi - angle_rad_robot
    print(f"  q4 = {q4_current:.4f} rad = {np.degrees(q4_current):.2f}°")

    # 应用关节方向
    joint_direction = config.robot_joint_directions[3]
    joint_offset = config.robot_joint_offsets[3]

    print(f"\n应用关节方向和偏移:")
    print(f"  关节方向: {joint_direction}")
    print(f"  关节偏移: {joint_offset:.4f} rad = {np.degrees(joint_offset):.2f}°")

    q4_final = q4_current * joint_direction + joint_offset

    print(f"\n最终关节角度:")
    print(f"  q4_final = q4 * direction + offset")
    print(f"  q4_final = {np.degrees(q4_current):.2f}° * {joint_direction} + {np.degrees(joint_offset):.2f}°")
    print(f"  q4_final = {np.degrees(q4_final):.2f}° ({q4_final:.4f} rad)")

    # 检查是否在限位内
    in_limit = -2.2 <= q4_final <= 2.2
    print(f"\n关节限位检查:")
    print(f"  URDF限位: [-2.2, 2.2] rad = [-126°, 126°]")
    print(f"  当前角度: {q4_final:.4f} rad = {np.degrees(q4_final):.2f}°")
    print(f"  在限位内: {'✅ 是' if in_limit else '❌ 否'}")

    # 总结
    print("\n" + "="*80)
    print("总结")
    print("="*80)
    print(f"人体肘部角度: {human_elbow_angle:.2f}°")
    print(f"机器人关节角度: {np.degrees(q4_final):.2f}°")
    print(f"差异: {abs(human_elbow_angle - np.degrees(q4_final)):.2f}°")

    # 关键公式
    print("\n" + "="*80)
    print("关键公式总结")
    print("="*80)
    print(f"\n1. 向量夹角计算:")
    print(f"   angle = arccos(v1·v2 / (|v1|·|v2|))")
    print(f"   其中 v1 = 肩→肘向量, v2 = 肘→腕向量")

    print(f"\n2. 人体肘部角度:")
    print(f"   human_angle = 180° - vector_angle")
    print(f"   （因为人体肘部角度是补角）")

    print(f"\n3. 机器人关节角度（当前实现）:")
    print(f"   q4 = π - arccos(cos_angle)")
    print(f"   q4_final = q4 * direction + offset")

    print(f"\n4. 注意事项:")
    print(f"   - 向量夹角永远是正的（0° ~ 180°）")
    print(f"   - 人体肘部角度也永远是正的（0° ~ 180°）")
    print(f"   - 机器人关节角度可以是负的（取决于URDF定义）")
    print(f"   - 需要确保最终角度在URDF限位内")

if __name__ == "__main__":
    show_complete_flow()