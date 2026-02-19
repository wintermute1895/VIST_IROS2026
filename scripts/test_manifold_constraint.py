#!/usr/bin/env python3
"""
测试流形约束功能

验证当α=1.0且流形约束启用时，Q矩阵是否正确应用了约束
"""

import sys
import os
from pathlib import Path
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.utils.parameter_override import ParameterOverrideManager

def test_manifold_constraint():
    """测试流形约束功能"""

    print("=" * 80)
    print("🧪 测试流形约束功能")
    print("=" * 80)

    # 1. 加载配置
    print("\n[1/4] 加载配置...")
    config = get_config()
    print(f"✅ vist_simulation_use_parameter_override: {config.vist_simulation_use_parameter_override}")

    # 2. 检查参数覆盖
    print("\n[2/4] 检查参数覆盖...")
    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()
    print(f"✅ alpha_override: {override.alpha_override}")
    print(f"✅ manifold_enabled_override: {override.manifold_enabled_override}")

    # 3. 初始化VIST
    print("\n[3/4] 初始化VIST...")
    urdf_path = project_root / "config" / "lkls73_o2_dual_arm_description.urdf"
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame="Right_Wrist_Roll_Link"
    )
    vist_filter = VISTKalmanFilter(ik_solver, config)
    print("✅ VIST滤波器初始化完成")

    # 4. 测试流形约束
    print("\n[4/4] 测试流形约束...")

    # 设置一个合理的初始状态
    vist_filter.state[:7] = np.array([0.0, 0.0, 0.0, 1.57, 0.0, 0.0, 0.0])  # 肘部90度

    # 调用detect_intent设置α
    target_pos = np.array([0.3, -0.2, 1.0])
    current_pos = np.array([0.3, -0.2, 1.05])
    velocity = np.array([0.0, 0.0, -0.01])
    alpha = vist_filter.detect_intent(target_pos, current_pos, velocity)

    print(f"✅ α_smoothed: {vist_filter.alpha_smoothed:.4f}")

    # 构建Q矩阵
    Q = vist_filter._build_process_noise_covariance()

    print(f"\n📊 Q矩阵分析:")
    print(f"   Q矩阵形状: {Q.shape}")
    print(f"   Q矩阵对角线（位置部分）:")
    for i in range(7):
        print(f"      J{i+1}: {Q[i, i]:.6e}")

    # 检查流形约束是否生效
    print(f"\n🔍 流形约束验证:")

    # 检查should_apply_manifold
    should_apply = override.should_apply_manifold(vist_filter.alpha_smoothed, 0.8)
    print(f"   should_apply_manifold: {should_apply}")

    if should_apply:
        # 流形约束应该使得某些关节的方差变小
        # 但由于是通过雅可比投影，不是简单的对角矩阵
        print(f"   ✅ 流形约束已启用")

        # 检查Q矩阵是否有非对角元素（雅可比投影的特征）
        off_diagonal_sum = np.sum(np.abs(Q[:7, :7])) - np.sum(np.abs(np.diag(Q[:7, :7])))
        print(f"   非对角元素和: {off_diagonal_sum:.6e}")

        if off_diagonal_sum > 1e-10:
            print(f"   ✅ Q矩阵包含非对角元素，说明雅可比投影已应用")
        else:
            print(f"   ⚠️ Q矩阵是对角矩阵，流形约束可能未正确应用")
    else:
        print(f"   ❌ 流形约束未启用")

    # 验证结果
    print("\n" + "=" * 80)
    print("📊 验证结果")
    print("=" * 80)

    success = True

    # 检查1: α_smoothed应该等于1.0
    if abs(vist_filter.alpha_smoothed - 1.0) < 0.01:
        print("✅ α_smoothed = 1.0 (正确)")
    else:
        print(f"❌ α_smoothed = {vist_filter.alpha_smoothed:.4f} (应该是1.0)")
        success = False

    # 检查2: 流形约束应该启用
    if should_apply:
        print("✅ 流形约束已启用 (正确)")
    else:
        print("❌ 流形约束未启用 (应该启用)")
        success = False

    # 检查3: Q矩阵应该包含非对角元素
    if off_diagonal_sum > 1e-10:
        print("✅ Q矩阵包含雅可比投影 (正确)")
    else:
        print("❌ Q矩阵是对角矩阵 (应该包含非对角元素)")
        success = False

    if success:
        print("\n✅ 所有测试通过！流形约束功能正常工作")
    else:
        print("\n❌ 部分测试失败")

    return success

if __name__ == "__main__":
    success = test_manifold_constraint()
    sys.exit(0 if success else 1)
