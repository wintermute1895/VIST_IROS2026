#!/usr/bin/env python3
"""
测试动态腕部解锁功能

演示在不同意图因子α下，腕部控制模式的平滑过渡
"""

import numpy as np
import time
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_loader import VISTConfig
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.ik_solver import PinocchioIKSolver
from src.robot.visualizer import RobotVisualizer


def test_dynamic_wrist_unlock():
    """测试动态腕部解锁"""

    print("=" * 80)
    print("🧪 动态腕部解锁测试")
    print("=" * 80)
    print()

    # 1. 加载配置
    print("📁 加载配置...")
    config_path = project_root / "config" / "system_config.yaml"
    config = VISTConfig(str(config_path))
    print(f"✅ 配置加载完成")
    print(f"   腕部控制模式: {config.vist_wrist_control_mode}")
    print(f"   动态解锁: {config.vist_geometric_solver_enable_dynamic_wrist_unlock}")
    print()

    # 2. 初始化IK求解器
    print("🧠 初始化IK求解器...")
    urdf_path = project_root / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )
    print("✅ IK求解器初始化完成")
    print()

    # 3. 初始化几何求解器
    print("🔧 初始化几何求解器...")
    geometric_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id,
        config=config
    )
    print("✅ 几何求解器初始化完成")
    print()

    # 4. 初始化可视化器
    print("🎨 初始化MeshCat可视化...")
    visualizer = RobotVisualizer(
        ik_solver.model,
        ik_solver.collision_model,
        ik_solver.visual_model,
        enable=True,
        show_angle_window=False
    )
    print(f"✅ MeshCat服务器启动")
    print(f"   请在浏览器中打开: {visualizer.get_url()}")
    print()

    # 5. 设置测试场景
    print("🎬 设置测试场景...")

    # 固定的肩部和肘部位置
    shoulder_pos = np.array([0.0, -0.17, 1.217])
    elbow_pos = np.array([-0.15, -0.17, 1.0])
    wrist_pos = np.array([-0.25, -0.17, 0.85])

    # 目标姿态（保持水平）
    target_orientation = np.eye(3)

    print(f"   肩部位置: {shoulder_pos}")
    print(f"   肘部位置: {elbow_pos}")
    print(f"   腕部位置: {wrist_pos}")
    print()

    # 6. 测试不同的α值
    print("🔬 开始测试不同的意图因子α...")
    print()

    alpha_values = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    for alpha in alpha_values:
        print(f"📊 测试 α = {alpha:.1f}")

        # 使用几何求解器计算关节角度
        q_solution = geometric_solver.solve(
            shoulder_pos, elbow_pos, wrist_pos,
            target_orientation,
            alpha=alpha
        )

        # 显示腕部关节角度
        print(f"   腕部关节角度:")
        print(f"     J5 (Wrist Yaw):   {np.degrees(q_solution[4]):6.1f}°")
        print(f"     J6 (Wrist Pitch): {np.degrees(q_solution[5]):6.1f}°")
        print(f"     J7 (Wrist Roll):  {np.degrees(q_solution[6]):6.1f}°")

        # 更新可视化
        q_full = np.zeros(ik_solver.model.nq)
        for i, ctrl_idx in enumerate(ik_solver.controlled_indices):
            if i < len(q_solution):
                q_full[ctrl_idx] = q_solution[i]

        visualizer.update(q_full)

        # 等待用户观察
        print(f"   ⏸️  按Enter继续...")
        input()
        print()

    print("=" * 80)
    print("✅ 测试完成！")
    print()
    print("📝 观察要点:")
    print("   1. α < 0.5: 腕部完全约束（J5≈0, J6≈-J4）")
    print("   2. 0.5 < α < 0.9: 腕部逐渐解锁（平滑过渡）")
    print("   3. α > 0.9: 腕部完全自由（可以任意姿态）")
    print()
    print("💡 提示:")
    print("   - 在真机上，α会根据运动速度和方向自动计算")
    print("   - 接近目标时α增大，进入精密插入阶段")
    print("   - 腕部会自动解锁以配合Z方向运动")
    print("=" * 80)


if __name__ == "__main__":
    test_dynamic_wrist_unlock()