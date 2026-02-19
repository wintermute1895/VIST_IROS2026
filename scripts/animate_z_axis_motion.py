#!/usr/bin/env python3
"""
演示末端在Z轴方向上下移动的动画

展示VIST系统在Z轴精密运动时的表现，包括：
- 末端垂直向下插入（保持水平姿态）
- 动态腕部解锁的平滑过渡
- 关节角度的实时变化

这是一个带约束的逆运动学问题（流形约束）：
- 约束1：末端位置只在Z轴方向变化（X、Y固定）
- 约束2：末端姿态保持水平（不旋转）
"""

import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_loader import VISTConfig
from src.core.ik_solver import PinocchioIKSolver
from src.robot.visualizer import RobotVisualizer


def animate_z_axis_motion():
    """演示末端在Z轴方向上下移动"""
    print("=" * 80)
    print("🎬 Z轴精密运动动画演示（流形约束IK）")
    print("=" * 80)
    print()

    # 1. 加载配置
    print("📋 加载系统配置...")
    config = VISTConfig()
    print(f"✅ 配置加载完成")
    print()

    # 2. 初始化IK求解器
    print("🤖 初始化IK求解器...")
    urdf_path = project_root / "config" / config.robot_model_urdf_file
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame
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

    # 3. 设置运动参数
    print("🎯 设置运动参数...")

    # 固定的X、Y坐标
    x_fixed = -0.25
    y_fixed = -0.17

    # Z轴运动范围（真机场景：只移动几厘米）
    z_start = 0.85  # 起始高度
    z_end = 0.80    # 结束高度（向下移动5cm）

    # 目标姿态：末端保持水平（垂直于Z轴）
    # 末端指向X轴正方向（朝前），保持水平
    # 这样USB可以垂直向下插入
    target_rot = Rotation.from_euler('xyz', [0, 0, 0], degrees=True)  # 无旋转，保持水平
    target_quat = target_rot.as_quat()  # [x, y, z, w]

    # 动画参数
    fps = 20
    duration = 4.0  # 单程4秒
    n_frames = int(fps * duration)

    print(f"   起始高度: {z_start:.2f}m")
    print(f"   结束高度: {z_end:.2f}m")
    print(f"   移动距离: {abs(z_end - z_start):.2f}m")
    print(f"   末端位置: X={x_fixed:.2f}m, Y={y_fixed:.2f}m")
    print(f"   姿态约束: 保持水平（垂直于Z轴）")
    print(f"   动画时长: {duration:.1f}秒 (单程)")
    print(f"   帧率: {fps} FPS")
    print()

    # 4. 运行动画
    print("▶️  开始动画 (按Ctrl+C停止)...")
    print("=" * 80)
    print()

    # 初始化：先求解起始位置
    target_pos_init = np.array([x_fixed, y_fixed, z_start])
    q_solution, success, error = ik_solver.solve(
        target_pos=target_pos_init,
        target_quat=target_quat,
        max_iter=100,
        tol=1e-4
    )

    if not success:
        print(f"❌ 无法求解起始位置: {target_pos_init}")
        print(f"   误差: {error:.6f}m")
        return

    print(f"✅ 起始位置求解成功 (误差: {error:.6f}m)")
    print()

    try:
        frame_count = 0
        direction = 1  # 1: 向下, -1: 向上

        while True:
            # 计算当前帧的进度 (0.0 到 1.0)
            progress = (frame_count % n_frames) / n_frames

            # 切换方向
            if frame_count > 0 and frame_count % n_frames == 0:
                direction *= -1
                print()
                if direction == 1:
                    print("⬇️  向下移动...")
                else:
                    print("⬆️  向上移动...")

            # 计算当前Z坐标（使用平滑的余弦插值）
            if direction == 1:
                # 向下移动
                t = (1 - np.cos(progress * np.pi)) / 2  # 平滑插值
                z_current = z_start + (z_end - z_start) * t
            else:
                # 向上移动
                t = (1 - np.cos(progress * np.pi)) / 2
                z_current = z_end + (z_start - z_end) * t

            # 当前目标位置
            target_pos = np.array([x_fixed, y_fixed, z_current])

            # 使用IK求解器求解（使用上一帧的结果作为初始猜测）
            q_solution, success, error = ik_solver.solve(
                target_pos=target_pos,
                target_quat=target_quat,
                q_init=q_solution,  # 使用上一帧的结果
                max_iter=50,  # 增加迭代次数
                tol=1e-3,  # 放宽收敛阈值
                damping=1e-2  # 增加阻尼系数避免奇异点
            )

            if not success:
                print(f"\n⚠️  求解失败: Z={z_current:.3f}m, 误差={error:.6f}m")
                # 继续运行，不中断

            # 更新可视化
            visualizer.update(q_solution)

            # 显示当前状态
            direction_symbol = "⬇️" if direction == 1 else "⬆️"

            # 提取受控关节的角度
            q_controlled = np.array([q_solution[idx] for idx in ik_solver.controlled_indices])

            print(f"\r{direction_symbol} Z={z_current:.3f}m | 误差={error:.4f}mm | "
                  f"J1={np.degrees(q_controlled[0]):5.1f}° "
                  f"J4={np.degrees(q_controlled[3]):5.1f}° "
                  f"J6={np.degrees(q_controlled[5]):5.1f}°", end="")

            # 控制帧率
            time.sleep(1.0 / fps)
            frame_count += 1

    except KeyboardInterrupt:
        print()
        print()
        print("⏹️  动画中断")

    print()
    print("=" * 80)
    print("✅ 动画演示完成！")
    print()
    print("💡 观察要点:")
    print("   - 末端只在Z轴方向移动，X和Y坐标保持不变")
    print("   - 末端姿态保持水平（垂直于Z轴），适合USB垂直插入")
    print("   - J1、J4、J6等关节协同配合实现垂直插入")
    print("   - 这是带约束的6-DOF IK：位置+姿态同时约束")
    print("=" * 80)


if __name__ == "__main__":
    animate_z_axis_motion()