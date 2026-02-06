#!/usr/bin/env python3
"""
可视化机器人URDF模型和坐标系
使用MeshCat显示机器人模型、各关节frame的坐标轴
"""
import numpy as np
import sys
import os
import yaml

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import meshcat.geometry as g
import meshcat.transformations as tf

print("="*80)
print("🎨 机器人坐标系可视化工具")
print("="*80)

# 使用双臂URDF
urdf_filename = "lkls73_o2_dual_arm_description.urdf"
urdf_path = os.path.join(project_root, "config", urdf_filename)
print(f"\n📁 加载URDF: {urdf_path}")

# 读取URDF并替换路径
with open(urdf_path, 'r') as f:
    urdf_content = f.read()

# 替换package路径（支持mesh文件）
# 注意：mesh文件在 config/meshes/arm/ 目录下
urdf_content = urdf_content.replace(
    'package://lkls73_o2_dual_arm_description/meshes/',
    f'file://{os.path.join(project_root, "config", "meshes", "arm")}/'
)

# 写入临时文件
import tempfile
temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
temp_urdf.write(urdf_content)
temp_urdf.close()

def add_coordinate_frame(viz, name, pose, axis_length=0.1, axis_radius=0.003):
    """
    在MeshCat中添加坐标系可视化（RGB = XYZ）
    """
    position = pose.translation
    rotation = pose.rotation

    # 创建三个坐标轴（X=红, Y=绿, Z=蓝）
    axes_colors = [
        ("x", [1.0, 0.0, 0.0]),  # X轴 - 红色
        ("y", [0.0, 1.0, 0.0]),  # Y轴 - 绿色
        ("z", [0.0, 0.0, 1.0]),  # Z轴 - 蓝色
    ]

    for axis_name, color in axes_colors:
        # 创建圆柱体作为坐标轴
        cylinder = g.Cylinder(axis_length, axis_radius)
        material = g.MeshLambertMaterial(color=color)

        # 计算坐标轴的位置和方向
        if axis_name == "x":
            axis_direction = rotation @ np.array([1, 0, 0])
            axis_rotation = rotation @ tf.rotation_matrix(np.pi/2, [0, 1, 0])[:3, :3]
        elif axis_name == "y":
            axis_direction = rotation @ np.array([0, 1, 0])
            axis_rotation = rotation @ tf.rotation_matrix(-np.pi/2, [1, 0, 0])[:3, :3]
        else:  # z
            axis_direction = rotation @ np.array([0, 0, 1])
            axis_rotation = rotation

        # 坐标轴中心位置
        axis_position = position + axis_direction * (axis_length / 2)

        # 构建变换矩阵
        transform = np.eye(4)
        transform[:3, :3] = axis_rotation
        transform[:3, 3] = axis_position

        # 添加到场景
        viz.viewer[f"frames/{name}/{axis_name}"].set_object(cylinder, material)
        viz.viewer[f"frames/{name}/{axis_name}"].set_transform(transform)

