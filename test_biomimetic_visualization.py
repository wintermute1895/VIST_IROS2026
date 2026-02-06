#!/usr/bin/env python3
"""
仿生观测模型可视化测试
在 MeshCat 中可视化关节映射和仿生观测模型的效果
"""
import numpy as np
import sys
import os
import time
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.config import get_config
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer

class BiomimeticVisualizer:
    """仿生观测模型可视化器"""

    def __init__(self):
        """初始化可视化器"""
        print("=" * 80)
        print("🎨 仿生观测模型可视化测试")
        print("=" * 80)

        # 1. 初始化 MeshCat
        print("\n🌐 启动 MeshCat 服务器...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat 已启动: {self.vis.url()}")

        # 2. 初始化 IK 求解器
        print("\n🧠 初始化 IK 求解器...")
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
        self.ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

        # 3. 初始化 VIST 滤波器
        print("\n🔬 初始化 VIST 滤波器...")
        self.config = get_config()
        self.vist_filter = VISTKalmanFilter(self.ik_solver, self.config)

        # 4. 初始化机器人可视化
        print("\n🤖 加载机器人模型...")
        self.robot_viz = MeshcatVisualizer(
            self.ik_solver.model,
            self.ik_solver.collision_model,
            self.ik_solver.visual_model
        )
        self.robot_viz.initViewer(viewer=self.vis)
        self.robot_viz.loadViewerModel(rootNodeName="robot")

        # 5. 设置场景
        self.setup_scene()

        print("\n✅ 初始化完成！")
        print(f"\n🌐 请在浏览器中打开: {self.vis.url()}")

    def setup_scene(self):
        """设置可视化场景"""
        # 设置相机视角
        self.vis["/Cameras/default"].set_transform(
            tf.translation_matrix([2.0, 2.0, 1.5]) @
            tf.euler_matrix(0, np.pi/6, -np.pi/4)
        )

        # 添加坐标系
        self.vis["world_frame"].set_object(
            g.triad(scale=0.3)
        )

        # 添加肩部标记
        shoulder_pos = self.config.robot_shoulder_position
        self.vis["shoulder"].set_object(
            g.Sphere(0.03),
            g.MeshLambertMaterial(color=0xffff00)
        )
        self.vis["shoulder"].set_transform(
            tf.translation_matrix(shoulder_pos)
        )

        # 添加人体关键点标记
        self.vis["human"]["shoulder"].set_object(
            g.Sphere(0.025),
            g.MeshLambertMaterial(color=0xff0000, opacity=0.7)
        )
        self.vis["human"]["elbow"].set_object(
            g.Sphere(0.025),
            g.MeshLambertMaterial(color=0x00ff00, opacity=0.7)
        )
        self.vis["human"]["wrist"].set_object(
            g.Sphere(0.025),
            g.MeshLambertMaterial(color=0x0000ff, opacity=0.7)
        )

        # 添加法向量箭头
        # 人体臂平面法向量（红色）
        self.vis["normals"]["human"].set_object(
            g.Cylinder(height=0.3, radius=0.005),
            g.MeshLambertMaterial(color=0xff0000)
        )

        # 机器人臂平面法向量（绿色）
        self.vis["normals"]["robot"].set_object(
            g.Cylinder(height=0.3, radius=0.005),
            g.MeshLambertMaterial(color=0x00ff00)
        )

    def update_human_arm(self, shoulder_pos, elbow_pos, wrist_pos):
        """更新人体手臂可视化"""
        # 更新关键点位置
        self.vis["human"]["shoulder"].set_transform(
            tf.translation_matrix(shoulder_pos)
        )
        self.vis["human"]["elbow"].set_transform(
            tf.translation_matrix(elbow_pos)
        )
        self.vis["human"]["wrist"].set_transform(
            tf.translation_matrix(wrist_pos)
        )

        # 绘制手臂线段
        # 上臂（肩→肘）
        upper_arm_points = np.array([shoulder_pos, elbow_pos]).T
        self.vis["human"]["upper_arm"].set_object(
            g.Line(g.PointsGeometry(upper_arm_points),
                   g.MeshBasicMaterial(color=0xff6600, linewidth=5))
        )

        # 前臂（肘→腕）
        forearm_points = np.array([elbow_pos, wrist_pos]).T
        self.vis["human"]["forearm"].set_object(
            g.Line(g.PointsGeometry(forearm_points),
                   g.MeshBasicMaterial(color=0xff3300, linewidth=5))
        )

    def update_normal_vectors(self, shoulder_pos, elbow_pos, wrist_pos):
        """更新法向量可视化"""
        # 计算人体臂平面法向量
        vec_upper = elbow_pos - shoulder_pos
        vec_lower = wrist_pos - elbow_pos
        n_human = np.cross(vec_upper, vec_lower)
        n_human_norm = np.linalg.norm(n_human)

        if n_human_norm > 1e-6:
            n_human = n_human / n_human_norm

            # 计算肘部位置作为法向量的起点
            elbow_center = elbow_pos

            # 人体法向量（红色箭头）
            arrow_length = 0.3
            arrow_end = elbow_center + n_human * arrow_length

            # 计算旋转矩阵（将 Z 轴对齐到法向量方向）
            z_axis = np.array([0, 0, 1])
            rotation_axis = np.cross(z_axis, n_human)
            rotation_axis_norm = np.linalg.norm(rotation_axis)

            if rotation_axis_norm > 1e-6:
                rotation_axis = rotation_axis / rotation_axis_norm
                angle = np.arccos(np.clip(np.dot(z_axis, n_human), -1.0, 1.0))
                rotation_matrix = tf.rotation_matrix(angle, rotation_axis)
            else:
                rotation_matrix = np.eye(4)

            # 设置箭头位置和方向
            transform = tf.translation_matrix(elbow_center + n_human * arrow_length / 2)
            transform[:3, :3] = rotation_matrix[:3, :3]
            self.vis["normals"]["human"].set_transform(transform)

        # 获取机器人臂平面法向量
        n_robot = self.vist_filter._get_robot_arm_plane_normal()

        # 机器人法向量（绿色箭头）
        arrow_length = 0.3

        # 计算旋转矩阵
        z_axis = np.array([0, 0, 1])
        rotation_axis = np.cross(z_axis, n_robot)
        rotation_axis_norm = np.linalg.norm(rotation_axis)

        if rotation_axis_norm > 1e-6:
            rotation_axis = rotation_axis / rotation_axis_norm
            angle = np.arccos(np.clip(np.dot(z_axis, n_robot), -1.0, 1.0))
            rotation_matrix = tf.rotation_matrix(angle, rotation_axis)
        else:
            rotation_matrix = np.eye(4)

        # 使用肩部位置作为起点
        shoulder_pos_robot = np.array(self.config.robot_shoulder_position)
        transform = tf.translation_matrix(shoulder_pos_robot + n_robot * arrow_length / 2)
        transform[:3, :3] = rotation_matrix[:3, :3]
        self.vis["normals"]["robot"].set_transform(transform)

    def update_robot(self, q_solution):
        """更新机器人姿态"""
        # 扩展到完整模型维度
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_solution) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_solution[i]

        # 更新机器人可视化
        self.robot_viz.display(q_full)

    def test_elbow_mapping(self):
        """测试1：肘部关节映射"""
        print("\n" + "=" * 80)
        print("测试1：肘部关节映射")
        print("=" * 80)
        print("\n将逐步增加肘部关节角度，观察机器人的肘部是否正确弯曲...")
        print("如果映射正确，应该看到 Right_Elbow_Pitch_Joint 弯曲")
        print("如果映射错误，会看到 Right_Wrist_Pitch_Joint 弯曲")

        input("\n按 Enter 开始测试...")

        # 测试不同的肘部角度
        test_angles = [0.0, 0.5, 1.0, 1.5, 2.0, 1.5, 1.0, 0.5, 0.0]

        for angle in test_angles:
            print(f"\n设置肘部角度: {np.degrees(angle):.1f}° ({angle:.3f} rad)")

            # 清零所有关节
            self.vist_filter.state[:7] = 0.0
            # 设置索引3（肘部）
            self.vist_filter.state[3] = angle

            # 更新可视化
            self.update_robot(self.vist_filter.state[:7])

            time.sleep(0.5)

        print("\n✅ 测试1完成！")
        print("如果看到肘部正确弯曲，说明映射正确。")

    def test_biomimetic_observation(self):
        """测试2：仿生观测模型"""
        print("\n" + "=" * 80)
        print("测试2：仿生观测模型（3+4解耦）")
        print("=" * 80)
        print("\n将模拟不同的人体手臂姿态，观察仿生观测模型的计算结果...")

        input("\n按 Enter 开始测试...")

        # 测试场景1：手臂弯曲90度
        print("\n场景1：手臂弯曲90度")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.1])
        wrist_pos = np.array([0.2, 0.0, 0.35])

        self.run_biomimetic_test(shoulder_pos, elbow_pos, wrist_pos, "手臂弯曲90度")
        time.sleep(2)

        # 测试场景2：手臂伸直
        print("\n场景2：手臂伸直")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.1])
        wrist_pos = np.array([0.4, 0.0, 0.2])

        self.run_biomimetic_test(shoulder_pos, elbow_pos, wrist_pos, "手臂伸直")
        time.sleep(2)

        # 测试场景3：手臂向侧面弯曲
        print("\n场景3：手臂向侧面弯曲")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.15, 0.15, 0.1])
        wrist_pos = np.array([0.15, 0.15, 0.35])

        self.run_biomimetic_test(shoulder_pos, elbow_pos, wrist_pos, "手臂向侧面弯曲")
        time.sleep(2)

        print("\n✅ 测试2完成！")

    def run_biomimetic_test(self, shoulder_pos, elbow_pos, wrist_pos, description):
        """运行单个仿生观测测试"""
        print(f"\n{description}:")
        print(f"  肩部: {shoulder_pos}")
        print(f"  肘部: {elbow_pos}")
        print(f"  手腕: {wrist_pos}")

        # 更新人体手臂可视化
        self.update_human_arm(shoulder_pos, elbow_pos, wrist_pos)

        # 更新法向量可视化
        self.update_normal_vectors(shoulder_pos, elbow_pos, wrist_pos)

        # 计算仿生观测
        target_pos = wrist_pos
        z_hand, z_elbow, z_swivel = self.vist_filter.compute_biomimetic_observation(
            shoulder_pos, elbow_pos, wrist_pos, target_pos
        )

        print(f"\n  观测结果:")
        print(f"    z_elbow (肘部角度):  {np.degrees(z_elbow):.1f}° ({z_elbow:.3f} rad)")
        print(f"    z_swivel (臂平面角度): {np.degrees(z_swivel):.1f}° ({z_swivel:.3f} rad)")

        # 应用观测到机器人（简化版本：只应用肘部角度）
        self.vist_filter.state[:7] = 0.0
        self.vist_filter.state[3] = z_elbow  # 应用肘部角度

        # 更新机器人可视化
        self.update_robot(self.vist_filter.state[:7])

    def run(self):
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("开始可视化测试")
        print("=" * 80)

        # 测试1：肘部关节映射
        self.test_elbow_mapping()

        # 测试2：仿生观测模型
        self.test_biomimetic_observation()

        print("\n" + "=" * 80)
        print("所有测试完成！")
        print("=" * 80)
        print(f"\n可视化窗口将保持打开，您可以在浏览器中查看: {self.vis.url()}")
        print("按 Ctrl+C 退出...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 退出可视化")

def main():
    visualizer = BiomimeticVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()
