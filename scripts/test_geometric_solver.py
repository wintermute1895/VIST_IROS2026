#!/usr/bin/env python3
"""
测试几何解析臂部求解器

验证三阶段求解方法：
1. 臂部配置求解（q1-q4）
2. 腕部姿态求解（q5-q7）
3. VIST 集成测试

Author: VIST Project
Date: 2026-02-06
"""

import sys
import os
import numpy as np
from scipy.spatial.transform import Rotation

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(project_root, "src"))

from core.ik_solver import PinocchioIKSolver
from core.geometric_arm_solver import GeometricArmSolver
from core.vist_kalman_filter import VISTKalmanFilter
from config.config_loader import get_config


def test_geometric_solver_basic():
    """测试 1: 基础几何求解器功能"""
    print("=" * 60)
    print("测试 1: 基础几何求解器功能")
    print("=" * 60)

    # 1. 加载机器人模型
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 2. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id
    )

    # 3. 定义测试数据（模拟 MediaPipe 检测到的关键点）
    shoulder_pos = np.array([0.0, 0.0, 0.0])  # 肩部在原点
    elbow_pos = np.array([0.2, 0.1, 0.1])     # 肘部在前方
    wrist_pos = np.array([0.3, 0.15, 0.2])    # 腕部在更前方

    print(f"\n🎯 测试数据:")
    print(f"   肩部位置: {shoulder_pos}")
    print(f"   肘部位置: {elbow_pos}")
    print(f"   腕部位置: {wrist_pos}")

    # 4. 求解臂部配置
    try:
        q_solution = geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)

        print(f"\n📊 求解结果:")
        print(f"   关节角度 (度): {np.degrees(q_solution)}")
        print(f"   关节角度 (弧度): {q_solution}")

        # 5. 验证：使用正运动学检查
        q_full = np.zeros(ik_solver.model.nq)
        for i, idx in enumerate(ik_solver.controlled_indices):
            q_full[idx] = q_solution[i]

        import pinocchio as pin
        pin.forwardKinematics(ik_solver.model, ik_solver.data, q_full)
        pin.updateFramePlacements(ik_solver.model, ik_solver.data)
        ee_placement = ik_solver.data.oMf[ik_solver.ee_frame_id]
        actual_wrist_pos = ee_placement.translation

        print(f"\n✅ 验证（正运动学）:")
        print(f"   目标腕部位置: {wrist_pos}")
        print(f"   实际腕部位置: {actual_wrist_pos}")
        print(f"   位置误差: {np.linalg.norm(wrist_pos - actual_wrist_pos)*1000:.2f}mm")

        print("\n✅ 测试 1 通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vist_integration():
    """测试 2: VIST 集成测试"""
    print("\n" + "=" * 60)
    print("测试 2: VIST 集成测试")
    print("=" * 60)

    # 1. 加载配置
    config = get_config()

    # 2. 加载机器人模型
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 3. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id
    )

    # 4. 创建 VIST 滤波器（集成几何求解器）
    vist_filter = VISTKalmanFilter(
        ik_solver=ik_solver,
        config=config,
        geometric_solver=geo_solver
    )

    # 5. 定义测试轨迹（模拟人手运动）
    shoulder_pos = np.array([0.0, 0.0, 0.0])

    # 轨迹 1: 肘部和腕部同时移动
    trajectory = [
        {
            "elbow": np.array([0.2, 0.1, 0.1]),
            "wrist": np.array([0.3, 0.15, 0.2])
        },
        {
            "elbow": np.array([0.22, 0.12, 0.12]),
            "wrist": np.array([0.32, 0.17, 0.22])
        },
        {
            "elbow": np.array([0.24, 0.14, 0.14]),
            "wrist": np.array([0.34, 0.19, 0.24])
        }
    ]

    print(f"\n🎯 测试轨迹: {len(trajectory)} 个点")

    # 6. 执行 VIST 求解
    try:
        for i, point in enumerate(trajectory):
            elbow_pos = point["elbow"]
            wrist_pos = point["wrist"]

            # 使用 VIST 求解（传入肘部位置）
            q_solution, success, error = vist_filter.solve(
                target_pos=wrist_pos,
                elbow_pos=elbow_pos,
                shoulder_pos=shoulder_pos
            )

            print(f"\n📊 点 {i+1}:")
            print(f"   肘部位置: {elbow_pos}")
            print(f"   腕部位置: {wrist_pos}")
            print(f"   求解成功: {success}")
            print(f"   位置误差: {error*1000:.2f}mm")
            print(f"   关节角度 (度): {np.degrees(q_solution)}")

        print("\n✅ 测试 2 通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_comparison():
    """测试 3: 性能对比（几何解析 vs 迭代 IK）"""
    print("\n" + "=" * 60)
    print("测试 3: 性能对比")
    print("=" * 60)

    import time

    # 1. 加载机器人模型
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 2. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id
    )

    # 3. 定义测试数据
    shoulder_pos = np.array([0.0, 0.0, 0.0])
    elbow_pos = np.array([0.2, 0.1, 0.1])
    wrist_pos = np.array([0.3, 0.15, 0.2])

    n_iterations = 100

    # 4. 测试几何解析解
    print(f"\n⏱️ 测试几何解析解 ({n_iterations} 次迭代)...")
    start_time = time.time()
    for _ in range(n_iterations):
        q_geo = geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)
    geo_time = time.time() - start_time
    geo_avg = geo_time / n_iterations * 1000  # ms

    print(f"   总时间: {geo_time:.4f}s")
    print(f"   平均时间: {geo_avg:.4f}ms")
    print(f"   频率: {1000/geo_avg:.1f}Hz")

    # 5. 测试迭代 IK
    print(f"\n⏱️ 测试迭代 IK ({n_iterations} 次迭代)...")
    start_time = time.time()
    for _ in range(n_iterations):
        q_ik, success, error = ik_solver.solve(wrist_pos, max_iter=50)
    ik_time = time.time() - start_time
    ik_avg = ik_time / n_iterations * 1000  # ms

    print(f"   总时间: {ik_time:.4f}s")
    print(f"   平均时间: {ik_avg:.4f}ms")
    print(f"   频率: {1000/ik_avg:.1f}Hz")

    # 6. 对比
    speedup = ik_avg / geo_avg
    print(f"\n📊 性能对比:")
    print(f"   几何解析解: {geo_avg:.4f}ms")
    print(f"   迭代 IK: {ik_avg:.4f}ms")
    print(f"   加速比: {speedup:.1f}x")

    if speedup > 5:
        print(f"\n✅ 测试 3 通过！几何解析解显著更快 ({speedup:.1f}x)")
        return True
    else:
        print(f"\n⚠️ 测试 3 警告：加速比低于预期 ({speedup:.1f}x < 5x)")
        return False


def main():
    """主测试函数"""
    print("🧪 几何解析臂部求解器测试套件")
    print("=" * 60)

    results = []

    # 运行所有测试
    results.append(("基础功能", test_geometric_solver_basic()))
    results.append(("VIST 集成", test_vist_integration()))
    results.append(("性能对比", test_performance_comparison()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
