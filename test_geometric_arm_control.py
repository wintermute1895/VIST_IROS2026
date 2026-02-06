#!/usr/bin/env python3
"""
纯几何 3+4 臂角控制可视化仿真
直接使用 GeometricArmSolver 进行关节角度计算和可视化
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
from src.core.geometric_arm_solver import GeometricArmSolver
from src.config import get_config
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer

class GeometricArmVisualizer:
    """纯几何臂角控制可视化器"""

    def __init__(self):
        """初始化可视化器"""
        print("=" * 80)
        print("🎨 纯几何 3+4 臂角控制可视化仿真")
        print("=" * 80)

        # 1. 初始化 MeshCat
        print("\n🌐 启动 MeshCat 服务器...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat 已启动: {self.vis.url()}")

        # 2. 初始化 IK 求解器
        print("\n🧠 初始化 IK 求解器...")
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
        self.ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

        # 3. 初始化几何求解器
        print("\n🧮 初始化几何解析求解器...")
        self.geo_solver = GeometricArmSolver(
            model=self.ik_solver.model,
            data=self.ik_solver.data,
            controlled_joints=self.ik_solver.controlled_indices,
            ee_frame_id=self.ik_solver.ee_frame_id
        )

        # 4. 加载配置
        self.config = get_config()

        # 5. 初始化机器人可视化
        print("\n🤖 加载机器人模型...")
        self.robot_viz = MeshcatVisualizer(
            self.ik_solver.model,
            self.ik_solver.collision_model,
            self.ik_solver.visual_model
        )
        self.robot_viz.initViewer(viewer=self.vis)
        self.robot_viz.loadViewerModel(rootNodeName="robot")

        # 6. 设置场景
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

        # 添加肩部标记（黄色）
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

        # 添加文本标签
        print("\n📝 场景元素:")
        print("  🟡 黄色球: 机器人肩部")
        print("  🔴 红色球: 人体肩部")
        print("  🟢 绿色球: 人体肘部")
        print("  🔵 蓝色球: 人体手腕")
        print("  🟠 橙色线: 人体手臂")

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

    def update_robot(self, q_solution):
        """更新机器人姿态"""
        # 扩展到完整模型维度
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_solution) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_solution[i]

        # 更新机器人可视化
        self.robot_viz.display(q_full)

        return q_full

    def print_joint_angles(self, q_solution, description=""):
        """打印关节角度"""
        if description:
            print(f"\n{description}")
        print("-" * 80)

        joint_names = [
            "Shoulder_Pitch",
            "Shoulder_Roll",
            "Shoulder_Yaw",
            "Elbow_Pitch",
            "Wrist_Yaw",
            "Wrist_Pitch",
            "Wrist_Roll"
        ]

        for i, (name, angle) in enumerate(zip(joint_names, q_solution)):
            marker = ""
            if i == 3:  # Elbow_Pitch
                marker = " ✅ 肘部"
            elif i == 5:  # Wrist_Pitch
                marker = " ⚠️ 腕部"

            print(f"  J{i} {name:<20}: {np.degrees(angle):>7.2f}° ({angle:>7.3f} rad){marker}")

    def test_scenario(self, shoulder_pos, elbow_pos, wrist_pos, description):
        """测试单个场景"""
        print("\n" + "=" * 80)
        print(f"场景: {description}")
        print("=" * 80)

        # 打印输入
        print(f"\n输入（人体手臂关键点）:")
        print(f"  肩部: [{shoulder_pos[0]:.3f}, {shoulder_pos[1]:.3f}, {shoulder_pos[2]:.3f}]")
        print(f"  肘部: [{elbow_pos[0]:.3f}, {elbow_pos[1]:.3f}, {elbow_pos[2]:.3f}]")
        print(f"  手腕: [{wrist_pos[0]:.3f}, {wrist_pos[1]:.3f}, {wrist_pos[2]:.3f}]")

        # 计算人体肘部角度（验证）
        vec_upper = elbow_pos - shoulder_pos
        vec_lower = wrist_pos - elbow_pos
        cos_angle = np.dot(vec_upper, vec_lower) / (
            np.linalg.norm(vec_upper) * np.linalg.norm(vec_lower) + 1e-6
        )
        human_elbow_angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
        print(f"\n人体肘部角度: {np.degrees(human_elbow_angle):.1f}° ({human_elbow_angle:.3f} rad)")

        # 更新人体手臂可视化
        self.update_human_arm(shoulder_pos, elbow_pos, wrist_pos)

        # 使用几何解析解计算机器人关节角度
        print(f"\n调用 GeometricArmSolver.solve()...")
        try:
            q_solution = self.geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)
            print("✅ 计算成功！")

            # 打印关节角度
            self.print_joint_angles(q_solution, "输出（机器人关节角度）:")

            # 验证肘部角度
            robot_elbow_angle = q_solution[3]  # 索引3 = Elbow_Pitch
            angle_diff = abs(robot_elbow_angle - human_elbow_angle)

            print(f"\n验证:")
            print(f"  人体肘部角度:   {np.degrees(human_elbow_angle):>7.2f}° ({human_elbow_angle:>7.3f} rad)")
            print(f"  机器人肘部角度: {np.degrees(robot_elbow_angle):>7.2f}° ({robot_elbow_angle:>7.3f} rad)")
            print(f"  角度差:         {np.degrees(angle_diff):>7.2f}° ({angle_diff:>7.3f} rad)")

            if angle_diff < 0.1:
                print("  ✅ 肘部角度匹配良好")
            else:
                print("  ⚠️ 肘部角度差异较大")

            # 更新机器人可视化
            q_full = self.update_robot(q_solution)

            # 验证正运动学
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
            robot_wrist_pos = ee_placement.translation

            position_error = np.linalg.norm(robot_wrist_pos - wrist_pos)
            print(f"\n末端位置误差: {position_error:.4f} m")
            if position_error < 0.01:
                print("  ✅ 末端位置精确")
            else:
                print("  ⚠️ 末端位置误差较大")

        except Exception as e:
            print(f"❌ 计算失败: {e}")
            import traceback
            traceback.print_exc()

    def run_interactive_test(self):
        """运行交互式测试"""
        print("\n" + "=" * 80)
        print("交互式测试模式")
        print("=" * 80)
        print("\n将测试多个场景，每个场景会暂停等待您观察...")

        # 场景1: 手臂弯曲90度
        input("\n按 Enter 开始场景1: 手臂弯曲90度...")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.1])
        wrist_pos = np.array([0.2, 0.0, 0.35])
        self.test_scenario(shoulder_pos, elbow_pos, wrist_pos, "手臂弯曲90度")
        time.sleep(2)

        # 场景2: 手臂弯曲45度
        input("\n按 Enter 开始场景2: 手臂弯曲45度...")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.1])
        wrist_pos = np.array([0.35, 0.0, 0.25])
        self.test_scenario(shoulder_pos, elbow_pos, wrist_pos, "手臂弯曲45度")
        time.sleep(2)

        # 场景3: 手臂几乎伸直
        input("\n按 Enter 开始场景3: 手臂几乎伸直...")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.25, 0.0, 0.1])
        wrist_pos = np.array([0.5, 0.0, 0.2])
        self.test_scenario(shoulder_pos, elbow_pos, wrist_pos, "手臂几乎伸直")
        time.sleep(2)

        # 场景4: 手臂向侧面弯曲
        input("\n按 Enter 开始场景4: 手臂向侧面弯曲...")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.15, 0.15, 0.1])
        wrist_pos = np.array([0.15, 0.15, 0.35])
        self.test_scenario(shoulder_pos, elbow_pos, wrist_pos, "手臂向侧面弯曲")
        time.sleep(2)

        # 场景5: 手臂向前伸展
        input("\n按 Enter 开始场景5: 手臂向前伸展...")
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.0])
        wrist_pos = np.array([0.4, 0.0, 0.0])
        self.test_scenario(shoulder_pos, elbow_pos, wrist_pos, "手臂向前伸展")
        time.sleep(2)

        print("\n" + "=" * 80)
        print("所有测试完成！")
        print("=" * 80)

    def run_animation_test(self):
        """运行动画测试：连续变化的肘部角度"""
        print("\n" + "=" * 80)
        print("动画测试模式：连续变化肘部角度")
        print("=" * 80)

        input("\n按 Enter 开始动画...")

        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.2, 0.0, 0.1])

        # 从伸直到弯曲90度，再回到伸直
        angles = np.concatenate([
            np.linspace(0, np.pi/2, 30),  # 0° → 90°
            np.linspace(np.pi/2, 0, 30)   # 90° → 0°
        ])

        for i, target_angle in enumerate(angles):
            # 计算手腕位置（保持前臂长度不变）
            forearm_length = 0.25
            # 使用余弦定理反推手腕位置
            wrist_offset = forearm_length * np.array([
                np.cos(target_angle),
                0.0,
                np.sin(target_angle)
            ])
            wrist_pos = elbow_pos + wrist_offset

            # 更新可视化
            self.update_human_arm(shoulder_pos, elbow_pos, wrist_pos)

            # 计算机器人关节角度
            try:
                q_solution = self.geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)
                self.update_robot(q_solution)

                # 每10帧打印一次
                if i % 10 == 0:
                    print(f"\n帧 {i}: 目标肘部角度 = {np.degrees(target_angle):.1f}°")
                    print(f"  机器人肘部角度 (J3) = {np.degrees(q_solution[3]):.1f}°")

            except Exception as e:
                print(f"帧 {i} 计算失败: {e}")

            time.sleep(0.1)

        print("\n✅ 动画测试完成！")

    def run(self):
        """运行测试"""
        print("\n" + "=" * 80)
        print("选择测试模式:")
        print("=" * 80)
        print("1. 交互式测试（逐场景观察）")
        print("2. 动画测试（连续变化）")
        print("3. 两者都运行")

        choice = input("\n请选择 (1/2/3，默认3): ").strip() or "3"

        if choice in ["1", "3"]:
            self.run_interactive_test()

        if choice in ["2", "3"]:
            self.run_animation_test()

        print("\n" + "=" * 80)
        print("测试完成！")
        print("=" * 80)
        print(f"\n可视化窗口将保持打开: {self.vis.url()}")
        print("按 Ctrl+C 退出...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 退出可视化")

def main():
    visualizer = GeometricArmVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()
