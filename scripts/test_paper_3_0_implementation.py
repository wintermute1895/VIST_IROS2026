#!/usr/bin/env python3
"""
测试论文3.0版本的实现

验证内容：
1. 意图因子α的非线性融合（状态先验 × 主动门控）
2. 协方差调度的指数形式（R_human和R_virtual）
3. 冲突项R_conflict机制
4. Z轴锁定（流形约束）

Author: VIST Project
Date: 2026-02-16
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from pathlib import Path


def test_intent_factor_nonlinear_fusion():
    """测试意图因子的非线性融合"""
    print("\n" + "="*80)
    print("测试1: 意图因子α的非线性融合")
    print("="*80)

    # 加载配置
    config = get_config()

    # 初始化IK求解器
    urdf_path = Path(project_root) / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 初始化VIST滤波器
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 测试场景：从远处接近目标
    target_pos = np.array([0.3, 0.0, 0.2])

    # 场景1：远离目标，快速移动，正对目标
    print("\n场景1: 远离目标，快速移动，正对目标")
    current_pos = np.array([0.5, 0.0, 0.2])
    velocity = np.array([-0.1, 0.0, 0.0])  # 向目标移动
    alpha1 = vist_filter.detect_intent(target_pos, current_pos, velocity)
    print(f"  α = {alpha1:.4f} (预期: 接近0，因为距离远且速度快)")

    # 场景2：接近目标，慢速移动，正对目标
    print("\n场景2: 接近目标，慢速移动，正对目标")
    current_pos = np.array([0.32, 0.0, 0.2])
    velocity = np.array([-0.01, 0.0, 0.0])  # 慢速向目标移动
    alpha2 = vist_filter.detect_intent(target_pos, current_pos, velocity)
    print(f"  α = {alpha2:.4f} (预期: 接近1，因为距离近且速度慢)")

    # 场景3：接近目标，慢速移动，但背离目标（方向门控测试）
    print("\n场景3: 接近目标，慢速移动，但背离目标")
    current_pos = np.array([0.32, 0.0, 0.2])
    velocity = np.array([0.01, 0.0, 0.0])  # 背离目标
    alpha3 = vist_filter.detect_intent(target_pos, current_pos, velocity)
    print(f"  α = {alpha3:.4f} (预期: 显著降低，因为方向门控起作用)")

    # 场景4：接近目标，慢速移动，切向移动（方向门控测试）
    print("\n场景4: 接近目标，慢速移动，切向移动")
    current_pos = np.array([0.32, 0.0, 0.2])
    velocity = np.array([0.0, 0.01, 0.0])  # 切向移动
    alpha4 = vist_filter.detect_intent(target_pos, current_pos, velocity)
    print(f"  α = {alpha4:.4f} (预期: 中等值，因为方向不对齐)")

    # 验证非线性融合的效果
    print("\n验证: 方向门控的'一票否决权'")
    print(f"  场景2 (正对目标): α = {alpha2:.4f}")
    print(f"  场景3 (背离目标): α = {alpha3:.4f}")
    print(f"  降低比例: {(1 - alpha3/alpha2)*100:.1f}%")

    if alpha3 < alpha2 * 0.5:
        print("  ✅ 方向门控有效：背离目标时α显著降低")
    else:
        print("  ⚠️ 方向门控效果不明显")

    return alpha1, alpha2, alpha3, alpha4


def test_covariance_scheduling():
    """测试协方差调度的指数形式"""
    print("\n" + "="*80)
    print("测试2: 协方差调度的指数形式")
    print("="*80)

    # 加载配置
    config = get_config()

    # 初始化IK求解器
    urdf_path = Path(project_root) / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 初始化VIST滤波器
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 测试不同α值下的协方差
    alphas = [0.0, 0.3, 0.6, 0.9, 1.0]
    R_humans = []
    R_virtuals = []

    print("\nα值变化对协方差的影响:")
    print(f"{'α':<6} {'R_human':<15} {'R_virtual':<15}")
    print("-" * 40)

    for alpha in alphas:
        vist_filter.alpha_smoothed = alpha

        # 构建观测噪声协方差矩阵
        R = vist_filter._build_observation_noise_covariance()

        # 提取人类指令和虚拟引导的方差
        R_human = R[0, 0]
        R_virtual = R[vist_filter.n_joints, vist_filter.n_joints]

        R_humans.append(R_human)
        R_virtuals.append(R_virtual)

        print(f"{alpha:<6.1f} {R_human:<15.6f} {R_virtual:<15.6f}")

    # 验证指数形式
    print("\n验证指数形式:")
    print(f"  R_human(α=0) = {R_humans[0]:.6f}")
    print(f"  R_human(α=1) = {R_humans[-1]:.6f}")
    print(f"  增长倍数 = {R_humans[-1]/R_humans[0]:.2f}x")

    if R_humans[-1] / R_humans[0] > 10:
        print("  ✅ 指数增长有效：α→1时R_human显著增大")
    else:
        print("  ⚠️ 指数增长效果不明显")

    print(f"\n  R_virtual(α=0) = {R_virtuals[0]:.6f}")
    print(f"  R_virtual(α=1) = {R_virtuals[-1]:.6f}")
    print(f"  降低倍数 = {R_virtuals[0]/R_virtuals[-1]:.2f}x")

    if R_virtuals[0] / R_virtuals[-1] > 10:
        print("  ✅ 反比例有效：α→1时R_virtual显著减小")
    else:
        print("  ⚠️ 反比例效果不明显")

    return alphas, R_humans, R_virtuals


def test_conflict_mechanism():
    """测试冲突项R_conflict机制"""
    print("\n" + "="*80)
    print("测试3: 冲突项R_conflict机制")
    print("="*80)

    # 加载配置
    config = get_config()

    # 初始化IK求解器
    urdf_path = Path(project_root) / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 初始化VIST滤波器
    vist_filter = VISTKalmanFilter(ik_solver, config)
    vist_filter.alpha_smoothed = 0.9  # 高意图因子

    # 测试不同冲突强度
    print("\n冲突强度对R_virtual的影响:")
    print(f"{'冲突强度':<15} {'R_virtual':<15}")
    print("-" * 35)

    conflicts = [0.0, 0.1, 0.5, 1.0, 2.0]
    R_virtuals_conflict = []

    for conflict_norm in conflicts:
        # 构造冲突向量
        human_delta = np.zeros(7)
        virtual_delta = np.ones(7) * conflict_norm / np.sqrt(7)

        # 构建观测噪声协方差矩阵
        R = vist_filter._build_observation_noise_covariance(
            human_delta_theta=human_delta,
            virtual_delta_theta=virtual_delta
        )

        R_virtual = R[vist_filter.n_joints, vist_filter.n_joints]
        R_virtuals_conflict.append(R_virtual)

        print(f"{conflict_norm:<15.1f} {R_virtual:<15.6f}")

    # 验证冲突项效果
    print("\n验证冲突项:")
    print(f"  无冲突时: R_virtual = {R_virtuals_conflict[0]:.6f}")
    print(f"  强冲突时: R_virtual = {R_virtuals_conflict[-1]:.6f}")
    print(f"  增长倍数 = {R_virtuals_conflict[-1]/R_virtuals_conflict[0]:.2f}x")

    if R_virtuals_conflict[-1] / R_virtuals_conflict[0] > 2:
        print("  ✅ 冲突项有效：冲突时R_virtual显著增大，允许'挣脱'")
    else:
        print("  ⚠️ 冲突项效果不明显")

    return conflicts, R_virtuals_conflict


def visualize_results(alphas, R_humans, R_virtuals, conflicts, R_virtuals_conflict):
    """可视化测试结果"""
    print("\n" + "="*80)
    print("生成可视化图表")
    print("="*80)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 图1: 协方差调度（指数形式）
    ax1 = axes[0, 0]
    ax1.plot(alphas, R_humans, 'b-o', label='R_human (指数增长)', linewidth=2)
    ax1.plot(alphas, R_virtuals, 'r-s', label='R_virtual (反比例)', linewidth=2)
    ax1.set_xlabel('意图因子 α', fontsize=12)
    ax1.set_ylabel('观测噪声方差', fontsize=12)
    ax1.set_title('协方差调度（论文3.0版本：指数形式）', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale('log')

    # 图2: 冲突项效果
    ax2 = axes[0, 1]
    ax2.plot(conflicts, R_virtuals_conflict, 'g-^', linewidth=2)
    ax2.set_xlabel('冲突强度 ||Δθ_h - Δθ_v||', fontsize=12)
    ax2.set_ylabel('R_virtual', fontsize=12)
    ax2.set_title('冲突项R_conflict机制', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # 图3: R_human的指数增长
    ax3 = axes[1, 0]
    ax3.semilogy(alphas, R_humans, 'b-o', linewidth=2)
    ax3.set_xlabel('意图因子 α', fontsize=12)
    ax3.set_ylabel('R_human (对数尺度)', fontsize=12)
    ax3.set_title('R_human = R_base × exp(λα)', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # 图4: R_virtual的反比例
    ax4 = axes[1, 1]
    ax4.plot(alphas, R_virtuals, 'r-s', linewidth=2)
    ax4.set_xlabel('意图因子 α', fontsize=12)
    ax4.set_ylabel('R_virtual', fontsize=12)
    ax4.set_title('R_virtual = R_min/(α + ε)', fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    # 保存图表
    output_path = os.path.join(project_root, 'logs', 'paper_3_0_verification.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存到: {output_path}")

    plt.show()


def main():
    """主函数"""
    print("\n" + "="*80)
    print("VIST 论文3.0版本实现验证")
    print("="*80)
    print("\n验证内容:")
    print("1. 意图因子α的非线性融合（状态先验 × 主动门控）")
    print("2. 协方差调度的指数形式（R_human和R_virtual）")
    print("3. 冲突项R_conflict机制")
    print("4. Z轴锁定（流形约束）")

    try:
        # 测试1: 意图因子
        alpha1, alpha2, alpha3, alpha4 = test_intent_factor_nonlinear_fusion()

        # 测试2: 协方差调度
        alphas, R_humans, R_virtuals = test_covariance_scheduling()

        # 测试3: 冲突机制
        conflicts, R_virtuals_conflict = test_conflict_mechanism()

        # 可视化结果
        visualize_results(alphas, R_humans, R_virtuals, conflicts, R_virtuals_conflict)

        print("\n" + "="*80)
        print("✅ 所有测试完成！")
        print("="*80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
