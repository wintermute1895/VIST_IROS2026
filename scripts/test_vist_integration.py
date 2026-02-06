#!/usr/bin/env python3
"""
VIST 集成测试脚本

快速验证 VIST Kalman Filter 是否正确集成
"""

import os
import sys
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
import pinocchio as pin


def test_vist_integration():
    """测试 VIST 集成"""
    print("=" * 80)
    print("🧪 VIST 集成测试")
    print("=" * 80)

    # 1. 测试配置加载
    print("\n📁 测试 1: 配置加载")
    try:
        config = get_config()
        print(f"✅ 配置加载成功")
        print(f"   IK 策略: {config.ik_strategy}")
        print(f"   VIST 启用: {config.vist_enabled}")
        print(f"   VIST 关节数: {config.vist_n_joints}")
        print(f"   VIST 状态维度: {config.vist_state_dim}")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

    # 2. 测试 IK 求解器初始化
    print("\n🧠 测试 2: IK 求解器初始化")
    try:
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
        ik_solver = PinocchioIKSolver(
            urdf_path=urdf_path,
            end_effector_frame="Right_Wrist_Roll_Link"
        )
        print(f"✅ IK 求解器初始化成功")
        print(f"   模型关节数: {ik_solver.model.nq}")
        print(f"   受控关节数: {len(ik_solver.controlled_indices)}")
    except Exception as e:
        print(f"❌ IK 求解器初始化失败: {e}")
        return False

    # 3. 测试 VIST Kalman Filter 初始化
    print("\n🔬 测试 3: VIST Kalman Filter 初始化")
    try:
        vist_filter = VISTKalmanFilter(ik_solver, config)
        print(f"✅ VIST Kalman Filter 初始化成功")
        print(f"   状态维度: {vist_filter.state_dim}")
        print(f"   关节数: {vist_filter.n_joints}")
        print(f"   时间步长: {vist_filter.dt}")
        print(f"   状态转移矩阵 F 形状: {vist_filter.F.shape}")
        print(f"   过程噪声 Q 形状: {vist_filter.Q.shape}")
        print(f"   观测矩阵 H 形状: {vist_filter.H.shape}")
    except Exception as e:
        print(f"❌ VIST Kalman Filter 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. 测试微分 IK
    print("\n🎯 测试 4: 微分 IK 计算")
    try:
        # 设置初始状态（使用 solve 方法的初始化逻辑）
        q_init = pin.neutral(ik_solver.model)

        # 通过 solve 方法初始化（会自动处理维度转换）
        target_pos_init = np.array([0.3, -0.2, 1.2])
        vist_filter.solve(target_pos_init, q_init=q_init)

        # 重置迭代计数以便后续测试
        vist_filter.iteration_count = 1  # 设置为非零，避免重新初始化

        # 计算当前末端位置
        current_pos = vist_filter._get_current_end_effector_position()

        # 设置目标位置（向前移动 10cm）
        target_pos = current_pos + np.array([0.1, 0.0, 0.0])

        # 计算微分 IK
        delta_theta = vist_filter.compute_differential_ik(target_pos)
        print(f"✅ 微分 IK 计算成功")
        print(f"   当前位置: {current_pos}")
        print(f"   目标位置: {target_pos}")
        print(f"   关节增量: {delta_theta}")
        print(f"   增量范数: {np.linalg.norm(delta_theta):.4f}")
    except Exception as e:
        print(f"❌ 微分 IK 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. 测试意图检测
    print("\n🧠 测试 5: 意图检测")
    try:
        # 测试不同距离和速度
        test_cases = [
            (0.5, 0.1, "远距离快速移动"),
            (0.05, 0.01, "近距离慢速移动"),
            (0.1, 0.05, "中等距离中等速度"),
        ]

        for distance, velocity, description in test_cases:
            target_pos = current_pos + np.array([distance, 0, 0])
            alpha = vist_filter.detect_intent(target_pos, current_pos, velocity)
            print(f"   {description}: α = {alpha:.3f}")

        print(f"✅ 意图检测测试成功")
    except Exception as e:
        print(f"❌ 意图检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 6. 测试完整求解流程
    print("\n🚀 测试 6: 完整求解流程")
    try:
        # 重置滤波器
        vist_filter.reset()

        # 设置目标位置
        target_pos = current_pos + np.array([0.1, 0.05, 0.0])

        # 求解
        q_solution, success, error = vist_filter.solve(
            target_pos=target_pos,
            q_init=q_init
        )

        print(f"✅ 完整求解流程测试成功")
        print(f"   求解成功: {success}")
        print(f"   位置误差: {error*1000:.2f}mm")
        print(f"   关节角度: {q_solution}")
    except Exception as e:
        print(f"❌ 完整求解流程失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 7. 测试多次迭代
    print("\n🔄 测试 7: 多次迭代（10次）")
    try:
        # 重置滤波器
        vist_filter.reset()

        # 使用 solve 初始化
        q_init = pin.neutral(ik_solver.model)
        target_pos = current_pos + np.array([0.1, 0.05, 0.0])

        errors = []
        for i in range(10):
            # 使用 solve 方法（包含预测和更新）
            q_solution, success, error = vist_filter.solve(
                target_pos=target_pos,
                q_init=q_init if i == 0 else None
            )
            errors.append(error * 1000)  # 转换为 mm

        print(f"✅ 多次迭代测试成功")
        print(f"   初始误差: {errors[0]:.2f}mm")
        print(f"   最终误差: {errors[-1]:.2f}mm")
        print(f"   误差收敛: {errors[0] > errors[-1]}")
    except Exception as e:
        print(f"❌ 多次迭代测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ 所有测试通过！VIST 集成成功！")
    print("=" * 80)
    print("\n📝 下一步:")
    print("   1. 运行 python scripts/simulate_full_flow.py 进行完整测试")
    print("   2. 在 config/system_config.yaml 中设置 ik_strategy: 'vist'")
    print("   3. 对比传统 IK 和 VIST 的性能")
    print()

    return True


if __name__ == "__main__":
    success = test_vist_integration()
    sys.exit(0 if success else 1)
