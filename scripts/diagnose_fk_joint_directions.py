#!/usr/bin/env python3
"""
正运动学关节方向诊断工具

目的：
1. 逐个关节测试正运动学的方向是否符合预期
2. 自动生成关节方向修正映射
3. 可视化每个关节对末端位置的影响

使用方法：
    python3 scripts/diagnose_fk_joint_directions.py

作者: VIST Team
日期: 2026-03-01
"""

import numpy as np
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 添加项目路径
ros2_ws_root = Path('/home/ilex/Dev/VIST/ros2_ws')
sys.path.insert(0, str(ros2_ws_root))

import pinocchio as pin
from src.core.ik_solver import PinocchioIKSolver as IKSolver


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


def test_joint_direction(ik_solver, joint_idx, delta_angle=np.deg2rad(45), arm_side='left', negation=None):
    """
    测试单个关节的正运动学方向

    Args:
        ik_solver: IK求解器实例
        joint_idx: 关节索引 (0-6)
        delta_angle: 测试角度增量（弧度）
        arm_side: 机械臂侧 ('left' 或 'right')
        negation: 关节方向映射 [7] 或 [14]，None 表示全为 1

    Returns:
        dict: 包含测试结果的字典
    """
    # 初始关节角（全零位置）
    q_zero = np.zeros(7)

    # 正向扰动
    q_pos = q_zero.copy()
    q_pos[joint_idx] = delta_angle

    # 负向扰动
    q_neg = q_zero.copy()
    q_neg[joint_idx] = -delta_angle

    # 扩展为双臂
    q_zero_dual = expand_single_arm_to_dual(q_zero, arm_side)
    q_pos_dual = expand_single_arm_to_dual(q_pos, arm_side)
    q_neg_dual = expand_single_arm_to_dual(q_neg, arm_side)

    # 应用 negation 映射（如果提供）
    if negation is not None:
        if len(negation) == 7:
            # 扩展为双臂
            negation_dual = np.concatenate([negation, np.ones(7)]) if arm_side == 'left' else np.concatenate([np.ones(7), negation])
        else:
            negation_dual = negation

        q_zero_dual = q_zero_dual * negation_dual
        q_pos_dual = q_pos_dual * negation_dual
        q_neg_dual = q_neg_dual * negation_dual

    # 计算正运动学
    pin.forwardKinematics(ik_solver.model, ik_solver.data, q_zero_dual)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)
    pos_zero = ik_solver.data.oMf[ik_solver.ee_frame_id].translation.copy()

    pin.forwardKinematics(ik_solver.model, ik_solver.data, q_pos_dual)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)
    pos_pos = ik_solver.data.oMf[ik_solver.ee_frame_id].translation.copy()

    pin.forwardKinematics(ik_solver.model, ik_solver.data, q_neg_dual)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)
    pos_neg = ik_solver.data.oMf[ik_solver.ee_frame_id].translation.copy()

    # 计算位移
    delta_pos = pos_pos - pos_zero
    delta_neg = pos_neg - pos_zero

    # 分析运动方向
    result = {
        'joint_idx': joint_idx,
        'delta_angle_deg': np.rad2deg(delta_angle),
        'pos_zero': pos_zero,
        'pos_pos': pos_pos,
        'pos_neg': pos_neg,
        'delta_pos': delta_pos,
        'delta_neg': delta_neg,
        'delta_pos_norm': np.linalg.norm(delta_pos),
        'delta_neg_norm': np.linalg.norm(delta_neg),
        'is_symmetric': np.allclose(delta_pos, -delta_neg, atol=1e-3)
    }

    return result


