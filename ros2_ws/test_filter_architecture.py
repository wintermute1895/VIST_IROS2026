#!/usr/bin/env python3
"""
VIST 滤波器架构测试脚本
验证策略模式和工厂模式的正确性
"""
import sys
from pathlib import Path

# 添加项目路径
ros2_ws_root = Path(__file__).parent.parent
sys.path.insert(0, str(ros2_ws_root))

import numpy as np


def test_filter_imports():
    """测试滤波器模块导入"""
    print("=" * 60)
    print("测试 1: 导入滤波器模块")
    print("=" * 60)

    try:
        from src.filters import (
            BaseTeleopFilter,
            GELLOFilter,
            OneEuroTeleopFilter,
            VISTTeleopFilter,
            FSMTeleopFilter,
            APFTeleopFilter,
            FilterFactory
        )
        print("✅ 所有滤波器类导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_core_modules():
    """测试核心模块导入"""
    print("\n" + "=" * 60)
    print("测试 2: 导入核心模块")
    print("=" * 60)

    try:
        from src.core.fsm_filter import FSMCore, MotionState
        print("✅ FSM 核心模块导入成功")

        from src.core.apf_filter import APFCore
        print("✅ APF 核心模块导入成功")

        return True
    except Exception as e:
        print(f"❌ 核心模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factory_pattern():
    """测试工厂模式"""
    print("\n" + "=" * 60)
    print("测试 3: 工厂模式")
    print("=" * 60)

    try:
        from src.filters import FilterFactory

        # 创建 Mock 对象
        class MockIKSolver:
            def __init__(self):
                self.model = None
                self.data = None
                self.ee_frame_id = 0

        class MockTCPCompensation:
            def compensate_target_pose(self, pos, quat):
                return pos, quat

        mock_ik = MockIKSolver()
        mock_tcp = MockTCPCompensation()
        target_pose = np.array([0.5, 0.0, 0.3, 0.0, 0.0, 0.0])

        # 测试 GELLO 滤波器创建
        print("\n测试创建 GELLO 滤波器...")
        gello_filter = FilterFactory.create_filter(
            'gello',
            ik_solver=mock_ik,
            tcp_compensation=mock_tcp,
            target_pose=target_pose
        )
        print(f"✅ GELLO 滤波器创建成功: {type(gello_filter).__name__}")

        # 测试 OneEuro 滤波器创建
        print("\n测试创建 OneEuro 滤波器...")
        oneeuro_filter = FilterFactory.create_filter(
            'oneeuro',
            ik_solver=mock_ik,
            tcp_compensation=mock_tcp,
            target_pose=target_pose,
            min_cutoff=1.0,
            beta=0.007
        )
        print(f"✅ OneEuro 滤波器创建成功: {type(oneeuro_filter).__name__}")

        # 测试不支持的滤波器类型
        print("\n测试不支持的滤波器类型...")
        try:
            FilterFactory.create_filter(
                'invalid_type',
                ik_solver=mock_ik,
                tcp_compensation=mock_tcp,
                target_pose=target_pose
            )
            print("❌ 应该抛出 ValueError")
            return False
        except ValueError as e:
            print(f"✅ 正确抛出异常: {e}")

        return True

    except Exception as e:
        print(f"❌ 工厂模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gello_filter():
    """测试 GELLO 滤波器"""
    print("\n" + "=" * 60)
    print("测试 4: GELLO 滤波器功能")
    print("=" * 60)

    try:
        from src.filters import GELLOFilter

        class MockIKSolver:
            pass

        class MockTCPCompensation:
            pass

        # 创建滤波器
        filter_obj = GELLOFilter(
            ik_solver=MockIKSolver(),
            tcp_compensation=MockTCPCompensation(),
            target_pose=np.zeros(6)
        )

        # 测试更新
        q_in = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        q_out = filter_obj.update(q_in, dt=0.0125)

        # GELLO 应该直通
        if np.allclose(q_in, q_out):
            print("✅ GELLO 滤波器直通测试通过")
            print(f"   输入: {q_in}")
            print(f"   输出: {q_out}")
            return True
        else:
            print("❌ GELLO 滤波器输出不匹配")
            return False

    except Exception as e:
        print(f"❌ GELLO 滤波器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fsm_core():
    """测试 FSM 核心逻辑"""
    print("\n" + "=" * 60)
    print("测试 5: FSM 核心状态机")
    print("=" * 60)

    try:
        from src.core.fsm_filter import FSMCore, MotionState

        # 创建 FSM 核心
        fsm = FSMCore(
            contact_threshold=0.005,
            approach_threshold=0.02,
            insertion_depth=0.01
        )

        # 测试状态转移
        print("\n测试状态转移...")

        # 初始状态应该是 FREE_SPACE
        assert fsm.current_state == MotionState.FREE_SPACE
        print(f"✅ 初始状态: {fsm.current_state.value}")

        # 接近目标 -> APPROACHING
        state = fsm.update_state(distance_to_target=0.015)
        assert state == MotionState.APPROACHING
        print(f"✅ 接近状态: {state.value}")

        # 接触 -> CONTACT
        state = fsm.update_state(distance_to_target=0.003)
        assert state == MotionState.CONTACT
        print(f"✅ 接触状态: {state.value}")

        # 测试控制增益
        pos_gain, ori_gain = fsm.get_control_gains()
        print(f"✅ 控制增益: pos={pos_gain}, ori={ori_gain}")

        return True

    except Exception as e:
        print(f"❌ FSM 核心测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_apf_core():
    """测试 APF 核心逻辑"""
    print("\n" + "=" * 60)
    print("测试 6: APF 核心势场计算")
    print("=" * 60)

    try:
        from src.core.apf_filter import APFCore

        # 创建 APF 核心
        apf = APFCore(
            attractive_gain=1.0,
            repulsive_gain=0.5,
            influence_distance=0.1,
            max_force=10.0
        )

        # 测试引力计算
        current_pos = np.array([0.0, 0.0, 0.0])
        target_pos = np.array([1.0, 0.0, 0.0])

        attractive_force = apf.compute_attractive_force(current_pos, target_pos)
        print(f"✅ 引力计算: {attractive_force}")
        assert attractive_force[0] > 0  # X 方向应该有正向力

        # 测试斥力计算
        obstacle_pos = [np.array([0.05, 0.0, 0.0])]  # 很近的障碍物
        repulsive_force = apf.compute_repulsive_force(current_pos, obstacle_pos)
        print(f"✅ 斥力计算: {repulsive_force}")
        assert repulsive_force[0] < 0  # X 方向应该有负向力（远离障碍物）

        # 测试总力计算
        total_force = apf.compute_total_force(current_pos, target_pos, obstacle_pos)
        print(f"✅ 总力计算: {total_force}")

        return True

    except Exception as e:
        print(f"❌ APF 核心测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("VIST 滤波器架构测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("导入滤波器模块", test_filter_imports()))
    results.append(("导入核心模块", test_core_modules()))
    results.append(("工厂模式", test_factory_pattern()))
    results.append(("GELLO 滤波器", test_gello_filter()))
    results.append(("FSM 核心", test_fsm_core()))
    results.append(("APF 核心", test_apf_core()))

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:20s} {status}")

    total = len(results)
    passed = sum(1 for _, r in results if r)

    print("\n" + "=" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    print("=" * 60)

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)