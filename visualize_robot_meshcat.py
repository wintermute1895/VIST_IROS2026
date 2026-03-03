#!/usr/bin/env python3
"""
机械臂Meshcat可视化
根据URDF文件显示机械臂3D模型和运动仿真
"""

import numpy as np
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import time
import re
from pathlib import Path

def prepare_urdf_for_meshcat(original_urdf_path):
    """
    准备URDF文件用于Meshcat可视化
    将package://路径转换为绝对路径
    """
    # 读取原始URDF
    with open(original_urdf_path, 'r') as f:
        content = f.read()

    # mesh文件的基础目录
    mesh_base_dir = original_urdf_path.parent.parent

    # 替换package://my_robot为绝对路径
    modified_content = re.sub(
        r'package://my_robot/',
        f'file://{mesh_base_dir}/',
        content
    )

    # 创建临时URDF文件
    temp_urdf = original_urdf_path.parent / f"{original_urdf_path.stem}_meshcat.urdf"
    with open(temp_urdf, 'w') as f:
        f.write(modified_content)

    return temp_urdf

def main():
    # URDF文件路径
    urdf_path = Path("/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf")

    if not urdf_path.exists():
        print(f"错误: URDF文件不存在: {urdf_path}")
        return

    print("=" * 60)
    print("机械臂Meshcat可视化")
    print("=" * 60)
    print(f"\n加载URDF: {urdf_path.name}")

    # 准备Meshcat专用URDF
    print("准备可视化文件...")
    meshcat_urdf = prepare_urdf_for_meshcat(urdf_path)

    # 加载机器人模型
    try:
        model, collision_model, visual_model = pin.buildModelsFromUrdf(str(meshcat_urdf))
        print("✓ 加载完整模型（包括3D mesh）")
    except Exception as e:
        print(f"警告: 无法加载几何模型: {e}")
        print("使用基础模型...")
        model = pin.buildModelFromUrdf(str(meshcat_urdf))
        collision_model = None
        visual_model = None

    data = model.createData()

    # 显示机器人信息
    print(f"\n机器人信息:")
    print(f"  关节总数: {model.nq}")
    print(f"  自由度: {model.nv}")
    print(f"  刚体数: {model.njoints}")

    # 显示左臂关节
    print(f"\n左臂关节 (前7个):")
    for i in range(1, min(8, len(model.names))):
        print(f"  {i}. {model.names[i]}")

    # 创建Meshcat可视化器
    print(f"\n启动Meshcat可视化器...")
    viz = MeshcatVisualizer(model, collision_model, visual_model)

    try:
        viz.initViewer(open=True)  # 自动打开浏览器
        if visual_model is not None:
            viz.loadViewerModel()
        print(f"✓ Meshcat已启动")
        print(f"  URL: {viz.viewer.url()}")
    except Exception as e:
        print(f"错误: 无法启动Meshcat: {e}")
        return

    # 设置初始关节角度
    q = pin.neutral(model)

    # 设置一个典型的机械臂姿态（左臂）
    if model.nq >= 7:
        q[0] = 0.0      # Left_Shoulder_Pitch
        q[1] = -0.5     # Left_Shoulder_Roll
        q[2] = 0.0      # Left_Shoulder_Yaw
        q[3] = -1.5     # Left_Elbow_Pitch
        q[4] = 0.0      # Left_Wrist_Yaw
        q[5] = 1.0      # Left_Wrist_Pitch
        q[6] = 0.0      # Left_Wrist_Roll

    # 更新可视化
    pin.forwardKinematics(model, data, q)
    pin.updateFramePlacements(model, data)

    try:
        viz.display(q)
    except (AttributeError, Exception):
        pass

    print(f"\n当前关节角度 (左臂):")
    for i in range(min(7, model.nq)):
        print(f"  q[{i}] ({model.names[i+1]}): {q[i]:.3f} rad ({np.degrees(q[i]):.1f}°)")

    print(f"\n" + "=" * 60)
    print("可视化已就绪")
    print("=" * 60)
    print(f"\n在浏览器中查看: {viz.viewer.url()}")
    print(f"\n操作提示:")
    print(f"  - 鼠标左键: 旋转视图")
    print(f"  - 鼠标右键: 平移视图")
    print(f"  - 滚轮: 缩放视图")

    # 动画演示
    print(f"\n开始动画演示...")
    print(f"  - 左臂关节将进行正弦波运动")
    print(f"  - 按 Ctrl+C 停止动画")

    try:
        t = 0
        dt = 0.05  # 50ms更新一次 (20Hz)

        while True:
            # 生成平滑的正弦波运动
            if model.nq >= 7:
                # 肩部俯仰
                q[0] = 0.0 + 0.2 * np.sin(0.5 * t)
                # 肩部侧摆
                q[1] = -0.5 + 0.3 * np.sin(0.7 * t)
                # 肘部
                q[3] = -1.5 + 0.4 * np.sin(0.9 * t + 1)
                # 腕部俯仰
                q[5] = 1.0 + 0.3 * np.sin(1.1 * t + 2)

            # 更新运动学
            pin.forwardKinematics(model, data, q)
            pin.updateFramePlacements(model, data)

            # 更新可视化
            try:
                viz.display(q)
            except (AttributeError, Exception):
                pass

            t += dt
            time.sleep(dt)

    except KeyboardInterrupt:
        print(f"\n\n动画停止")

    print(f"\nMeshcat窗口将保持打开")
    print(f"按 Enter 键退出...")
    input()

    # 清理临时文件
    if meshcat_urdf.exists():
        meshcat_urdf.unlink()
        print(f"✓ 清理临时文件")

if __name__ == '__main__':
    main()
