#!/usr/bin/env python3 -u
"""
可视化左臂关节依次转动
每个关节先转动45度，然后回到零位，再进行下一个关节
"""

import sys
import pinocchio as pin
import numpy as np
import time
from pinocchio.visualize import MeshcatVisualizer

print("开始加载模型...", flush=True)

# URDF文件路径 - 使用绝对路径版本，不需要处理package路径
urdf_path = "/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description_absolute.urdf"

# 加载机器人模型（包括几何模型）
try:
    print("尝试加载完整模型（包含mesh）...", flush=True)
    model, collision_model, visual_model = pin.buildModelsFromUrdf(urdf_path)
    print(f"成功加载完整模型，包含 {len(visual_model.geometryObjects)} 个可视化对象", flush=True)
except Exception as e:
    # 如果无法加载几何模型，只加载运动学模型
    print(f"警告：无法加载完整的几何模型: {e}", flush=True)
    print("将使用简化可视化", flush=True)
    model = pin.buildModelFromUrdf(urdf_path)
    collision_model = pin.GeometryModel()
    visual_model = pin.GeometryModel()

print(f"模型加载完成，关节数量: {model.nq}", flush=True)
data = model.createData()

# 左臂关节名称列表
left_arm_joints = [
    "Left_Shoulder_Pitch_Joint",
    "Left_Shoulder_Roll_Joint",
    "Left_Shoulder_Yaw_Joint",
    "Left_Elbow_Pitch_Joint",
    "Left_Wrist_Yaw_Joint",
    "Left_Wrist_Pitch_Joint",
    "Left_Wrist_Roll_Joint"
]

# 创建meshcat可视化器
viz = MeshcatVisualizer(model, collision_model, visual_model)

# 初始化可视化器
print("初始化Meshcat可视化器...", flush=True)
try:
    viz.initViewer(open=True)
    print(f"Meshcat可视化器已启动", flush=True)
    print(f"请在浏览器中打开: {viz.viewer.url()}", flush=True)
except ImportError as err:
    print("Error while initializing the viewer. It seems you should install python meshcat", flush=True)
    print(err, flush=True)
    exit(1)

# 尝试加载机器人模型到可视化器
print("加载机器人模型到可视化器...", flush=True)
try:
    viz.loadViewerModel()
    print("模型加载成功", flush=True)
except Exception as e:
    print(f"警告：无法加载完整模型到可视化器: {e}", flush=True)
    print("将只显示关节坐标系", flush=True)
print("\n开始演示左臂关节运动...")

# 初始化关节配置（全部为零）
q = pin.neutral(model)

# 显示初始姿态
pin.forwardKinematics(model, data, q)
viz.display(q)
time.sleep(2)

# 45度转换为弧度
angle_45_deg = np.pi / 4

# 动画参数
steps = 30  # 每次转动的步数
delay = 0.05  # 每步之间的延迟（秒）

# 依次转动每个左臂关节
for joint_name in left_arm_joints:
    print(f"\n正在转动关节: {joint_name}")

    # 获取关节在模型中的索引
    if model.existJointName(joint_name):
        joint_id = model.getJointId(joint_name)
        # 获取关节在配置向量中的索引
        joint_q_idx = model.joints[joint_id].idx_q

        print(f"  - 关节ID: {joint_id}, 配置索引: {joint_q_idx}")

        # 第一阶段：从0度转到45度
        print(f"  - 转动到 45度...")
        for i in range(steps + 1):
            alpha = i / steps
            q[joint_q_idx] = alpha * angle_45_deg
            pin.forwardKinematics(model, data, q)
            viz.display(q)
            time.sleep(delay)

        time.sleep(0.5)  # 在45度位置停留

        # 第二阶段：从45度回到0度
        print(f"  - 回到零位...")
        for i in range(steps + 1):
            alpha = 1 - (i / steps)
            q[joint_q_idx] = alpha * angle_45_deg
            pin.forwardKinematics(model, data, q)
            viz.display(q)
            time.sleep(delay)

        time.sleep(0.5)  # 在零位停留

    else:
        print(f"  - 警告: 关节 {joint_name} 不存在于模型中")

print("\n演示完成！")
print("按Ctrl+C退出...")

# 保持程序运行，以便查看最终姿态
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n程序退出")
