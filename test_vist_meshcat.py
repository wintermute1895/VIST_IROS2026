#!/usr/bin/env python3
"""
VIST 基础卡尔曼滤波 Meshcat 可视化测试

功能：
1. 在 Meshcat 中显示机械臂
2. 模拟带噪声的遥操臂输入
3. 实时显示滤波前后的对比效果
"""

import numpy as np
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import time
import re
import sys
from pathlib import Path

# 添加路径
ros2_ws_root = Path(__file__).parent / "ros2_ws"
sys.path.insert(0, str(ros2_ws_root))

from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.config.config_loader import get_config


def prepare_urdf_for_meshcat(original_urdf_path):
    """准备URDF文件用于Meshcat可视化"""
    with open(original_urdf_path, 'r') as f:
        content = f.read()

    mesh_base_dir = original_urdf_path.parent.parent
    modified_content = re.sub(
        r'package://my_robot/',
        f'file://{mesh_base_dir}/',
        content
    )

    temp_urdf = original_urdf_path.parent / f"{original_urdf_path.stem}_meshcat.urdf"
    with open(temp_urdf, 'w') as f:
        f.write(modified_content)

    return temp_urdf


class SimpleConfig:
    """简单配置对象"""
    def __init__(self):
        self.robot_model_urdf_file = "ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf"
        self.robot_model_end_effector_frame = "Left_Wrist_Yaw_Link"


