#!/usr/bin/env python3
"""
测试腕部控制模式

测试三种腕部控制模式：
1. full_dof: 全自由度欧拉角分解
2. constrained_horizontal: 约束水平模式（J5锁定，J6保持水平）
3. wrist_locked: 腕部锁定模式（J5-J7全部锁定）

使用方法：
    python scripts/test_wrist_control_modes.py
"""

import numpy as np
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.core.ik_solver import PinocchioIKSolver
from src.core.geometric_arm_solver import GeometricArmSolver


def test_wrist_control_mode(mode_name):
    """
    测试指定的腕部控制模式

    Args:
        mode_name: 控制模式名称 ("full_dof", "constrained_horizontal", "wrist_locked")
    """
    print(f"\n{'='*60}")
    print(f"测试模式: {mode_name}")
    print(f"{'='*60}")

    # 1. 加载配置
    config = get_config()

    # 临时修改配置以测试不同模式
    original_mode = config._config.get('vist_kalman', {}).get('geometric_solver', {}).get('wrist_control_mode', 'full_dof')
    config._config.setdefault('vist_kalman', {}).setdefault('geometric_solver', {})['wrist_control_mode'] = mode_name

    # 2. 初始化 IK 求解器
    urdf_path = project_root / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 3. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id,
        config=config
    )

    # 4. 定义测试数据
    shoulder_pos = np.array([0.0, 0.0, 0.0])  # 肩部在原点
    elbow_pos = np.array([0.2, 0.1, 0.1])     # 肘部在前方
    wrist_pos = np.array([0.3, 0.15, 0.2])    # 腕部在更前方

    # 目标姿态：末端指向前方，稍微向右旋转30度
    from scipy.spatial.transform import Rotation
    target_rot = Rotation.from_euler('z', 30, degrees=True)
    target_quat = target_rot.as_quat()  # [x, y, z, w]

    print(f"\n📍 测试数据:")
    print(f"   肩部位置: {shoulder_pos}")
    print(f"   肘部位置: {elbow_pos}")
    print(f"   腕部位置: {wrist_pos}")
    print(f"   目标姿态 (四元数): {target_quat}")
    print(f"   目标姿态 (欧拉角, 度): {target_rot.as_euler('xyz', degrees=True)}")

    # 5. 求解关节角度
    q_solution = geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos, target_quat)

    print(f"\n📊 求解结果:")
    print(f"   关节角度 (度): {np.degrees(q_solution)}")
    print(f"   关节角度 (弧度): {q_solution}")

    # 分解显示
    print(f"\n   臂部关节 (J1-J4):")
    for i in range(4):
        print(f"      J{i+1}: {np.degrees(q_solution[i]):7.2f}° ({q_solution[i]:7.4f} rad)")

    print(f"\n   腕部关节 (J5-J7):")
    for i in range(4, 7):
        print(f"      J{i+1}: {np.degrees(q_solution[i]):7.2f}° ({q_solution[i]:7.4f} rad)")

    # 6. 验证结果
    print(f"\n✅ 模式特征验证:")
    if mode_name == "wrist_locked":
        is_locked = np.allclose(q_solution[4:7], 0.0, atol=1e-6)
        print(f"   J5-J7 全部锁定为0: {'✅ 通过' if is_locked else '❌ 失败'}")

    elif mode_name == "constrained_horizontal":
        is_j5_locked = np.isclose(q_solution[4], 0.0, atol=1e-6)
        is_j6_compensating = np.isclose(q_solution[5], -q_solution[3], atol=0.1)
        print(f"   J5 锁定为0: {'✅ 通过' if is_j5_locked else '❌ 失败'}")
        print(f"   J6 补偿J4 (q6 ≈ -q4): {'✅ 通过' if is_j6_compensating else '❌ 失败'}")
        print(f"      q4 = {np.degrees(q_solution[3]):7.2f}°, q6 = {np.degrees(q_solution[5]):7.2f}°")

    elif mode_name == "full_dof":
        has_wrist_motion = not np.allclose(q_solution[4:7], 0.0, atol=0.1)
        print(f"   腕部关节有运动: {'✅ 通过' if has_wrist_motion else '⚠️  警告（可能目标姿态接近零位）'}")

    # 恢复原始配置
    config._config['vist_kalman']['geometric_solver']['wrist_control_mode'] = original_mode

    return q_solution


def main():
    """主函数：测试所有控制模式"""
    print("🧪 腕部控制模式测试")
    print("="*60)

    modes = ["full_dof", "constrained_horizontal", "wrist_locked"]
    results = {}

    for mode in modes:
        try:
            q_solution = test_wrist_control_mode(mode)
            results[mode] = q_solution
        except Exception as e:
            print(f"\n❌ 模式 {mode} 测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 对比结果
    print(f"\n{'='*60}")
    print("📊 模式对比")
    print(f"{'='*60}")

    if len(results) > 1:
        print(f"\n{'关节':<10} {'full_dof':<15} {'constrained':<15} {'locked':<15}")
        print("-" * 60)

        for i in range(7):
            joint_name = f"J{i+1}"
            values = []
            for mode in modes:
                if mode in results:
                    angle_deg = np.degrees(results[mode][i])
                    values.append(f"{angle_deg:7.2f}°")
                else:
                    values.append("N/A")

            print(f"{joint_name:<10} {values[0]:<15} {values[1]:<15} {values[2]:<15}")

    print(f"\n✅ 测试完成！")
    print(f"\n💡 使用建议:")
    print(f"   - full_dof: 通用遥操作任务，需要完整的姿态控制")
    print(f"   - constrained_horizontal: 桌面操作任务（插入、抓取），保持末端水平")
    print(f"   - wrist_locked: 简单的位置追踪任务，不需要姿态控制")


if __name__ == "__main__":
    main()
