"""
Unit tests for Enhanced Intent Detector with Conflict Detection

Tests the core functionality of the β term conflict detection and
compliant takeover mechanism.

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


def test_conflict_detection_no_conflict():
    """测试无冲突情况（方向一致）"""
    print("\n" + "="*60)
    print("Test 1: No Conflict (Same Direction)")
    print("="*60)

    detector = EnhancedIntentDetector()

    # 人类和算法方向一致
    human_cmd = np.array([1.0, 0.0, 0.0])
    algo_exp = np.array([1.0, 0.0, 0.0])
    velocity = 0.01  # 1cm/s

    beta = detector._compute_conflict(human_cmd, algo_exp, velocity)

    print(f"Human command: {human_cmd}")
    print(f"Algorithm expectation: {algo_exp}")
    print(f"Velocity: {velocity*100:.1f} cm/s")
    print(f"β (conflict): {beta:.3f}")

    assert beta == 0.0, f"Expected β=0, got β={beta}"
    print("✅ PASSED: No conflict detected when directions align")


def test_conflict_detection_full_conflict():
    """测试完全冲突情况（方向相反）"""
    print("\n" + "="*60)
    print("Test 2: Full Conflict (Opposite Direction)")
    print("="*60)

    detector = EnhancedIntentDetector()
    # 设置为算法主导阶段（才会检测冲突）
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    # 人类和算法方向相反
    human_cmd = np.array([1.0, 0.0, 0.0])
    algo_exp = np.array([-1.0, 0.0, 0.0])
    velocity = 0.05  # 5cm/s（高速）

    beta = detector._compute_conflict(human_cmd, algo_exp, velocity)

    print(f"Human command: {human_cmd}")
    print(f"Algorithm expectation: {algo_exp}")
    print(f"Velocity: {velocity*100:.1f} cm/s")
    print(f"β (conflict): {beta:.3f}")

    assert beta > 0.8, f"Expected β>0.8, got β={beta}"
    print("✅ PASSED: Strong conflict detected when directions oppose")


def test_conflict_detection_partial_conflict():
    """测试部分冲突情况（夹角 90°）"""
    print("\n" + "="*60)
    print("Test 3: Partial Conflict (90° Angle)")
    print("="*60)

    detector = EnhancedIntentDetector()
    # 设置为算法主导阶段（才会检测冲突）
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    # 人类和算法夹角 90°
    human_cmd = np.array([1.0, 0.0, 0.0])
    algo_exp = np.array([0.0, 1.0, 0.0])
    velocity = 0.02  # 2cm/s（中速）

    beta = detector._compute_conflict(human_cmd, algo_exp, velocity)

    print(f"Human command: {human_cmd}")
    print(f"Algorithm expectation: {algo_exp}")
    print(f"Velocity: {velocity*100:.1f} cm/s")
    print(f"β (conflict): {beta:.3f}")

    assert 0.15 < beta < 0.85, f"Expected 0.15<β<0.85, got β={beta}"
    print("✅ PASSED: Partial conflict detected at 90° angle")


def test_alpha_effective_calculation():
    """测试有效意图因子计算"""
    print("\n" + "="*60)
    print("Test 4: Effective Alpha Calculation")
    print("="*60)

    detector = EnhancedIntentDetector()
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    # 场景 1: 无冲突
    human_cmd = np.array([1.0, 0.0, 0.0])
    algo_exp = np.array([1.0, 0.0, 0.0])

    result = detector.detect_intent(
        distance=0.03,  # 3cm
        velocity=0.01,  # 1cm/s
        human_command=human_cmd,
        algorithm_expectation=algo_exp,
        alignment_error=0.005
    )

    print(f"\nScenario 1: No Conflict")
    print(f"  α (base): {result.alpha:.3f}")
    print(f"  β (conflict): {result.beta:.3f}")
    print(f"  α_eff: {result.alpha_effective:.3f}")

    assert result.alpha_effective == result.alpha, "α_eff should equal α when β=0"
    print("  ✅ α_eff = α when no conflict")

    # 场景 2: 完全冲突
    human_cmd = np.array([1.0, 0.0, 0.0])
    algo_exp = np.array([-1.0, 0.0, 0.0])

    result = detector.detect_intent(
        distance=0.03,
        velocity=0.05,  # 5cm/s（高速）
        human_command=human_cmd,
        algorithm_expectation=algo_exp,
        alignment_error=0.005
    )

    print(f"\nScenario 2: Full Conflict")
    print(f"  α (base): {result.alpha:.3f}")
    print(f"  β (conflict): {result.beta:.3f}")
    print(f"  α_eff: {result.alpha_effective:.3f}")

    assert result.alpha_effective < 0.3, f"α_eff should be low when β is high, got {result.alpha_effective}"
    print("  ✅ α_eff << α when strong conflict")


def test_state_transitions():
    """测试状态转换"""
    print("\n" + "="*60)
    print("Test 5: State Transitions")
    print("="*60)

    detector = EnhancedIntentDetector()

    # 初始状态：APPROACHING
    assert detector.current_state == IntentState.APPROACHING
    print(f"Initial state: {detector.current_state.value}")

    # 接近目标 → VISUAL_ADMITTANCE
    result = detector.detect_intent(
        distance=0.04,  # 4cm（< 5cm）
        velocity=0.01,
        human_command=np.array([1.0, 0.0, 0.0]),
        algorithm_expectation=np.array([1.0, 0.0, 0.0]),
        alignment_error=0.01
    )

    assert detector.current_state == IntentState.VISUAL_ADMITTANCE
    print(f"After approaching: {detector.current_state.value} ✅")

    # 对齐完成 → CONSTRAINED_INSERTION
    result = detector.detect_intent(
        distance=0.001,  # 1mm
        velocity=0.001,
        human_command=np.array([0.0, 0.0, 1.0]),
        algorithm_expectation=np.array([0.0, 0.0, 1.0]),
        alignment_error=0.001  # < 2mm
    )

    assert detector.current_state == IntentState.CONSTRAINED_INSERTION
    print(f"After alignment: {detector.current_state.value} ✅")


def test_compliant_takeover_scenario():
    """测试柔顺接管场景"""
    print("\n" + "="*60)
    print("Test 6: Compliant Takeover Scenario")
    print("="*60)

    detector = EnhancedIntentDetector()
    detector.current_state = IntentState.VISUAL_ADMITTANCE

    print("\n场景：算法主导对齐，但人类发现位置偏离，开始微调")

    # 步骤 1: 算法主导，无冲突
    print("\n步骤 1: 算法主导对齐（无冲突）")
    result = detector.detect_intent(
        distance=0.03,
        velocity=0.01,
        human_command=np.array([1.0, 0.0, 0.0]),
        algorithm_expectation=np.array([1.0, 0.0, 0.0]),
        alignment_error=0.005
    )
    print(f"  α_eff: {result.alpha_effective:.3f} (算法主导)")

    # 步骤 2: 人类开始微调（检测到冲突）
    print("\n步骤 2: 人类开始微调（检测到冲突）")
    result = detector.detect_intent(
        distance=0.03,
        velocity=0.04,  # 4cm/s（较高速度）
        human_command=np.array([0.0, 1.0, 0.0]),  # 人类朝 Y 方向
        algorithm_expectation=np.array([1.0, 0.0, 0.0]),  # 算法朝 X 方向
        alignment_error=0.005
    )
    print(f"  β: {result.beta:.3f} (检测到冲突)")
    print(f"  α_eff: {result.alpha_effective:.3f} (降低算法权重)")
    assert result.beta > 0.2, "应该检测到冲突"
    assert result.alpha_effective < result.alpha, "α_eff 应该降低"

    # 步骤 3: 人类完成微调（冲突消失）
    print("\n步骤 3: 人类完成微调（冲突消失）")
    result = detector.detect_intent(
        distance=0.03,
        velocity=0.005,  # 0.5cm/s（慢速）
        human_command=np.array([1.0, 0.0, 0.0]),
        algorithm_expectation=np.array([1.0, 0.0, 0.0]),
        alignment_error=0.005
    )
    print(f"  β: {result.beta:.3f} (冲突消失)")
    print(f"  α_eff: {result.alpha_effective:.3f} (恢复算法主导)")

    print("\n✅ PASSED: Compliant takeover works as expected")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("VIST Enhanced Intent Detector - Unit Tests")
    print("="*60)

    try:
        test_conflict_detection_no_conflict()
        test_conflict_detection_full_conflict()
        test_conflict_detection_partial_conflict()
        test_alpha_effective_calculation()
        test_state_transitions()
        test_compliant_takeover_scenario()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60 + "\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise


if __name__ == "__main__":
    run_all_tests()