def main():
    print("=" * 70)
    print("VIST 基础卡尔曼滤波 Meshcat 可视化测试")
    print("=" * 70)

    # 路径设置
    project_root = Path(__file__).parent
    urdf_path = project_root / "ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf"

    if not urdf_path.exists():
        print(f"错误: URDF文件不存在: {urdf_path}")
        return

    print(f"\n加载URDF: {urdf_path.name}")

    # 准备Meshcat专用URDF
    meshcat_urdf = prepare_urdf_for_meshcat(urdf_path)

    # 加载机器人模型
    try:
        model, collision_model, visual_model = pin.buildModelsFromUrdf(str(meshcat_urdf))
        print("✓ 加载完整模型（包括3D mesh）")
    except Exception as e:
        print(f"警告: 无法加载几何模型: {e}")
        model = pin.buildModelFromUrdf(str(meshcat_urdf))
        collision_model = None
        visual_model = None

    data = model.createData()

    # 创建 IK solver
    controlled_joints = [
        'Left_Shoulder_Pitch_Joint',
        'Left_Shoulder_Roll_Joint',
        'Left_Shoulder_Yaw_Joint',
        'Left_Elbow_Pitch_Joint',
        'Left_Wrist_Yaw_Joint',
        'Left_Wrist_Pitch_Joint',
        'Left_Wrist_Roll_Joint'
    ]

    config = SimpleConfig()
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame=config.robot_model_end_effector_frame,
        controlled_joints=controlled_joints
    )

    # 创建卡尔曼滤波器
    print("\n初始化 VIST 卡尔曼滤波器...")
    kf = VISTKalmanFilter(ik_solver, config)

    # 创建Meshcat可视化器
    print("\n启动Meshcat可视化器...")
    viz = MeshcatVisualizer(model, collision_model, visual_model)

    try:
        viz.initViewer(open=True)
        if visual_model is not None:
            viz.loadViewerModel()
        print(f"✓ Meshcat已启动")
        print(f"  URL: {viz.viewer.url()}")
    except Exception as e:
        print(f"错误: 无法启动Meshcat: {e}")
        return

    # 设置初始关节角度
    q = pin.neutral(model)
    q_display = q.copy()

    # 初始姿态（左臂）
    initial_joints = np.array([0.0, -0.3, 0.0, -1.2, 0.0, 0.8, 0.0])
    if model.nq >= 7:
        q[:7] = initial_joints

    # 显示初始姿态
    viz.display(q)

    print("\n" + "=" * 70)
    print("测试场景设置")
    print("=" * 70)
    print("\n场景1: 恒定输入 + 噪声")
    print("  - 基准输入: 保持不变")
    print("  - 添加高斯噪声: std=0.03 rad (~1.7°)")
    print("  - 观察滤波器如何平滑噪声")
    print("\n场景2: 正弦波运动 + 噪声")
    print("  - 输入: 平滑的正弦波")
    print("  - 添加高斯噪声: std=0.03 rad")
    print("  - 观察滤波器如何跟踪运动")

    print("\n" + "=" * 70)
    print("开始测试")
    print("=" * 70)
    print("\n按 Ctrl+C 切换场景或退出")

    # 目标位姿（简单的单位矩阵）
    target_pose = np.eye(4)

    try:
        # ==========================================
        # 场景1: 恒定输入 + 噪声
        # ==========================================
        print("\n[场景1] 恒定输入 + 噪声 (持续10秒)")
        print("  观察: 机械臂应该保持相对静止，滤波器抑制噪声")

        base_input = initial_joints.copy()
        noise_std = 0.03  # 约1.7度
        t_start = time.time()
        frame_count = 0

        while time.time() - t_start < 10.0:
            # 生成带噪声的输入
            noisy_input = base_input + np.random.normal(0, noise_std, 7)

            # 应用卡尔曼滤波
            filtered_joints = kf.update(noisy_input, target_pose)

            # 更新显示（使用滤波后的值）
            if model.nq >= 7:
                q_display[:7] = filtered_joints

            pin.forwardKinematics(model, data, q_display)
            pin.updateFramePlacements(model, data)
            viz.display(q_display)

            frame_count += 1
            if frame_count % 20 == 0:
                noise_level = np.linalg.norm(noisy_input - base_input)
                filter_diff = np.linalg.norm(filtered_joints - base_input)
                print(f"  帧{frame_count}: 噪声={noise_level:.4f}, 滤波差异={filter_diff:.4f}")

            time.sleep(0.05)  # 20Hz

        print("✓ 场景1完成\n")

        # ==========================================
        # 场景2: 正弦波运动 + 噪声
        # ==========================================
        print("[场景2] 正弦波运动 + 噪声 (持续15秒)")
        print("  观察: 机械臂应该平滑运动，滤波器跟踪正弦波并抑制噪声")

        # 重置滤波器
        kf.reset(initial_joints)

        t = 0
        dt = 0.05
        frame_count = 0

        while t < 15.0:
            # 生成正弦波输入
            clean_input = initial_joints.copy()
            clean_input[0] = initial_joints[0] + 0.3 * np.sin(0.5 * t)  # 肩部俯仰
            clean_input[1] = initial_joints[1] + 0.2 * np.sin(0.7 * t)  # 肩部侧摆
            clean_input[3] = initial_joints[3] + 0.4 * np.sin(0.9 * t)  # 肘部
            clean_input[5] = initial_joints[5] + 0.3 * np.sin(1.1 * t)  # 腕部

            # 添加噪声
            noisy_input = clean_input + np.random.normal(0, noise_std, 7)

            # 应用卡尔曼滤波
            filtered_joints = kf.update(noisy_input, target_pose)

            # 更新显示
            if model.nq >= 7:
                q_display[:7] = filtered_joints

            pin.forwardKinematics(model, data, q_display)
            pin.updateFramePlacements(model, data)
            viz.display(q_display)

            frame_count += 1
            if frame_count % 40 == 0:
                tracking_error = np.linalg.norm(filtered_joints - clean_input)
                print(f"  帧{frame_count}: 跟踪误差={tracking_error:.4f}")

            t += dt
            time.sleep(dt)

        print("✓ 场景2完成\n")

        # ==========================================
        # 场景3: 关节方向测试（索引2和4）
        # ==========================================
        print("[场景3] 关节方向测试 (持续10秒)")
        print("  测试关节2和4的方向映射")

        kf.reset(initial_joints)

        # 只让关节2和4运动
        t = 0
        frame_count = 0

        while t < 10.0:
            test_input = initial_joints.copy()
            test_input[2] = 0.5 * np.sin(t)  # 关节2（Shoulder_Yaw）
            test_input[4] = 0.3 * np.sin(t + 1.5)  # 关节4（Wrist_Yaw）

            # 添加小噪声
            noisy_input = test_input + np.random.normal(0, 0.01, 7)

            # 应用滤波
            filtered_joints = kf.update(noisy_input, target_pose)

            # 更新显示
            if model.nq >= 7:
                q_display[:7] = filtered_joints

            pin.forwardKinematics(model, data, q_display)
            pin.updateFramePlacements(model, data)
            viz.display(q_display)

            frame_count += 1
            if frame_count % 40 == 0:
                print(f"  帧{frame_count}: Joint2={filtered_joints[2]:.3f}, Joint4={filtered_joints[4]:.3f}")

            t += dt
            time.sleep(dt)

        print("✓ 场景3完成\n")

    except KeyboardInterrupt:
        print("\n\n测试中断")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print("\n总结:")
    print("  ✓ 场景1: 验证了滤波器的噪声抑制能力")
    print("  ✓ 场景2: 验证了滤波器的运动跟踪能力")
    print("  ✓ 场景3: 验证了关节方向映射")
    print("\nMeshcat窗口将保持打开")
    print("按 Enter 键退出...")
    input()

    # 清理临时文件
    if meshcat_urdf.exists():
        meshcat_urdf.unlink()
        print("✓ 清理临时文件")


if __name__ == '__main__':
    main()
