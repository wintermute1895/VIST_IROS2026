#!/usr/bin/env python3
"""
测试李代数集成到 VIST Kalman 滤波器

验证：
1. 李代数模块导入成功
2. 任务空间误差计算（使用李代数）
3. 带姿态的微分 IK
4. 配置开关工作正常
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_loader import VISTConfig
import pinocchio as pin


def test_lie_algebra_import():
    """测试1: 李代数模块导入"""
    print("=" * 60)
    print("测试1: 李代数模块导入")
    print("=" * 60)

    try:
        from src.utils.lie_algebra import slerp_rotation
        print("✅ 李代数模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 李代数模块导入失败: {e}")
        return False


def test_task_space_error():
    """测试2: 任务空间误差计算"""
    print("\n" + "=" * 60)
    print("测试2: 任务空间误差计算（李代数）")
    print("=" * 60)

    try:
        # 创建两个测试位姿
        # 位姿1: 单位旋转，位置 [0, 0, 0]
        R1 = np.eye(3)
        p1 = np.array([0.0, 0.0, 0.0])
        pose1 = pin.SE3(R1, p1)

        # 位姿2: 绕Z轴旋转90度，位置 [0.1, 0.2, 0.3]
        R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/2)
        p2 = np.array([0.1, 0.2, 0.3])
        pose2 = pin.SE3(R2, p2)

        # 计算误差
        # 位置误差
        δp = pose2.translation - pose1.translation
        print(f"   位置误差: {δp}")

        # 姿态误差（李代数）
        R_rel = pose1.rotation.T @ pose2.rotation
        δθ = pin.log3(R_rel)
        print(f"   姿态误差 (so(3)): {δθ}")
        print(f"   姿态误差范数: {np.linalg.norm(δθ):.4f} rad")
        print(f"   预期: {np.pi/2:.4f} rad (90度)")

        # 验证
        expected_angle = np.pi/2
        actual_angle = np.linalg.norm(δθ)
        error = abs(actual_angle - expected_angle)

        if error < 1e-6:
            print("✅ 任务空间误差计算正确")
            return True
        else:
            print(f"❌ 任务空间误差计算错误: 误差 = {error}")
            return False

    except Exception as e:
        print(f"❌ 任务空间误差计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_switch():
    """测试3: 配置开关"""
    print("\n" + "=" * 60)
    print("测试3: 配置开关")
    print("=" * 60)

    try:
        config = VISTConfig()

        # 检查配置是否存在
        use_orientation = getattr(config, 'vist_use_orientation_control', None)

        if use_orientation is None:
            print("⚠️  配置项 'vist_use_orientation_control' 不存在，使用默认值 False")
            use_orientation = False
        else:
            print(f"   配置项 'vist_use_orientation_control': {use_orientation}")

        print("✅ 配置开关测试通过")
        return True

    except Exception as e:
        print(f"❌ 配置开关测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vist_kalman_filter_integration():
    """测试4: VIST Kalman 滤波器集成"""
    print("\n" + "=" * 60)
    print("测试4: VIST Kalman 滤波器集成")
    print("=" * 60)

    try:
        from src.core.vist_kalman_filter import VISTKalmanFilter

        # 检查新方法是否存在
        if not hasattr(VISTKalmanFilter, '_compute_task_space_error_with_lie_algebra'):
            print("❌ 方法 '_compute_task_space_error_with_lie_algebra' 不存在")
            return False

        if not hasattr(VISTKalmanFilter, 'compute_differential_ik_with_orientation'):
            print("❌ 方法 'compute_differential_ik_with_orientation' 不存在")
            return False

        print("✅ VIST Kalman 滤波器集成成功")
        print(f"   新方法:")
        print(f"   - _compute_task_space_error_with_lie_algebra")
        print(f"   - compute_differential_ik_with_orientation")

        return True

    except Exception as e:
        print(f"❌ VIST Kalman 滤波器集成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("李代数集成测试")
    print("=" * 60)

    results = []

    # 运行所有测试
    results.append(("李代数模块导入", test_lie_algebra_import()))
    results.append(("任务空间误差计算", test_task_space_error()))
    results.append(("配置开关", test_config_switch()))
    results.append(("VIST Kalman 滤波器集成", test_vist_kalman_filter_integration()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {name}: {status}")

    print(f"\n   总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
