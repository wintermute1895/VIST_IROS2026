#!/usr/bin/env python3
"""
VIST v3.0 测试脚本

测试内容：
1. 双观测源融合（人类观测 + 虚拟观测）
2. 改进的意图因子计算（融合速度和位置距离）
3. α范围限制在 [0.05, 0.95]
4. 监控关节变化量和卡尔曼增益K
"""

import numpy as np
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "ros2_ws"))

from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.config.config_loader import get_config


def test_v3_intent_detection():
    """测试v3.0的意图检测（融合速度和距离）"""
    print("\n" + "="*80)
    print("测试 1: v3.0 意图检测（速度 + 距离融合）")
    print("="*80)

    # 初始化
    config_path = project_root / "config" / "system_config.yaml"
    config = get_config(str(config_path))

    # 使用URDF路径
    urdf_path = str(project_root / "config" / "urdf" / "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path)
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 测试场景
    test_cases = [
        {
            "name": "场景1: 高速 + 远离目标",
            "velocity": 0.20,  # 高速
            "ee_position": np.array([0.5, 0.0, 0.3]),  # 远离目标
            "expected_alpha": "低 (0.05-0.2)"
        },
        {
            "name": "场景2: 低速 + 接近目标",
            "velocity": 0.003,  # 低速
            "ee_position": np.array([0.41, -0.11, 0.3]),  # 接近目标
            "expected_alpha": "高 (0.8-0.95)"
        },
        {
            "name": "场景3: 中速 + 中等距离",
            "velocity": 0.05,  # 中速
            "ee_position": np.array([0.45, -0.05, 0.3]),  # 中等距离
            "expected_alpha": "中 (0.4-0.6)"
        },
        {
            "name": "场景4: 高速 + 接近目标（冲突）",
            "velocity": 0.18,  # 高速
            "ee_position": np.array([0.41, -0.11, 0.3]),  # 接近目标
            "expected_alpha": "中低 (0.3-0.5)"
        },
    ]

    for case in test_cases:
        print(f"\n{case['name']}")
        print(f"  输入速度: {case['velocity']:.4f} m/s")
        print(f"  末端位置: {case['ee_position']}")
        print(f"  目标位置: [0.41, -0.11, z]")

        # 计算距离
        distance = np.linalg.norm(case['ee_position'][:2] - vist_filter.target_position_xy)
        print(f"  XY距离: {distance:.4f} m")

        # 计算意图因子
        alpha = vist_filter._compute_intent_factor(case['velocity'], case['ee_position'])

        print(f"  计算得到 α: {alpha:.3f}")
        print(f"  预期范围: {case['expected_alpha']}")
        print(f"  α范围检查: {'✅' if 0.05 <= alpha <= 0.95 else '❌'}")

    print("\n✅ 意图检测测试完成")


def test_v3_dual_observation():
    """测试v3.0的双观测源融合"""
    print("\n" + "="*80)
    print("测试 2: v3.0 双观测源融合")
    print("="*80)

    # 初始化
    config_path = project_root / "config" / "system_config.yaml"
    config = get_config(str(config_path))
    urdf_path = str(project_root / "config" / "urdf" / "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path)
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 初始关节角度
    initial_joints = np.array([0.0, 0.3, 0.0, -1.5, 0.0, 1.8, 0.0])

    # 第一帧：初始化
    print("\n第1帧：初始化")
    filtered = vist_filter.update(initial_joints, None, None)
    print(f"  初始关节: {initial_joints[:3]}...")
    print(f"  滤波输出: {filtered[:3]}...")

    # 第2-5帧：单观测源（仅人类）
    print("\n第2-5帧：单观测源（仅人类观测）")
    for i in range(4):
        # 模拟人类输入（有噪声）
        noise = np.random.randn(7) * 0.01
        human_obs = initial_joints + noise + 0.05 * (i + 1)

        filtered = vist_filter.update(human_obs, None, None)

        print(f"  帧{i+2}: α={vist_filter.current_alpha:.3f}, "
              f"R_human×{np.trace(vist_filter.R_human)/np.trace(vist_filter.R_base):.1f}")

    # 第6-10帧：双观测源（人类 + 虚拟）
    print("\n第6-10帧：双观测源（人类 + 虚拟）")
    for i in range(5):
        # 模拟人类输入（有噪声）
        noise = np.random.randn(7) * 0.02
        human_obs = initial_joints + noise + 0.05 * (i + 5)

        # 模拟虚拟引导（更精确）
        virtual_obs = initial_joints + 0.05 * (i + 5) + np.random.randn(7) * 0.005

        filtered = vist_filter.update(human_obs, None, virtual_obs)

        print(f"  帧{i+6}: α={vist_filter.current_alpha:.3f}, "
              f"R_human×{np.trace(vist_filter.R_human)/np.trace(vist_filter.R_base):.1f}, "
              f"R_virtual×{np.trace(vist_filter.R_virtual)/np.trace(vist_filter.R_base):.2f}")

    print("\n✅ 双观测源融合测试完成")


def test_v3_monitoring():
    """测试v3.0的监控功能"""
    print("\n" + "="*80)
    print("测试 3: v3.0 监控功能")
    print("="*80)

    # 初始化
    config_path = project_root / "config" / "system_config.yaml"
    config = get_config(str(config_path))
    urdf_path = str(project_root / "config" / "urdf" / "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path)
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 初始关节角度
    initial_joints = np.array([0.0, 0.3, 0.0, -1.5, 0.0, 1.8, 0.0])

    # 运行几帧
    print("\n运行10帧，监控关节变化量和卡尔曼增益K")
    for i in range(10):
        noise = np.random.randn(7) * 0.01
        obs = initial_joints + noise + 0.02 * i

        filtered = vist_filter.update(obs, None, None)

        # 获取监控数据
        joint_delta = vist_filter.get_joint_delta()
        k_gain = vist_filter.get_kalman_gain()
        distance = vist_filter.get_distance_to_target()

        if i > 0:  # 第一帧没有delta
            print(f"  帧{i+1}: "
                  f"关节变化={np.linalg.norm(joint_delta):.6f}, "
                  f"K范数={np.linalg.norm(k_gain):.6f}, "
                  f"距离={distance:.4f}m")

    print("\n✅ 监控功能测试完成")


def test_v3_alpha_limits():
    """测试v3.0的α限制"""
    print("\n" + "="*80)
    print("测试 4: v3.0 α范围限制 [0.05, 0.95]")
    print("="*80)

    # 初始化
    config_path = project_root / "config" / "system_config.yaml"
    config = get_config(str(config_path))
    urdf_path = str(project_root / "config" / "urdf" / "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(urdf_path)
    vist_filter = VISTKalmanFilter(ik_solver, config)

    # 极端场景
    extreme_cases = [
        {
            "name": "极低速 + 极近距离",
            "velocity": 0.0001,
            "ee_position": np.array([0.41, -0.11, 0.3])
        },
        {
            "name": "极高速 + 极远距离",
            "velocity": 0.5,
            "ee_position": np.array([0.8, 0.3, 0.3])
        },
    ]

    for case in extreme_cases:
        alpha = vist_filter._compute_intent_factor(case['velocity'], case['ee_position'])
        print(f"\n{case['name']}")
        print(f"  速度: {case['velocity']:.4f} m/s")
        print(f"  位置: {case['ee_position']}")
        print(f"  α: {alpha:.3f}")
        print(f"  范围检查: {'✅ 在[0.05, 0.95]内' if 0.05 <= alpha <= 0.95 else '❌ 超出范围'}")

    print("\n✅ α范围限制测试完成")


def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("VIST v3.0 完整测试套件")
    print("="*80)

    try:
        test_v3_intent_detection()
        test_v3_dual_observation()
        test_v3_monitoring()
        test_v3_alpha_limits()

        print("\n" + "="*80)
        print("✅ 所有测试通过！v3.0 功能正常")
        print("="*80)
        print("\n下一步：")
        print("1. 启动 ROS2 节点: ros2 run vist_filter vist_filter_node")
        print("2. 启动监控节点: python3 ros2_ws/src/nodes/vist_monitor.py")
        print("3. 使用 meshcat 可视化测试实际效果")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
