#!/usr/bin/env python3
"""
检查 VIST 的 dt 计算是否正确
"""

import sys
import time
from pathlib import Path

# Add ROS2 workspace to path
sys.path.insert(0, str(Path(__file__).parent / "ros2_ws" / "src"))

from config.config_loader import VISTConfig
from core.vist_kalman_filter import VISTKalmanFilter
from core.ik_solver import PinocchioIKSolver
import numpy as np

def test_dt_calculation():
    """测试 dt 计算是否正确"""

    print("=" * 60)
    print("VIST dt 计算诊断")
    print("=" * 60)
    print()

    # 加载配置
    config_path = Path(__file__).parent / "config" / "system_config.yaml"
    config = VISTConfig(config_path)

    print(f"1. 配置的 dt: {config.vist_filter_system_dt}s ({1/config.vist_filter_system_dt:.1f}Hz)")
    print()

    # 初始化 IK solver
    urdf_path = Path(__file__).parent / "ros2_ws" / "src" / "vist_description" / "urdf" / "lkls73_o2_dual_arm_description.urdf"
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 初始化 VIST filter
    vist_filter = VISTKalmanFilter(ik_solver, config)

    print(f"2. VIST 内部 dt: {vist_filter.dt}s")
    print()

    # 测试实际更新频率
    print("3. 测试实际更新频率 (100次迭代)...")

    shadow_joints = np.array([0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0])
    target_pose = np.eye(4)
    target_pose[:3, 3] = [0.5, 0.0, 0.3]

    # 预热
    for _ in range(10):
        vist_filter.update(shadow_joints, target_pose)

    # 测试
    dts = []
    last_time = time.time()

    for i in range(100):
        vist_filter.update(shadow_joints, target_pose)
        current_time = time.time()
        dt = current_time - last_time
        dts.append(dt)
        last_time = current_time

    dts = np.array(dts)

    print(f"   平均 dt: {np.mean(dts)*1000:.3f}ms ({1/np.mean(dts):.1f}Hz)")
    print(f"   最小 dt: {np.min(dts)*1000:.3f}ms")
    print(f"   最大 dt: {np.max(dts)*1000:.3f}ms")
    print(f"   标准差: {np.std(dts)*1000:.3f}ms")
    print()

    # 检查 F 矩阵
    print("4. 检查 F 矩阵更新...")
    print(f"   F[0, 7] = {vist_filter.F[0, 7]:.6f} (应该等于实际 dt)")
    print()

    # 诊断
    print("5. 诊断结果")
    print("-" * 60)

    config_dt = config.vist_filter_system_dt
    actual_dt = np.mean(dts)

    if abs(actual_dt - config_dt) / config_dt > 0.2:  # 超过20%偏差
        print(f"⚠️  警告: 实际 dt ({actual_dt*1000:.3f}ms) 与配置 dt ({config_dt*1000:.3f}ms) 偏差过大")
        print(f"   偏差: {abs(actual_dt - config_dt)/config_dt*100:.1f}%")
        print()
        print("   可能原因:")
        print("   1. 控制循环频率不稳定")
        print("   2. update() 函数耗时过长")
        print("   3. 系统负载过高")
        print()
        print("   影响:")
        print("   - F 矩阵不准确")
        print("   - 状态预测错误")
        print("   - 可能导致震荡")
        print()
        print("   建议:")
        print("   - 使用动态 dt 更新（已实现）")
        print("   - 优化 update() 性能")
    else:
        print(f"✓ dt 计算正常")
        print(f"  配置 dt: {config_dt*1000:.3f}ms")
        print(f"  实际 dt: {actual_dt*1000:.3f}ms")
        print(f"  偏差: {abs(actual_dt - config_dt)/config_dt*100:.1f}%")

    print()

    # 检查 dt 波动
    if np.std(dts) / np.mean(dts) > 0.1:  # 变异系数 > 10%
        print(f"⚠️  警告: dt 波动过大")
        print(f"   变异系数: {np.std(dts) / np.mean(dts) * 100:.1f}%")
        print(f"   范围: {np.min(dts)*1000:.3f}ms - {np.max(dts)*1000:.3f}ms")
        print()
        print("   影响:")
        print("   - 固定 F 矩阵会导致预测误差")
        print("   - 累积误差可能导致震荡")
        print()
        print("   建议:")
        print("   - 已实现动态 dt 更新（修复问题2）")
        print("   - 检查系统负载")
    else:
        print(f"✓ dt 波动正常")
        print(f"  变异系数: {np.std(dts) / np.mean(dts) * 100:.1f}%")

    print()
    print("=" * 60)

if __name__ == "__main__":
    test_dt_calculation()