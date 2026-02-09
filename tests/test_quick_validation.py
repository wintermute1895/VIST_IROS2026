"""
VIST 快速验证脚本

快速验证算法设计的关键特性，无需可视化。

验证内容：
1. 零速死区是否有效
2. 迟滞逻辑是否消除抖动
3. 冲突检测是否准确
4. 紧急退出是否及时

Author: VIST Team
Date: 2026-02-09
"""

import numpy as np
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.intent_detector import (
    EnhancedIntentDetector,
    IntentState,
    compute_human_command,
    compute_algorithm_expectation
)


def test_zero_velocity_deadband():
    """测试零速死区"""
    print("\n" + "="*60)
    print("测试 1: 零速死区 (Zero-Velocity Deadband)")
    print("="*60)

    detector = EnhancedIntentDetector()
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    # 测试极低速度（应该返回 β=0）
    human_cmd = np.array([0.001, 0.0, 0.0])  # 1mm/s（低于 5mm/s 死区）
    algo_exp = np.array([-1.0, 0.0, 0.0])  # 完全相反方向

    beta = detector._compute_conflict(human_cmd, algo_exp, 0.001)

    print(f"人类指令: {human_cmd} (速度: 1mm/s)")
    print(f"算法期望: {algo_exp}")
    print(f"β (冲突因子): {beta:.3f}")

    if beta == 0.0:
        print("✅ PASSED: 零速死区有效，低速时不计算冲突")
    else:
        print(f"❌ FAILED: 预期 β=0，实际 β={beta}")

    return beta == 0.0


def test_hysteresis_logic():
    """测试迟滞逻辑"""
    print("\n" + "="*60)
    print("测试 2: 迟滞逻辑 (Hysteresis)")
    print("="*60)

    detector = EnhancedIntentDetector()

    # 场景：从远处接近，穿过边界，然后返回
    test_distances = [
        (0.06, "远离（6cm）"),
        (0.05, "边界（5cm）"),
        (0.044, "进入（4.4cm）- 应该切换到 VISUAL_ADMITTANCE"),
        (0.05, "返回边界（5cm）- 应该保持 VISUAL_ADMITTANCE"),
        (0.056, "远离（5.6cm）- 应该切换回 APPROACHING")
    ]

    results = []
    for distance, desc in test_distances:
        result = detector.detect_intent(
            distance=distance,
            velocity=0.01,
            human_command=np.array([1.0, 0.0, 0.0]),
            algorithm_expectation=np.array([1.0, 0.0, 0.0]),
            alignment_error=distance
        )
        state = result.state.value
        results.append((distance, state))
        print(f"{desc:50s} → State: {state}")

    # 验证迟滞逻辑
    expected_states = [
        'approaching',
        'approaching',
        'visual_admittance',
        'visual_admittance',  # 关键：应该保持，不应该切回
        'approaching'
    ]

    success = all(r[1] == e for r, e in zip(results, expected_states))

    if success:
        print("✅ PASSED: 迟滞逻辑有效，消除边界抖动")
    else:
        print("❌ FAILED: 迟滞逻辑失效")
        for (d, s), e in zip(results, expected_states):
            if s != e:
                print(f"  距离 {d*100:.1f}cm: 预期 {e}, 实际 {s}")

    return success


def test_conflict_detection_accuracy():
    """测试冲突检测准确性"""
    print("\n" + "="*60)
    print("测试 3: 冲突检测准确性")
    print("="*60)

    detector = EnhancedIntentDetector()
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    test_cases = [
        # (human_cmd, algo_exp, velocity, expected_beta_range, description)
        (np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]), 0.02, (0.0, 0.1), "方向一致"),
        (np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), 0.05, (0.9, 1.0), "方向相反"),
        (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), 0.02, (0.15, 0.25), "夹角 90°"),
        (np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), 0.001, (0.0, 0.1), "方向相反但速度慢"),
    ]

    all_passed = True
    for human_cmd, algo_exp, velocity, (min_beta, max_beta), desc in test_cases:
        beta = detector._compute_conflict(human_cmd, algo_exp, velocity)
        passed = min_beta <= beta <= max_beta

        status = "✅" if passed else "❌"
        print(f"{status} {desc:20s} | β={beta:.3f} | 预期范围: [{min_beta:.1f}, {max_beta:.1f}]")

        if not passed:
            all_passed = False

    if all_passed:
        print("✅ PASSED: 冲突检测准确")
    else:
        print("❌ FAILED: 部分冲突检测不准确")

    return all_passed


