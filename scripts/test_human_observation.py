#!/usr/bin/env python3
"""
测试 VIST 人类指令观测集成

验证：
1. 人类指令观测是否正确计算
2. 双观测融合是否正常工作
3. 响应速度是否改善
"""

import numpy as np
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.config import get_config
import pinocchio as pin


def test_human_observation():
    """测试人类指令观测计算"""
    print("=" * 60)
    print("测试 1: 人类指令观测计算")
    print("=" * 60)

    # 初始化
    config = get_config()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 初始化状态
    q_init = pin.neutral(ik_solver.model)
    target_pos_init = np.array([0.3, -0.2, 1.2])
    vist_filter.solve(target_pos_init, q_init=q_init)

    print(f"✅ 初始化完成")
    print(f"   初始位置: {target_pos_init}")
    print(f"   历史位置: {vist_filter.previous_target_pos}")

    # 测试1：静止（人手不动）
    print("\n📍 场景 1: 人手静止")
    target_pos_1 = target_pos_init.copy()
    q_sol_1, success_1, error_1 = vist_filter.solve(target_pos_1)

    # 手动计算人类指令（应该接近零）
    if vist_filter.previous_target_pos is not None:
        human_delta = vist_filter.compute_human_delta_theta(
            target_pos_1,
            vist_filter.previous_target_pos
        )
        print(f"   人类指令增量: {np.linalg.norm(human_delta):.6f} rad")
        print(f"   预期: 接近 0（因为手不动）")

        if np.linalg.norm(human_delta) < 1e-6:
            print(f"   ✅ 通过：人手静止时指令增量为零")
        else:
            print(f"   ⚠️  警告：人手静止但指令增量非零")

    # 测试2：匀速运动（人手向前移动10cm）
    print("\n🏃 场景 2: 人手匀速运动（向前10cm）")
    target_pos_2 = target_pos_1 + np.array([0.1, 0.0, 0.0])
    q_sol_2, success_2, error_2 = vist_filter.solve(target_pos_2)

    # 计算人类指令
    human_delta_2 = vist_filter.compute_human_delta_theta(
        target_pos_2,
        target_pos_1
    )
    print(f"   人类指令增量: {np.linalg.norm(human_delta_2):.6f} rad")
    print(f"   预期: 明显非零（因为手在移动）")

    if np.linalg.norm(human_delta_2) > 1e-3:
        print(f"   ✅ 通过：人手运动时指令增量明显")
    else:
        print(f"   ❌ 失败：人手运动但指令增量过小")

    # 测试3：突然停止
    print("\n🛑 场景 3: 人手突然停止")
    target_pos_3 = target_pos_2.copy()  # 保持不动
    q_sol_3, success_3, error_3 = vist_filter.solve(target_pos_3)

    human_delta_3 = vist_filter.compute_human_delta_theta(
        target_pos_3,
        target_pos_2
    )
    print(f"   人类指令增量: {np.linalg.norm(human_delta_3):.6f} rad")
    print(f"   预期: 接近 0（因为手停止了）")

    if np.linalg.norm(human_delta_3) < 1e-6:
        print(f"   ✅ 通过：人手停止时指令增量为零")
    else:
        print(f"   ⚠️  警告：人手停止但指令增量非零")

    print("\n" + "=" * 60)
    print("测试 1 完成")
    print("=" * 60)


