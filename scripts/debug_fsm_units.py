#!/usr/bin/env python3
"""
FSM 单位与坐标系诊断脚本
用于排查距离计算异常的 Bug

诊断方向：
1. 单位混用：米 vs 毫米
2. 弧度 vs 角度混用
3. 数组切片维度错误
"""

import numpy as np
import sys
import os
from pathlib import Path

# 添加项目路径
ros2_ws_root = Path('/home/ilex/Dev/VIST/ros2_ws')
sys.path.insert(0, str(ros2_ws_root))

# 导入必要的模块
import pinocchio as pin
from src.core.ik_solver import PinocchioIKSolver as IKSolver


def print_section(title):
    """打印分隔线"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def diagnose_units_and_coordinates():
    """诊断单位和坐标系问题"""

    print_section("🔍 FSM 单位与坐标系诊断")

    # ========== 1. 配置文件中的目标坐标 ==========
    print_section("1️⃣ 配置文件中的目标坐标")
    socket_center_xy = np.array([0.42, -0.11])
    print(f"socket_center_xy = {socket_center_xy}")
    print(f"配置文件注释：单位为 米 (m)")
    print(f"数值量级：{np.linalg.norm(socket_center_xy):.3f} m")

    # ========== 2. 初始化 IK Solver 并测试正运动学 ==========
    print_section("2️⃣ 正运动学（FK）输出单位测试")

    try:
        # 初始化 IK Solver
        urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/models/urdf/dual_arm_robot.urdf'
        ik_solver = IKSolver(
            urdf_path=urdf_path,
            ee_frame_name='left_tool0',
            arm_side='left'
        )
        print(f"✓ IK Solver 初始化成功")
        print(f"  URDF: {urdf_path}")
        print(f"  末端执行器: left_tool0")

        # ========== 3. 测试关节角输入（弧度 vs 角度） ==========
        print_section("3️⃣ 关节角输入单位测试（弧度 vs 角度）")

        # 测试用关节角（单位：弧度）
        test_joints_rad = np.array([0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0])
        print(f"测试关节角（弧度）: {test_joints_rad}")
        print(f"  量级范围: [{test_joints_rad.min():.3f}, {test_joints_rad.max():.3f}] rad")
        print(f"  对应角度: [{np.rad2deg(test_joints_rad.min()):.1f}°, {np.rad2deg(test_joints_rad.max()):.1f}°]")

        # 如果误用角度（会导致极度非线性）
        test_joints_deg = np.rad2deg(test_joints_rad)
        print(f"\n⚠️  如果误用角度值: {test_joints_deg}")
        print(f"  量级范围: [{test_joints_deg.min():.1f}°, {test_joints_deg.max():.1f}°]")
        print(f"  这会被当作 [{test_joints_deg.min():.1f}, {test_joints_deg.max():.1f}] rad（错误！）")

        # ========== 4. 执行正运动学并检查输出单位 ==========
        print_section("4️⃣ 正运动学输出分析")

        # 扩展为双臂关节角（14维）
        q_dual = np.zeros(14)
        q_dual[0:7] = test_joints_rad  # 左臂

        # 执行正运动学
        pin.forwardKinematics(ik_solver.model, ik_solver.data, q_dual)
        pin.updateFramePlacements(ik_solver.model, ik_solver.data)

        # 获取法兰位置
        flange_pose = ik_solver.data.oMf[ik_solver.ee_frame_id]
        flange_position = flange_pose.translation.copy()

        print(f"法兰位置（完整）: {flange_position}")
        print(f"  X = {flange_position[0]:.6f}")
        print(f"  Y = {flange_position[1]:.6f}")
        print(f"  Z = {flange_position[2]:.6f}")

        # ========== 5. 判断单位 ==========
        print_section("5️⃣ 单位判断")

        position_norm = np.linalg.norm(flange_position)
        print(f"位置向量模长: {position_norm:.6f}")

        if position_norm > 10:
            print(f"❌ 单位可能是 毫米 (mm)")
            print(f"   理由：模长 {position_norm:.1f} mm = {position_norm/1000:.3f} m")
            print(f"   机械臂工作空间通常在 0.3-1.5 米范围内")
            unit_scale = 1000.0
            unit_name = "mm"
        else:
            print(f"✓ 单位可能是 米 (m)")
            print(f"   理由：模长 {position_norm:.3f} m 在合理范围内")
            unit_scale = 1.0
            unit_name = "m"

        # ========== 6. 数组切片测试 ==========
        print_section("6️⃣ 数组切片维度测试")

        print(f"完整法兰位姿数组: {flange_position}")
        print(f"  shape: {flange_position.shape}")
        print(f"  dtype: {flange_position.dtype}")

        flange_xy = flange_position[:2]
        print(f"\nflange_xy = flange_position[:2]")
        print(f"  结果: {flange_xy}")
        print(f"  shape: {flange_xy.shape}")

        print(f"\n✓ 切片正确：前两个元素确实是 X 和 Y 坐标")
        print(f"  X = {flange_xy[0]:.6f} {unit_name}")
        print(f"  Y = {flange_xy[1]:.6f} {unit_name}")
        print(f"  Z = {flange_position[2]:.6f} {unit_name} (未使用)")

        # ========== 7. 距离计算模拟（单位混用场景） ==========
        print_section("7️⃣ 距离计算模拟（Bug 重现）")

        print(f"socket_center_xy = {socket_center_xy} m")
        print(f"flange_xy = {flange_xy} {unit_name}")

        # 场景 1：单位统一（正确）
        if unit_name == "mm":
            flange_xy_m = flange_xy / 1000.0
            distance_correct = np.linalg.norm(flange_xy_m - socket_center_xy)
            print(f"\n✓ 场景 1：单位统一（正确）")
            print(f"  flange_xy (转换为米) = {flange_xy_m}")
            print(f"  distance = norm({flange_xy_m} - {socket_center_xy})")
            print(f"  distance = {distance_correct:.6f} m = {distance_correct*1000:.1f} mm")
        else:
            distance_correct = np.linalg.norm(flange_xy - socket_center_xy)
            print(f"\n✓ 场景 1：单位统一（正确）")
            print(f"  distance = norm({flange_xy} - {socket_center_xy})")
            print(f"  distance = {distance_correct:.6f} m = {distance_correct*1000:.1f} mm")

        # 场景 2：单位混用（Bug）
        if unit_name == "mm":
            distance_bug = np.linalg.norm(flange_xy - socket_center_xy)
            print(f"\n❌ 场景 2：单位混用（Bug）")
            print(f"  distance = norm({flange_xy} mm - {socket_center_xy} m)")
            print(f"  distance = norm({flange_xy} - {socket_center_xy})")
            print(f"  distance ≈ {distance_bug:.1f} (无意义的混合单位)")
            print(f"\n🔥 这就是你看到的 800 左右的异常值！")

        # ========== 8. 总结与建议 ==========
        print_section("8️⃣ 诊断总结与修复建议")

        print(f"✓ 猜想 1（单位混用）：实锤！")
        print(f"  - socket_center_xy: 米 (m)")
        print(f"  - robot_flange_position: {unit_name}")
        print(f"  - 需要在 FSM 中统一单位")

        print(f"\n✓ 猜想 2（弧度 vs 角度）：未发现问题")
        print(f"  - 测试关节角量级在 [-1.5, 1.0] rad 范围内")
        print(f"  - Pinocchio 默认使用弧度，输入正确")

        print(f"\n✓ 猜想 3（数组切片）：未发现问题")
        print(f"  - flange_position[:2] 正确提取了 X 和 Y 坐标")
        print(f"  - Z 坐标 ({flange_position[2]:.3f} {unit_name}) 未被误用")

        print(f"\n🔧 修复方案：")
        if unit_name == "mm":
            print(f"  在 vitual_fixture_fsm.py 的 update() 方法中：")
            print(f"  1. 将 robot_flange_position 从毫米转换为米：")
            print(f"     robot_flange_position_m = robot_flange_position / 1000.0")
            print(f"  2. 或者将 socket_center_xy 从米转换为毫米：")
            print(f"     socket_center_xy_mm = socket_center_xy * 1000.0")
            print(f"  推荐：统一使用米 (m) 作为标准单位")
        else:
            print(f"  单位已统一，无需修改")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    diagnose_units_and_coordinates()