def analyze_joint_motion(result):
    """
    分析关节运动特性

    Args:
        result: test_joint_direction 返回的结果字典

    Returns:
        str: 分析报告
    """
    joint_idx = result['joint_idx']
    delta_pos = result['delta_pos']
    delta_neg = result['delta_neg']

    # 判断主要运动方向
    abs_delta = np.abs(delta_pos)
    dominant_axis = np.argmax(abs_delta)
    axis_names = ['X', 'Y', 'Z']
    dominant_axis_name = axis_names[dominant_axis]

    # 判断运动类型
    if result['delta_pos_norm'] < 1e-6:
        motion_type = "⚠️  无运动（可能是固定关节或奇异位置）"
    elif result['is_symmetric']:
        motion_type = f"✓ 对称运动（主要沿 {dominant_axis_name} 轴）"
    else:
        motion_type = f"⚠️  非对称运动（可能存在耦合）"

    # 生成报告
    report = f"""
关节 {joint_idx + 1} 运动分析:
  运动类型: {motion_type}
  正向位移: [{delta_pos[0]:+.4f}, {delta_pos[1]:+.4f}, {delta_pos[2]:+.4f}] m
  负向位移: [{delta_neg[0]:+.4f}, {delta_neg[1]:+.4f}, {delta_neg[2]:+.4f}] m
  位移模长: {result['delta_pos_norm']:.4f} m
  主要运动轴: {dominant_axis_name} ({abs_delta[dominant_axis]:.4f} m)
"""

    return report


def visualize_joint_motions(results, arm_side='left'):
    """
    可视化所有关节的运动方向

    Args:
        results: 所有关节的测试结果列表
        arm_side: 机械臂侧
    """
    fig = plt.figure(figsize=(15, 10))

    # 3D 可视化
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    ax1.set_title(f'{arm_side.capitalize()} Arm - Joint Motions (3D)')
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')

    colors = plt.cm.rainbow(np.linspace(0, 1, 7))

    for i, result in enumerate(results):
        pos_zero = result['pos_zero']
        delta_pos = result['delta_pos']

        # 绘制箭头（从零位到正向扰动位置）
        ax1.quiver(pos_zero[0], pos_zero[1], pos_zero[2],
                   delta_pos[0], delta_pos[1], delta_pos[2],
                   color=colors[i], arrow_length_ratio=0.3,
                   label=f'Joint {i+1}', linewidth=2)

    ax1.legend()
    ax1.grid(True)

    # XY 平面投影
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.set_title('XY Plane Projection')
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.grid(True)
    ax2.axis('equal')

    for i, result in enumerate(results):
        pos_zero = result['pos_zero']
        delta_pos = result['delta_pos']
        ax2.arrow(pos_zero[0], pos_zero[1], delta_pos[0], delta_pos[1],
                  head_width=0.02, head_length=0.03, fc=colors[i], ec=colors[i],
                  label=f'Joint {i+1}')

    ax2.legend()

    # XZ 平面投影
    ax3 = fig.add_subplot(2, 2, 3)
    ax3.set_title('XZ Plane Projection')
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Z (m)')
    ax3.grid(True)
    ax3.axis('equal')

    for i, result in enumerate(results):
        pos_zero = result['pos_zero']
        delta_pos = result['delta_pos']
        ax3.arrow(pos_zero[0], pos_zero[2], delta_pos[0], delta_pos[2],
                  head_width=0.02, head_length=0.03, fc=colors[i], ec=colors[i],
                  label=f'Joint {i+1}')

    ax3.legend()

    # 位移模长柱状图
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.set_title('Joint Motion Magnitude')
    ax4.set_xlabel('Joint Index')
    ax4.set_ylabel('Displacement (m)')
    ax4.grid(True, axis='y')

    joint_indices = [r['joint_idx'] + 1 for r in results]
    magnitudes = [r['delta_pos_norm'] for r in results]
    ax4.bar(joint_indices, magnitudes, color=colors)

    plt.tight_layout()
    plt.savefig('/home/ilex/Dev/VIST/data/fk_joint_directions_diagnosis.png', dpi=150)
    print(f"\n📊 可视化结果已保存到: /home/ilex/Dev/VIST/data/fk_joint_directions_diagnosis.png")
    plt.show()