def test_dual_observation_fusion():
    """测试双观测融合"""
    print("\n" + "=" * 60)
    print("测试 2: 双观测融合")
    print("=" * 60)

    # 初始化
    config = get_config()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 初始化
    q_init = pin.neutral(ik_solver.model)
    target_pos = np.array([0.3, -0.2, 1.2])
    vist_filter.solve(target_pos, q_init=q_init)

    print(f"✅ 初始化完成")

    # 模拟连续运动
    print("\n🔄 模拟连续运动（10帧）")
    trajectory = []
    for i in range(10):
        # 向前移动
        target_pos = target_pos + np.array([0.01, 0.0, 0.0])
        q_solution, success, error = vist_filter.solve(target_pos)

        trajectory.append({
            'frame': i,
            'target_pos': target_pos.copy(),
            'error': error,
            'alpha': vist_filter.alpha_smoothed
        })

        if i % 3 == 0:
            print(f"   帧 {i}: 误差={error*1000:.2f}mm, 意图因子={vist_filter.alpha_smoothed:.3f}")

    # 分析轨迹
    errors = [t['error'] for t in trajectory]
    print(f"\n📊 轨迹分析:")
    print(f"   初始误差: {errors[0]*1000:.2f}mm")
    print(f"   最终误差: {errors[-1]*1000:.2f}mm")
    print(f"   平均误差: {np.mean(errors)*1000:.2f}mm")
    print(f"   最大误差: {np.max(errors)*1000:.2f}mm")

    if errors[-1] < errors[0]:
        print(f"   ✅ 通过：误差收敛")
    else:
        print(f"   ⚠️  警告：误差未收敛")

    print("\n" + "=" * 60)
    print("测试 2 完成")
    print("=" * 60)


def test_response_speed():
    """测试响应速度对比"""
    print("\n" + "=" * 60)
    print("测试 3: 响应速度对比")
    print("=" * 60)

    # 初始化
    config = get_config()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 测试A：有人类指令观测（正常模式）
    print("\n🔬 模式 A: 有人类指令观测")
    vist_filter_a = VISTKalmanFilter(ik_solver, config)
    q_init = pin.neutral(ik_solver.model)
    target_pos = np.array([0.3, -0.2, 1.2])
    vist_filter_a.solve(target_pos, q_init=q_init)

    # 大幅度运动
    target_pos_far = target_pos + np.array([0.15, 0.0, 0.0])
    errors_a = []
    for i in range(20):
        q_sol, success, error = vist_filter_a.solve(target_pos_far)
        errors_a.append(error)

    print(f"   初始误差: {errors_a[0]*1000:.2f}mm")
    print(f"   5帧后误差: {errors_a[4]*1000:.2f}mm")
    print(f"   10帧后误差: {errors_a[9]*1000:.2f}mm")
    print(f"   最终误差: {errors_a[-1]*1000:.2f}mm")

    # 测试B：无人类指令观测（模拟旧版本）
    print("\n🔬 模式 B: 无人类指令观测（模拟）")
    vist_filter_b = VISTKalmanFilter(ik_solver, config)
    vist_filter_b.solve(target_pos, q_init=q_init)

    # 强制禁用人类指令（通过清空历史）
    errors_b = []
    for i in range(20):
        # 每次都清空历史，模拟无人类指令
        vist_filter_b.previous_target_pos = None
        q_sol, success, error = vist_filter_b.solve(target_pos_far)
        errors_b.append(error)

    print(f"   初始误差: {errors_b[0]*1000:.2f}mm")
    print(f"   5帧后误差: {errors_b[4]*1000:.2f}mm")
    print(f"   10帧后误差: {errors_b[9]*1000:.2f}mm")
    print(f"   最终误差: {errors_b[-1]*1000:.2f}mm")

    # 对比
    print(f"\n📊 响应速度对比:")
    print(f"   5帧误差改善: {(errors_b[4] - errors_a[4])*1000:.2f}mm")
    print(f"   10帧误差改善: {(errors_b[9] - errors_a[9])*1000:.2f}mm")

    if errors_a[4] < errors_b[4]:
        print(f"   ✅ 通过：有人类指令观测时响应更快")
    else:
        print(f"   ⚠️  警告：人类指令观测未改善响应速度")

    print("\n" + "=" * 60)
    print("测试 3 完成")
    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("VIST 人类指令观测集成测试")
    print("=" * 60)

    try:
        # 测试1：人类指令观测计算
        test_human_observation()

        # 测试2：双观测融合
        test_dual_observation_fusion()

        # 测试3：响应速度对比
        test_response_speed()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
