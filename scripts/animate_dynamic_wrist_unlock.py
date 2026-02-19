#!/usr/bin/env python3
"""
动态腕部解锁动画演示

自动演示α从0到1的连续变化过程，展示腕部的平滑过渡
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


def animate_dynamic_wrist_unlock():
    """动画演示动态腕部解锁"""

    print("=" * 80)
    print("🎬 动态腕部解锁动画演示")
    print("=" * 80)
    print()

    # 1. 加载配置
    config_path = project_root / "config" / "system_config.yaml"
    config = VISTConfig(str(config_path))

    # 2. 初始化组件
    urdf_path = project_root / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
    )

    geometric_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id,
        config=config
    )

    visualizer = RobotVisualizer(
        ik_solver.model,
        ik_solver.collision_model,
        ik_solver.visual_model,
        enable=True,
        show_angle_window=False
    )

    print(f"✅ 初始化完成")
    print(f"   MeshCat: {visualizer.get_url()}")
    print()
    print(f"⚙️  配置:")
    print(f"   腕部控制模式: {config.vist_wrist_control_mode}")
    print(f"   动态解锁: {config.vist_geometric_solver_enable_dynamic_wrist_unlock}")
    print()

    # 3. 设置场景
    shoulder_pos = np.array([0.0, -0.17, 1.217])
    elbow_pos = np.array([-0.15, -0.17, 1.0])
    wrist_pos = np.array([-0.25, -0.17, 0.85])
    target_orientation = np.eye(3)

    print("🎬 开始动画...")
    print()
    print("阶段说明:")
    print("  α = 0.0-0.5: 自由移动阶段（腕部约束）")
    print("  α = 0.5-0.9: 过渡阶段（腕部逐渐解锁）")
    print("  α = 0.9-1.0: 精密插入阶段（腕部完全自由）")
    print()

    input("按Enter开始动画...")
    print()

    # 4. 动画循环
    try:
        # 正向：α从0到1
        print("▶️  正向：α从0到1")
        for i in range(101):
            alpha = i / 100.0

            # 计算关节角度
            q_solution = geometric_solver.solve(
                shoulder_pos, elbow_pos, wrist_pos,
                target_orientation,
                alpha=alpha
            )

            # 更新可视化
            q_full = np.zeros(ik_solver.model.nq)
            for j, ctrl_idx in enumerate(ik_solver.controlled_indices):
                if j < len(q_solution):
                    q_full[ctrl_idx] = q_solution[j]

            visualizer.update(q_full)

            # 显示当前状态
            stage = "约束" if alpha < 0.5 else ("过渡" if alpha < 0.9 else "自由")
            print(f"\rα = {alpha:.2f} [{stage}] | "
                  f"J5={np.degrees(q_solution[4]):5.1f}° "
                  f"J6={np.degrees(q_solution[5]):5.1f}° "
                  f"J7={np.degrees(q_solution[6]):5.1f}°", end="")

            time.sleep(0.05)  # 50ms per frame = 20 FPS

        print()
        print()

        # 暂停
        time.sleep(1.0)

        # 反向：α从1到0
        print("◀️  反向：α从1到0")
        for i in range(100, -1, -1):
            alpha = i / 100.0

            q_solution = geometric_solver.solve(
                shoulder_pos, elbow_pos, wrist_pos,
                target_orientation,
                alpha=alpha
            )

            q_full = np.zeros(ik_solver.model.nq)
            for j, ctrl_idx in enumerate(ik_solver.controlled_indices):
                if j < len(q_solution):
                    q_full[ctrl_idx] = q_solution[j]

            visualizer.update_robot_configuration(q_full)

            stage = "约束" if alpha < 0.5 else ("过渡" if alpha < 0.9 else "自由")
            print(f"\rα = {alpha:.2f} [{stage}] | "
                  f"J5={np.degrees(q_solution[4]):5.1f}° "
                  f"J6={np.degrees(q_solution[5]):5.1f}° "
                  f"J7={np.degrees(q_solution[6]):5.1f}°", end="")

            time.sleep(0.05)

        print()
        print()
        print("✅ 动画完成！")
        print()
        print("💡 观察要点:")
        print("   - 注意腕部关节角度的平滑变化")
        print("   - α < 0.5时，J5≈0（锁定），J6≈-J4（配合肘部）")
        print("   - α > 0.9时，J5-J7可以自由调整姿态")
        print("   - 过渡过程是连续的，没有突变")
        print()

    except KeyboardInterrupt:
        print()
        print("⏹️  动画中断")

    print("=" * 80)


if __name__ == "__main__":
    animate_dynamic_wrist_unlock()