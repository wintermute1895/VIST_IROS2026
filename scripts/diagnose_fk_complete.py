#!/usr/bin/env python3
"""
FK 计算完整诊断工具

目的：
1. 验证关节角单位（弧度 vs 角度）
2. 验证关节顺序映射
3. 验证坐标系定义
4. 对比不同 FK 计算方法的结果

使用方法：
    python3 scripts/diagnose_fk_complete.py
"""

import numpy as np
import sys
from pathlib import Path

# 添加项目路径
ros2_ws_root = Path('/home/ilex/Dev/VIST/ros2_ws')
sys.path.insert(0, str(ros2_ws_root))

import pinocchio as pin


def print_section(title):
    """打印分隔线"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def expand_single_arm_to_dual(q_single: np.ndarray, arm_side: str = 'left') -> np.ndarray:
    """将单臂7关节扩展为双臂14关节向量"""
    q_dual = np.zeros(14)
    if arm_side == 'left':
        q_dual[0:7] = q_single
    else:  # right
        q_dual[7:14] = q_single
    return q_dual


def test_fk_with_different_configs():
    """测试不同配置下的 FK 计算"""

    print_section("🔍 FK 计算完整诊断")

    # 加载 URDF
    urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf'
    model = pin.buildModelFromUrdf(urdf_path)
    data = model.createData()

    print(f"\n✓ 已加载 URDF: {urdf_path}")
    print(f"  总关节数: {model.nq}")

    # 测试用的关节角（零位）
    q_test_deg = np.array([0, 0, 0, 0, 0, 0, 0])  # 角度
    q_test_rad = np.deg2rad(q_test_deg)  # 弧度

    # 测试不同的末端执行器
    ee_frames = {
        'Left_Wrist_Roll_Link': None,
        'Left_Wrist_Pitch_Link': None,
        'Left_Wrist_Yaw_Link': None
    }

    # 获取 frame IDs
    for frame_name in ee_frames.keys():
        if model.existFrame(frame_name):
            ee_frames[frame_name] = model.getFrameId(frame_name)

    # ========== 测试 1: 零位时的末端位置 ==========
    print_section("1️⃣ 测试：零位时的末端位置")

    q_dual = expand_single_arm_to_dual(q_test_rad, 'left')
    pin.forwardKinematics(model, data, q_dual)
    pin.updateFramePlacements(model, data)

    print("\n关节角（零位）:")
    print(f"  弧度: {q_test_rad}")
    print(f"  角度: {q_test_deg}")

    print("\n不同末端执行器的位置:")
    for frame_name, frame_id in ee_frames.items():
        if frame_id is not None:
            position = data.oMf[frame_id].translation
            print(f"\n  {frame_name}:")
            print(f"    位置: [{position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f}] m")
            print(f"    模长: {np.linalg.norm(position):.4f} m")
            print(f"    X坐标: {'✓ 正' if position[0] > 0 else '❌ 负'}")

    # ========== 测试 2: 应用 negation 映射 ==========
    print_section("2️⃣ 测试：应用 negation 映射")

    # 遥操配置中的 negation
    negation_left = np.array([1, 1, 1, -1, 1, -1, 1])
    negation_dual = np.concatenate([negation_left, np.ones(7)])

    q_dual_corrected = q_dual * negation_dual
    pin.forwardKinematics(model, data, q_dual_corrected)
    pin.updateFramePlacements(model, data)

    print("\nNegation 映射:")
    print(f"  左臂: {negation_left}")
    print(f"  修正后关节角: {q_dual_corrected[:7]}")

    print("\n应用 negation 后的末端位置:")
    for frame_name, frame_id in ee_frames.items():
        if frame_id is not None:
            position = data.oMf[frame_id].translation
            print(f"\n  {frame_name}:")
            print(f"    位置: [{position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f}] m")
            print(f"    X坐标: {'✓ 正' if position[0] > 0 else '❌ 负'}")

    # ========== 测试 3: 非零位测试 ==========
    print_section("3️⃣ 测试：非零位关节角")

    # 测试一个典型的工作位姿
    q_work_deg = np.array([0, -30, 0, 90, 0, 60, 0])  # 角度
    q_work_rad = np.deg2rad(q_work_deg)  # 弧度

    q_dual_work = expand_single_arm_to_dual(q_work_rad, 'left')
    q_dual_work_corrected = q_dual_work * negation_dual

    pin.forwardKinematics(model, data, q_dual_work_corrected)
    pin.updateFramePlacements(model, data)

    print("\n工作位姿关节角:")
    print(f"  角度: {q_work_deg}")
    print(f"  弧度: {q_work_rad}")

    print("\n工作位姿的末端位置:")
    for frame_name, frame_id in ee_frames.items():
        if frame_id is not None:
            position = data.oMf[frame_id].translation
            print(f"\n  {frame_name}:")
            print(f"    位置: [{position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f}] m")
            print(f"    X坐标: {'✓ 正' if position[0] > 0 else '❌ 负'}")

    # ========== 测试 4: 坐标系验证 ==========
    print_section("4️⃣ 测试：坐标系定义验证")

    print("\nPinocchio 坐标系约定:")
    print("  - X轴: 前方（机器人前进方向）")
    print("  - Y轴: 左侧")
    print("  - Z轴: 上方")
    print("  - 右手坐标系")

    print("\n基座坐标系（universe）:")
    print(f"  位置: {data.oMf[0].translation}")
    print(f"  旋转: {data.oMf[0].rotation}")

    # ========== 测试 5: 关节限位检查 ==========
    print_section("5️⃣ 测试：关节限位")

    print("\n左臂关节限位:")
    joint_names = [
        'Left_Shoulder_Pitch_Joint',
        'Left_Shoulder_Roll_Joint',
        'Left_Shoulder_Yaw_Joint',
        'Left_Elbow_Pitch_Joint',
        'Left_Wrist_Yaw_Joint',
        'Left_Wrist_Pitch_Joint',
        'Left_Wrist_Roll_Joint'
    ]

    for i, name in enumerate(joint_names):
        if model.existJointName(name):
            joint_id = model.getJointId(name)
            q_min = model.lowerPositionLimit[i]
            q_max = model.upperPositionLimit[i]
            print(f"  {i+1}. {name}:")
            print(f"     范围: [{np.rad2deg(q_min):.1f}°, {np.rad2deg(q_max):.1f}°]")

    # ========== 分析与建议 ==========
    print_section("📊 分析与建议")

    print("\n🔍 关键检查点:")
    print("  1. 关节角单位: 确认输入是弧度（rad）而非角度（°）")
    print("  2. 关节顺序: 确认控制指令顺序与 URDF 一致")
    print("  3. Negation 映射: 确认方向修正是否正确")
    print("  4. 末端执行器: 确认使用正确的 frame")
    print("  5. 坐标系: 确认 Pinocchio 坐标系与预期一致")

    print("\n💡 常见问题:")
    print("  - 如果 X 坐标为负: 可能是关节方向或 negation 映射错误")
    print("  - 如果 Z 坐标异常: 可能是关节角单位错误（角度 vs 弧度）")
    print("  - 如果距离值很大: 可能是单位混用（米 vs 毫米）")

    print("\n🚀 下一步:")
    print("  1. 对比上述结果与实际机械臂位置")
    print("  2. 确认哪个末端执行器的结果最接近实际")
    print("  3. 调整 negation 映射或 URDF 关节方向")
    print("  4. 更新配置文件中的末端执行器名称")


if __name__ == '__main__':
    try:
        test_fk_with_different_configs()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
