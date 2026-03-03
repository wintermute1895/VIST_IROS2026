#!/usr/bin/env python3
"""
Performance benchmark for VIST Kalman Filter optimizations.
Validates that update() method achieves 3-5ms target latency.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add ROS2 workspace to path
sys.path.insert(0, str(Path(__file__).parent / "ros2_ws" / "src"))

from config.config_loader import VISTConfig
from core.vist_kalman_filter import VISTKalmanFilter
from core.ik_solver import PinocchioIKSolver


def benchmark_update_performance(num_iterations=100):
    """Benchmark the update() method performance."""

    # Load configuration
    config_path = Path(__file__).parent / "config" / "system_config.yaml"
    config = VISTConfig(config_path)

    # Initialize IK solver
    urdf_path = Path(__file__).parent / "ros2_ws" / "src" / "vist_description" / "urdf" / "lkls73_o2_dual_arm_description.urdf"
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # Initialize filter
    filter_node = VISTKalmanFilter(ik_solver, config)

    # Prepare realistic test data
    num_joints = 7
    shadow_joints = np.array([0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0])

    # Target pose (realistic end-effector pose)
    target_pose = np.eye(4)
    target_pose[:3, 3] = [0.5, 0.0, 0.3]  # Position

    # Warm-up runs (to ensure caching is active)
    print("Warming up (10 iterations)...")
    for _ in range(10):
        filter_node.update(shadow_joints, target_pose)

    # Benchmark runs
    print(f"\nBenchmarking update() performance ({num_iterations} iterations)...")
    timings = []

    for i in range(num_iterations):
        # Add small variations to test realistic conditions
        shadow_joints_var = shadow_joints + np.random.randn(num_joints) * 0.001

        start_time = time.perf_counter()
        filter_node.update(shadow_joints_var, target_pose)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000
        timings.append(elapsed_ms)

    # Statistical analysis
    timings = np.array(timings)
    mean_time = np.mean(timings)
    median_time = np.median(timings)
    std_time = np.std(timings)
    min_time = np.min(timings)
    max_time = np.max(timings)
    p95_time = np.percentile(timings, 95)
    p99_time = np.percentile(timings, 99)

    # Results
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("="*60)
    print(f"Mean time:      {mean_time:.3f} ms")
    print(f"Median time:    {median_time:.3f} ms")
    print(f"Std deviation:  {std_time:.3f} ms")
    print(f"Min time:       {min_time:.3f} ms")
    print(f"Max time:       {max_time:.3f} ms")
    print(f"95th percentile: {p95_time:.3f} ms")
    print(f"99th percentile: {p99_time:.3f} ms")
    print("="*60)

    # Performance evaluation
    target_min = 3.0  # ms
    target_max = 5.0  # ms
    acceptable_max = 8.0  # ms (with some margin)

    print("\nPERFORMANCE EVALUATION:")
    if mean_time <= target_max:
        print(f"✓ EXCELLENT: Mean time {mean_time:.3f}ms is within target range ({target_min}-{target_max}ms)")
    elif mean_time <= acceptable_max:
        print(f"✓ GOOD: Mean time {mean_time:.3f}ms is acceptable (target: {target_min}-{target_max}ms)")
    else:
        print(f"✗ NEEDS IMPROVEMENT: Mean time {mean_time:.3f}ms exceeds acceptable range")

    if p95_time <= acceptable_max:
        print(f"✓ 95th percentile {p95_time:.3f}ms is acceptable")
    else:
        print(f"✗ 95th percentile {p95_time:.3f}ms is too high")

    # Control loop frequency analysis
    max_freq_hz = 1000.0 / mean_time
    target_freq_hz = 80.0
    print(f"\nCONTROL LOOP ANALYSIS:")
    print(f"Maximum sustainable frequency: {max_freq_hz:.1f} Hz")
    print(f"Target frequency: {target_freq_hz:.1f} Hz")
    if max_freq_hz >= target_freq_hz * 1.5:
        print(f"✓ EXCELLENT: {max_freq_hz/target_freq_hz:.1f}x headroom for {target_freq_hz}Hz control")
    elif max_freq_hz >= target_freq_hz:
        print(f"✓ ADEQUATE: Can sustain {target_freq_hz}Hz control")
    else:
        print(f"✗ INSUFFICIENT: Cannot sustain {target_freq_hz}Hz control")

    return timings


def test_cache_effectiveness():
    """Test that kinematics caching is working correctly."""
    print("\n" + "="*60)
    print("CACHE EFFECTIVENESS TEST")
    print("="*60)

    config_path = Path(__file__).parent / "config" / "system_config.yaml"
    config = VISTConfig(config_path)

    # Initialize IK solver
    urdf_path = Path(__file__).parent / "ros2_ws" / "src" / "vist_description" / "urdf" / "lkls73_o2_dual_arm_description.urdf"
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    filter_node = VISTKalmanFilter(ik_solver, config)

    shadow_joints = np.array([0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0])
    target_pose = np.eye(4)
    target_pose[:3, 3] = [0.5, 0.0, 0.3]

    # First call (cache miss)
    start = time.perf_counter()
    filter_node.update(shadow_joints, target_pose)
    first_call_ms = (time.perf_counter() - start) * 1000

    # Second call with same joints (cache hit)
    start = time.perf_counter()
    filter_node.update(shadow_joints, target_pose)
    second_call_ms = (time.perf_counter() - start) * 1000

    # Third call with different joints (cache miss)
    shadow_joints_new = shadow_joints + 0.1
    start = time.perf_counter()
    filter_node.update(shadow_joints_new, target_pose)
    third_call_ms = (time.perf_counter() - start) * 1000

    print(f"First call (cache miss):  {first_call_ms:.3f} ms")
    print(f"Second call (cache hit):  {second_call_ms:.3f} ms")
    print(f"Third call (cache miss):  {third_call_ms:.3f} ms")

    if second_call_ms < first_call_ms * 0.8:
        print(f"✓ Cache is effective: {(1 - second_call_ms/first_call_ms)*100:.1f}% speedup")
    else:
        print(f"⚠ Cache may not be working optimally")


if __name__ == "__main__":
    print("VIST Kalman Filter Performance Benchmark")
    print("Testing optimizations: CSV logging disabled, kinematics caching,")
    print("diagonal matrix inversion, flush=True removed\n")

    # Run cache effectiveness test
    test_cache_effectiveness()

    # Run main benchmark
    timings = benchmark_update_performance(num_iterations=100)

    print("\n" + "="*60)
    print("Benchmark complete!")
    print("="*60)