def test_emergency_pullback():
    """测试紧急退出机制"""
    print("\n" + "="*60)
    print("测试 4: 紧急退出机制")
    print("="*60)

    detector = EnhancedIntentDetector()

    # 模拟插入阶段
    detector.current_state = IntentState.CONSTRAINED_INSERTION

    # 测试正常插入（不应该触发紧急退出）
    result1 = detector.detect_intent(
        distance=0.01,
        velocity=0.005,  # 0.5cm/s（慢速）
        human_command=np.array([0.0, 0.0, 1.0]),
        algorithm_expectation=np.array([0.0, 0.0, 1.0]),
        alignment_error=0.001,
        current_depth=0.005
    )

    print(f"正常插入: State={result1.state.value}")
    test1_passed = result1.state == IntentState.CONSTRAINED_INSERTION

    # 重置状态
    detector.current_state = IntentState.CONSTRAINED_INSERTION

    # 测试紧急回拉（应该触发紧急退出）
    result2 = detector.detect_intent(
        distance=0.01,
        velocity=0.04,  # 4cm/s（高速）
        human_command=np.array([0.0, 0.0, -1.0]),  # 反向
        algorithm_expectation=np.array([0.0, 0.0, 1.0]),  # 正向
        alignment_error=0.001,
        current_depth=0.005
    )

    print(f"紧急回拉: State={result2.state.value}")
    test2_passed = result2.state == IntentState.CORRECTION_OVERRIDE

    if test1_passed and test2_passed:
        print("✅ PASSED: 紧急退出机制有效")
    else:
        print("❌ FAILED: 紧急退出机制失效")
        if not test1_passed:
            print("  正常插入时不应该退出")
        if not test2_passed:
            print("  紧急回拉时应该退出")

    return test1_passed and test2_passed


def test_alpha_effective_calculation():
    """测试有效意图因子计算"""
    print("\n" + "="*60)
    print("测试 5: 有效意图因子计算 (α_eff = α × (1-β))")
    print("="*60)

    detector = EnhancedIntentDetector()
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    test_cases = [
        # (alpha, beta, expected_alpha_eff, description)
        (1.0, 0.0, 1.0, "无冲突"),
        (1.0, 0.5, 0.5, "中等冲突"),
        (1.0, 0.9, 0.1, "强烈冲突"),
        (1.0, 1.0, 0.0, "完全冲突"),
    ]

    all_passed = True
    for alpha, beta, expected, desc in test_cases:
        # 模拟不同的冲突情况
        if beta == 0.0:
            human_cmd = np.array([1.0, 0.0, 0.0])
            algo_exp = np.array([1.0, 0.0, 0.0])
            velocity = 0.02
        elif beta == 1.0:
            human_cmd = np.array([1.0, 0.0, 0.0])
            algo_exp = np.array([-1.0, 0.0, 0.0])
            velocity = 0.05
        else:
            # 通过调整夹角和速度来模拟中等冲突
            angle = np.arccos(1 - 2*beta)  # 反推夹角
            human_cmd = np.array([1.0, 0.0, 0.0])
            algo_exp = np.array([np.cos(angle), np.sin(angle), 0.0])
            velocity = 0.05

        result = detector.detect_intent(
            distance=0.03,
            velocity=velocity,
            human_command=human_cmd,
            algorithm_expectation=algo_exp,
            alignment_error=0.005
        )

        alpha_eff = result.alpha_effective
        error = abs(alpha_eff - expected)
        passed = error < 0.15  # 允许 15% 误差

        status = "✅" if passed else "❌"
        print(f"{status} {desc:15s} | α={alpha:.1f}, β={result.beta:.2f} → α_eff={alpha_eff:.2f} (预期: {expected:.2f})")

        if not passed:
            all_passed = False

    if all_passed:
        print("✅ PASSED: 有效意图因子计算正确")
    else:
        print("❌ FAILED: 部分计算不准确")

    return all_passed


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("VIST 快速验证测试")
    print("="*60)

    results = {
        "零速死区": test_zero_velocity_deadband(),
        "迟滞逻辑": test_hysteresis_logic(),
        "冲突检测": test_conflict_detection_accuracy(),
        "紧急退出": test_emergency_pullback(),
        "有效意图因子": test_alpha_effective_calculation()
    }

    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:15s}: {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！算法设计符合预期。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要修正。")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