try:
    # 加载模型（包括visual model）
    model, collision_model, visual_model = pin.buildModelsFromUrdf(
        temp_urdf.name,
        package_dirs=[os.path.join(project_root, "config")]
    )
    data = model.createData()

    print(f"✅ 模型加载成功")
    print(f"   关节数量: {model.nq}")
    print(f"   Frame数量: {model.nframes}")

    # 初始化MeshCat可视化器
    print("\n🎨 启动MeshCat可视化器...")
    viz = MeshcatVisualizer(model, collision_model, visual_model)

    try:
        viz.initViewer(open=True)
    except ImportError as err:
        print("错误: 无法启动MeshCat可视化器")
        print("请确保已安装: pip install meshcat")
        sys.exit(1)

    # 尝试加载可视化模型
    model_loaded = False
    try:
        viz.loadViewerModel()
        model_loaded = True
        print("✅ 可视化模型加载成功")
    except Exception as err:
        print("⚠️ 警告: 无法加载可视化模型")
        print(f"   错误: {type(err).__name__}: {err}")
        print("   将只显示坐标系")

    print("✅ MeshCat已启动")
    print(f"   访问: http://127.0.0.1:7000/static/")

    # 设置不同的关节配置（14个关节：左臂7个 + 右臂7个）
    # 关节顺序：Left_Shoulder_Pitch, Left_Shoulder_Roll, Left_Shoulder_Yaw, Left_Elbow_Pitch,
    #          Left_Wrist_Yaw, Left_Wrist_Pitch, Left_Wrist_Roll,
    #          Right_Shoulder_Pitch, Right_Shoulder_Roll, Right_Shoulder_Yaw, Right_Elbow_Pitch,
    #          Right_Wrist_Yaw, Right_Wrist_Pitch, Right_Wrist_Roll
    configurations = {
        "零位姿态 (全0)": np.zeros(model.nq),
        "右臂下垂": np.concatenate([
            np.zeros(7),  # 左臂全0
            np.deg2rad([28.6, 0, 0, 85.9, 0, 0, 0])  # 右臂下垂
        ]),
        "右臂前伸": np.concatenate([
            np.zeros(7),  # 左臂全0
            np.deg2rad([0, 0, 0, 90, 0, 0, 0])  # 右臂前伸
        ]),
        "右臂侧举": np.concatenate([
            np.zeros(7),  # 左臂全0
            np.deg2rad([0, -90, 0, 0, 0, 0, 0])  # 右臂侧举
        ]),
        "双臂下垂": np.concatenate([
            np.deg2rad([28.6, 0, 0, 85.9, 0, 0, 0]),  # 左臂下垂
            np.deg2rad([28.6, 0, 0, 85.9, 0, 0, 0])   # 右臂下垂
        ]),
    }

    # 重要的frame列表（使用双臂URDF的大写命名）
    important_frames = [
        ("Body_Base_link", "基座"),
        ("Right_Shoulder_Pitch_Link", "右肩"),
        ("Right_Elbow_Pitch_Link", "右肘"),
        ("Right_Wrist_Roll_Link", "右腕/末端执行器"),
        ("Left_Shoulder_Pitch_Link", "左肩"),
        ("Left_Elbow_Pitch_Link", "左肘"),
        ("Left_Wrist_Roll_Link", "左腕/末端执行器")
    ]

    print("\n" + "="*80)
    print("📊 坐标系说明")
    print("="*80)
    print("URDF坐标系定义 (Body_Base_link为原点):")
    print("  🔴 红色轴 = X轴")
    print("  🟢 绿色轴 = Y轴")
    print("  🔵 蓝色轴 = Z轴")
    print()
    print("注意: URDF中的坐标系方向由各关节的axis定义决定")
    print("      例如: Right_Shoulder_Pitch_Joint的axis=\"0 -1 0\"表示绕-Y轴旋转")
    print()
    print("重要Frame:")
    for frame_name, description in important_frames:
        if model.existFrame(frame_name):
            frame_id = model.getFrameId(frame_name)
            print(f"  - {description:20s} ({frame_name}, ID={frame_id})")

    print("\n" + "="*80)
    print("🎮 交互控制")
    print("="*80)
    print("按数字键切换不同姿态:")
    for i, (name, _) in enumerate(configurations.items(), 1):
        print(f"  {i} - {name}")
    print("  q - 退出")
    print("="*80)

    # 主循环
    current_config_idx = 0
    config_names = list(configurations.keys())

    while True:
        # 获取当前配置
        config_name = config_names[current_config_idx]
        q = configurations[config_name]

        # 更新机器人姿态
        pin.forwardKinematics(model, data, q)
        pin.updateFramePlacements(model, data)

        # 如果模型加载成功，显示机器人
        if model_loaded:
            try:
                viz.display(q)
            except Exception as e:
                print(f"⚠️ 显示机器人失败: {e}")
                model_loaded = False  # 标记为失败，后续不再尝试

        # 显示重要frame的坐标系（增大尺寸以便观察）
        for frame_name, description in important_frames:
            if model.existFrame(frame_name):
                frame_id = model.getFrameId(frame_name)
                frame_pose = data.oMf[frame_id]
                add_coordinate_frame(viz, frame_name, frame_pose, axis_length=0.08, axis_radius=0.005)

        # 打印当前配置信息
        print(f"\n{'='*80}")
        print(f"当前姿态: {config_name}")
        print(f"{'='*80}")
        print(f"关节角度 (度): {np.rad2deg(q)}")

        # 打印重要frame的位置
        print("\n重要Frame位置 (Body_Base_link坐标系):")
        print(f"{'Frame':<30s} {'X':>10s} {'Y':>10s} {'Z':>10s}")
        print("-" * 65)
        for frame_name, description in important_frames:
            if model.existFrame(frame_name):
                frame_id = model.getFrameId(frame_name)
                pos = data.oMf[frame_id].translation
                print(f"{description:<30s} {pos[0]:>10.3f} {pos[1]:>10.3f} {pos[2]:>10.3f}")

        # 计算臂长（右臂）
        if model.existFrame("Right_Shoulder_Pitch_Link") and model.existFrame("Right_Elbow_Pitch_Link") and model.existFrame("Right_Wrist_Roll_Link"):
            shoulder_id = model.getFrameId("Right_Shoulder_Pitch_Link")
            elbow_id = model.getFrameId("Right_Elbow_Pitch_Link")
            wrist_id = model.getFrameId("Right_Wrist_Roll_Link")

            p_shoulder = data.oMf[shoulder_id].translation
            p_elbow = data.oMf[elbow_id].translation
            p_wrist = data.oMf[wrist_id].translation

            upper_len = np.linalg.norm(p_elbow - p_shoulder)
            fore_len = np.linalg.norm(p_wrist - p_elbow)

            print(f"\n右臂臂长测量:")
            print(f"  上臂 (肩→肘): {upper_len:.3f}m")
            print(f"  前臂 (肘→腕): {fore_len:.3f}m")
            print(f"  总臂展: {upper_len + fore_len:.3f}m")

        # 等待用户输入
        print(f"\n{'='*80}")
        print(f"按数字键切换姿态 (1-{len(config_names)}), 或按 'q' 退出: ", end='', flush=True)

        try:
            user_input = input().strip()

            if user_input == 'q':
                break
            elif user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(config_names):
                    current_config_idx = idx
                else:
                    print(f"⚠️ 无效输入，请输入 1-{len(config_names)}")
            else:
                print("⚠️ 无效输入")

        except KeyboardInterrupt:
            break

    print("\n✅ 退出可视化")

finally:
    # 清理临时文件
    os.unlink(temp_urdf.name)
    print("🗑️ 已清理临时文件")
