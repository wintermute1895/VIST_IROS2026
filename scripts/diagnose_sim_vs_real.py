#!/usr/bin/env python3
"""
诊断仿真和真机控制差异的脚本
"""

import os
import sys
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config

def main():
    print("=" * 80)
    print("🔍 仿真 vs 真机控制差异诊断")
    print("=" * 80)

    # 加载配置
    config = get_config()

    print("\n📋 关键配置参数:")
    print(f"  IK 策略: {config.ik_strategy}")
    print(f"  关节方向: {config.robot_joint_directions}")
    print(f"  关节偏移: {config.robot_joint_offsets}")

    print("\n🔬 VIST 配置:")
    print(f"  启用: {config.vist_enabled}")
    print(f"  几何求解器启用: {config.vist_geometric_solver_enabled}")
    print(f"  几何求解器信任权重: {config.vist_geometric_solver_trust_weight}")
    print(f"  禁用微分IK: {config.vist_geometric_solver_disable_differential_ik}")

    print("\n⚙️  控制参数:")
    print(f"  控制频率: {1.0/config.control_dt:.1f} Hz")
    print(f"  最大关节速度: {config.max_joint_velocity} rad/s")
    print(f"  最大关节加速度: {config.max_joint_acceleration} rad/s²")

    print("\n🤖 硬件参数:")
    if hasattr(config, 'robot_hardware_move_joint_speed'):
        print(f"  move_joint 速度: {config.robot_hardware_move_joint_speed} rad/s")
        print(f"  move_joint 加速度: {config.robot_hardware_move_joint_accel} rad/s²")
    else:
        print("  未配置硬件参数")

    print("\n🎯 VIST Kalman Filter 参数:")
    if hasattr(config, 'vist_simulation_use_parameter_override'):
        print(f"  仿真参数覆盖: {config.vist_simulation_use_parameter_override}")

    # 检查参数覆盖文件
    override_file = os.path.expanduser("~/.vist_parameter_override.json")
    if os.path.exists(override_file):
        import json
        with open(override_file, 'r') as f:
            override_data = json.load(f)
        print(f"\n📄 参数覆盖文件存在: {override_file}")
        print(f"  内容: {override_data}")
    else:
        print(f"\n⚠️  参数覆盖文件不存在: {override_file}")

    print("\n" + "=" * 80)
    print("💡 可能的差异原因:")
    print("=" * 80)

    issues = []

    # 检查1: 关节方向
    expected_directions = np.array([-1, 1, -1, 1, 1, 1, 1])
    if not np.array_equal(config.robot_joint_directions, expected_directions):
        issues.append(f"⚠️  关节方向不匹配: 当前={config.robot_joint_directions}, 期望={expected_directions}")

    # 检查2: 速度限制
    if config.max_joint_velocity < 0.5:
        issues.append(f"⚠️  关节速度限制较低: {config.max_joint_velocity} rad/s (可能导致运动缓慢)")

    # 检查3: 硬件速度限制
    if hasattr(config, 'robot_hardware_move_joint_speed') and config.robot_hardware_move_joint_speed < 0.2:
        issues.append(f"⚠️  硬件速度限制较低: {config.robot_hardware_move_joint_speed} rad/s")

    # 检查4: 几何求解器
    if not config.vist_geometric_solver_enabled:
        issues.append("⚠️  几何求解器未启用（仿真可能已启用）")

    if issues:
        for issue in issues:
            print(f"\n{issue}")
    else:
        print("\n✅ 未发现明显配置问题")

    print("\n" + "=" * 80)
    print("🔧 建议:")
    print("=" * 80)
    print("1. 确认仿真和真机使用相同的配置文件")
    print("2. 检查真机的安全限制是否过于严格")
    print("3. 对比仿真和真机的关节角度输出")
    print("4. 检查真机的初始位置是否和仿真一致")
    print("5. 确认视觉节点发送的数据格式一致")

if __name__ == "__main__":
    main()