def suggest_negation_mapping(results, expected_directions=None):
    """
    根据测试结果建议关节方向映射

    Args:
        results: 所有关节的测试结果列表
        expected_directions: 期望的运动方向（可选）

    Returns:
        np.ndarray: 建议的 negation 映射
    """
    print_section("🔧 关节方向映射建议")

    print("\n基于测试结果，建议的关节方向映射：")
    print("（注意：这只是基于运动对称性的初步建议，需要结合实际机械臂行为验证）\n")

    negation = np.ones(7)

    for result in results:
        joint_idx = result['joint_idx']
        is_symmetric = result['is_symmetric']

        if is_symmetric:
            print(f"  关节 {joint_idx + 1}: 1  (对称运动，无需反向)")
        else:
            print(f"  关节 {joint_idx + 1}: ?  (非对称运动，需要人工判断)")
            print(f"    提示: 正向位移 = {result['delta_pos']}")
            print(f"          负向位移 = {result['delta_neg']}")

    print(f"\n建议的 negation 数组（左臂）:")
    print(f"  {negation}")

    return negation


def main():
    """主函数"""
    print_section("🔍 正运动学关节方向诊断工具")

    # 配置参数
    arm_side = 'left'
    delta_angle = np.deg2rad(45)  # 测试角度：45度

    # 从 filters.py 读取当前的 negation 映射
    # 或者手动指定测试的 negation
    test_negation = np.array([1, 1, 1, 1, 1, 1, 1])  # 遥操配置文件中的值

    print(f"\n配置:")
    print(f"  机械臂侧: {arm_side}")
    print(f"  测试角度: {np.rad2deg(delta_angle):.1f}°")
    print(f"  Negation 映射: {test_negation}")
    print(f"  说明: 使用 negation 映射测试 FK 计算结果")

    # 初始化 Pinocchio 模型（只需要 FK，不需要完整的 IK Solver）
    print_section("1️⃣ 初始化 Pinocchio 模型")

    try:
        urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf'

        # 直接使用 Pinocchio 加载模型（不需要 IKSolver 的复杂初始化）
        model = pin.buildModelFromUrdf(urdf_path)
        data = model.createData()

        # 查找左臂末端执行器的 frame ID
        # 根据 check_joint_order.py 的结果，使用 Left_Wrist_Roll_Link（Z 最低，最末端）
        ee_frame_name = 'Left_Wrist_Roll_Link'
        if model.existFrame(ee_frame_name):
            ee_frame_id = model.getFrameId(ee_frame_name)
            print(f"✓ Pinocchio 模型初始化成功")
            print(f"  URDF: {urdf_path}")
            print(f"  末端执行器: {ee_frame_name} (frame_id={ee_frame_id})")
        else:
            print(f"❌ 找不到末端执行器 frame: {ee_frame_name}")
            print(f"可用的 frames: {[model.frames[i].name for i in range(model.nframes)]}")
            return

        # 创建一个简单的对象来模拟 IKSolver 接口
        class SimpleFK:
            def __init__(self, model, data, ee_frame_id):
                self.model = model
                self.data = data
                self.ee_frame_id = ee_frame_id

        ik_solver = SimpleFK(model, data, ee_frame_id)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return

    # 测试所有关节
    print_section("2️⃣ 逐个关节测试正运动学")

    results = []
    for joint_idx in range(7):
        print(f"\n测试关节 {joint_idx + 1}...")
        result = test_joint_direction(ik_solver, joint_idx, delta_angle, arm_side, negation=test_negation)
        results.append(result)

        # 打印分析报告
        report = analyze_joint_motion(result)
        print(report)

    # 生成建议
    print_section("3️⃣ 生成关节方向映射建议")
    suggested_ntion = suggest_negation_mapping(results)

    # 可视化
    print_section("4️⃣ 生成可视化图表")
    try:
        visualize_joint_motions(results, arm_side)
    except Exception as e:
        print(f"⚠️  可视化失败: {e}")
        print("（可能是因为没有图形界面，跳过可视化）")

    # 总结
    print_section("✅ 诊断完成")
    print("\n下一步建议:")
    print("1. 查看生成的可视化图表，理解每个关节的运动方向")
    print("2. 对比实际机械臂的运动行为，确认哪些关节需要反向")
    print("3. 更新 filters.py 中的 joint_negation 数组")
    print("4. 重新测试 FSM 的距离计算是否正确")

    print("\n💡 提示:")
    print("  - 如果某个关节的运动方向与预期相反，将对应的 negation 值改为 -1")
    print("  - 如果运动方向正确，保持 negation 值为 1")
    print("  - 对于非对称运动的关节，需要结合实际机械臂行为判断")


if __name__ == '__main__':
    main()