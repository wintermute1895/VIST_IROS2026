#!/usr/bin/env python3
"""
URDF坐标系分析工具
分析机器人的坐标系定义和关节位置
"""

import sys
import os
import numpy as np

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pinocchio as pin


def analyze_urdf():
    """分析URDF中的坐标系定义"""

    print("\n" + "="*80)
    print("🔍 URDF 坐标系分析")
    print("="*80)

    urdf_path = os.path.join(project_root, "config", "right_arm_only.urdf")

    # 加载URDF
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    print(f"\n📁 URDF文件: {urdf_path}")
    print(f"   关节数量: {model.nq}")
    print(f"   自由度: {model.nv}")

    # 打印所有frame
    print("\n📐 所有坐标系 (Frames):")
    for i, frame in enumerate(model.frames):
        print(f"   [{i}] {frame.name} (type: {frame.type})")

    # 找到末端执行器
    end_effector_name = "hand_base_link"
    if model.existFrame(end_effector_name):
        ee_frame_id = model.getFrameId(end_effector_name)
        print(f"\n✅ 末端执行器: {end_effector_name} (Frame ID: {ee_frame_id})")
    else:
        print(f"\n❌ 未找到末端执行器: {end_effector_name}")
        return

    # 计算零位姿态下的正运动学
    q_zero = pin.neutral(model)
    print(f"\n🎯 零位姿态 (neutral configuration):")
    print(f"   q = {q_zero}")

    # 正运动学
    pin.forwardKinematics(model, data, q_zero)
    pin.updateFramePlacements(model, data)

    # 获取末端执行器位姿
    ee_placement = data.oMf[ee_frame_id]
    ee_pos = ee_placement.translation
    ee_rot = ee_placement.rotation

    print(f"\n📍 零位姿态下的末端执行器位置 (相对于base_link):")
    print(f"   位置: [{ee_pos[0]:.4f}, {ee_pos[1]:.4f}, {ee_pos[2]:.4f}] (米)")
    print(f"   旋转矩阵:")
    for row in ee_rot:
        print(f"      [{row[0]:7.4f}, {row[1]:7.4f}, {row[2]:7.4f}]")

    # 分析关节位置
    print("\n🔗 关节链分析:")
    print("   从URDF可以看出:")
    print("   - base_link 在原点 [0, 0, 0]")
    print("   - Right_Shoulder_Pitch_Joint 在 [0, -0.15, 0] (相对于base_link)")
    print("   - 后续关节依次连接...")

    print("\n⚠️  关键问题:")
    print("   1. 机器人肩部位置: [0, -0.15, 0] (NOT [0, 0, 0]!)")
    print("   2. IK求解器的参考系: base_link (原点)")
    print("   3. 末端执行器在零位时的位置: 如上所示")

    # 计算臂长
    print("\n📏 估算臂长:")

    # 从URDF读取关节偏移
    # Shoulder Pitch -> Shoulder Roll: z=0.1
    # Shoulder Roll -> Shoulder Yaw: z=0.1
    # Shoulder Yaw -> Elbow: z=0.15
    # Elbow -> Wrist Yaw: z=0.25
    # Wrist Yaw -> Wrist Pitch: z=0.1
    # Wrist Pitch -> Wrist Roll: z=0.08
    # Wrist Roll -> Hand Base: z=0.06

    upper_arm = 0.1 + 0.1 + 0.15  # Shoulder到Elbow
    forearm = 0.25 + 0.1 + 0.08 + 0.06  # Elbow到Hand Base

    print(f"   上臂长度 (Shoulder→Elbow): {upper_arm:.3f}m")
    print(f"   前臂长度 (Elbow→Hand): {forearm:.3f}m")
    print(f"   总臂长: {upper_arm + forearm:.3f}m")

    print("\n" + "="*80)
    print("📋 总结")
    print("="*80)
    print("\n当前代码的问题:")
    print("   ❌ mapper中 robot_shoulder_pos=[0, 0, 0] 是错误的!")
    print("   ✅ 应该是 robot_shoulder_pos=[0, -0.15, 0]")
    print("\n   ❌ 臂长估算可能不准确")
    print(f"   ✅ 应该是 upper={upper_arm:.3f}m, fore={forearm:.3f}m")

    print("\nIK求解器的参考系:")
    print("   ✅ IK求解器求解的是末端执行器相对于 base_link 的位姿")
    print("   ✅ base_link 在原点 [0, 0, 0]")
    print("   ✅ 所以目标位置应该在 base_link 坐标系中表示")

    print("\n坐标变换流程应该是:")
    print("   1. MediaPipe检测 → 人体关键点 (相机坐标系)")
    print("   2. 动态归零 → 相对于人体肩部 (相机坐标系)")
    print("   3. 坐标转换 → 机器人坐标系 (相对于人体肩部)")
    print("   4. 添加机器人肩部偏移 → base_link坐标系")
    print("   5. IK求解 → 关节角度")

    print("\n" + "="*80)


if __name__ == "__main__":
    analyze_urdf()
