#!/usr/bin/env python3
"""
MeshCat可视化URDF的零位姿态

显示机器人在所有关节为0度时的姿态
"""
import numpy as np
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import meshcat
import time
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def visualize_zero_pose():
    """可视化URDF零位姿态"""

    print("="*80)
    print("MeshCat可视化URDF零位姿态")
    print("="*80)

    # 加载URDF
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    # 处理URDF路径
    with open(urdf_path, 'r') as f:
        urdf_content = f.read()

    # 替换package路径
    urdf_content = urdf_content.replace(
        'package://my_robot/',
        os.path.join(project_root, 'config') + '/'
    )

    # 保存临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False) as tmp:
        tmp.write(urdf_content)
        tmp_urdf_path = tmp.name

    try:
        # 加载模型
        model, collision_model, visual_model = pin.buildModelsFromUrdf(
            tmp_urdf_path,
            package_dirs=[os.path.join(project_root, 'config')]
        )
        data = model.createData()

        # 初始化MeshCat
        viz = meshcat.Visualizer()
        print(f"\n✅ MeshCat服务器启动: {viz.url()}")
        print(f"   请在浏览器中打开: {viz.url()}")

        # 初始化Pinocchio可视化器
        robot_viz = MeshcatVisualizer(model, collision_model, visual_model)
        robot_viz.initViewer(viewer=viz)
        robot_viz.loadViewerModel(rootNodeName="robot")

        print("\n加载完成！")

        # 显示不同的姿态
        poses = [
            ("零位姿态（所有关节 = 0°）", pin.neutral(model)),
            ("肘部 = 45°", None),
            ("肘部 = 90°", None),
            ("肘部 = -45°", None),
            ("肘部 = -90°", None),
        ]

        # 找到肘部关节的索引
        elbow_joint_id = model.getJointId('Right_Elbow_Pitch_Joint')
        elbow_v_idx = model.joints[elbow_joint_id].idx_v

        # 准备不同姿态的配置
        for i, (name, q) in enumerate(poses):
            if q is None:
                # 从名称中提取角度
                angle_str = name.split("=")[1].strip().replace("°", "")
                angle_deg = float(angle_str)
                angle_rad = np.radians(angle_deg)

                q = pin.neutral(model).copy()
                q[elbow_v_idx] = angle_rad

            poses[i] = (name, q)

        # 循环显示不同姿态
        print("\n开始循环显示不同姿态...")
        print("按 Ctrl+C 停止\n")

        try:
            while True:
                for name, q in poses:
                    print(f"显示: {name}")

                    # 更新可视化
                    robot_viz.display(q)

                    # 计算并显示末端位置
                    pin.forwardKinematics(model, data, q)
                    pin.updateFramePlacements(model, data)

                    ee_frame_id = model.getFrameId("Right_Wrist_Roll_Link")
                    ee_pos = data.oMf[ee_frame_id].translation

                    print(f"  末端位置: [{ee_pos[0]:.4f}, {ee_pos[1]:.4f}, {ee_pos[2]:.4f}]")

                    # 显示肘部角度
                    elbow_angle_rad = q[elbow_v_idx]
                    elbow_angle_deg = np.degrees(elbow_angle_rad)
                    print(f"  肘部角度: {elbow_angle_deg:.2f}°\n")

                    time.sleep(3)  # 每个姿态显示3秒

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")

    finally:
        # 清理临时文件
        os.unlink(tmp_urdf_path)
        print("\n✅ 可视化已退出")

if __name__ == "__main__":
    visualize_zero_pose()