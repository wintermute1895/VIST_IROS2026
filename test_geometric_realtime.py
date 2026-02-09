#!/usr/bin/env python3
"""
纯几何 3+4 臂角控制实时仿真（视觉数据驱动）
接收视觉节点的 UDP 数据，使用 GeometricArmSolver 进行实时控制
"""
import numpy as np
import sys
import os
import time
import socket
import json
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.core.ik_solver import PinocchioIKSolver
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.motion_mapper import ArmMotionMapper
from src.config import get_config
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer

class GeometricArmRealtimeSimulator:
    """纯几何臂角控制实时仿真器（视觉数据驱动）"""

    def __init__(self):
        """初始化仿真器"""
        print("=" * 80)
        print("🎨 纯几何 3+4 臂角控制实时仿真（视觉数据驱动）")
        print("=" * 80)

        # 1. 加载配置
        print("\n📁 加载系统配置...")
        self.config = get_config()
        print("✅ 配置加载完成")

        # 2. 初始化运动映射器
        print("\n🗺️  初始化运动映射器...")
        self.mapper = ArmMotionMapper()
        print("✅ 运动映射器初始化完成")

        # 3. 初始化 IK 求解器
        print("\n🧠 初始化 IK 求解器...")
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
        self.ik_solver = PinocchioIKSolver(urdf_path=urdf_path)
        print("✅ IK 求解器初始化完成")

        # 4. 初始化几何求解器
        print("\n🧮 初始化几何解析求解器...")
        self.geo_solver = GeometricArmSolver(
            model=self.ik_solver.model,
            data=self.ik_solver.data,
            controlled_joints=self.ik_solver.controlled_indices,
            ee_frame_id=self.ik_solver.ee_frame_id
        )
        print("✅ 几何求解器初始化完成")

        # 5. 初始化 MeshCat
        print("\n🌐 启动 MeshCat 服务器...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat 已启动: {self.vis.url()}")

        # 6. 初始化机器人可视化
        print("\n🤖 加载机器人模型...")
        self.robot_viz = MeshcatVisualizer(
            self.ik_solver.model,
            self.ik_solver.collision_model,
            self.ik_solver.visual_model
        )
        self.robot_viz.initViewer(viewer=self.vis)
        self.robot_viz.loadViewerModel(rootNodeName="robot")

        # 7. 设置场景
        self.setup_scene()

        # 8. 初始化 UDP socket
        print("\n🔌 初始化 UDP 接收器...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.config.udp_host, self.config.udp_port))
        self.sock.setblocking(False)
        print(f"✅ UDP 监听: {self.config.udp_host}:{self.config.udp_port}")

        # 9. 初始化状态
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.trajectory_points = []
        self.max_trajectory_points = 100

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

        # 添加目标标记
        # 红色球：目标手腕位置
        self.vis["targets"]["wrist"].set_object(
            g.Sphere(0.03),
            g.MeshLambertMaterial(color=0xff0000, opacity=0.7)
        )

        # 绿色球：目标肘部位置
        self.vis["targets"]["elbow"].set_object(
            g.Sphere(0.025),
            g.MeshLambertMaterial(color=0x00ff00, opacity=0.7)
        )

        print("\n📝 场景元素:")
        print("  🟡 黄色球: 机器人肩部")
        print("  🔴 红色球: 目标手腕位置")
        print("  🟢 绿色球: 目标肘部位置")
        print("  🟠 橙色线: 人体手臂")
        print("  🔵 蓝色线: 末端轨迹")

    def update_visualization(self, q, target_wrist, target_elbow):
        """更新可视化"""
        # 1. 更新机器人姿态
        if self.robot_viz is not None:
            self.robot_viz.display(q)

        # 更新正向运动学
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        # 2. 更新目标标记
        self.vis["targets"]["wrist"].set_transform(
            tf.translation_matrix(target_wrist)
        )
        self.vis["targets"]["elbow"].set_transform(
            tf.translation_matrix(target_elbow)
        )

        # 3. 绘制手臂线段（肩部→肘部→手腕）
        shoulder_pos = self.config.robot_shoulder_position

        # 肩部到肘部的线段（黄色）
        upper_arm_points = np.array([shoulder_pos, target_elbow]).T
        self.vis["arm_segments"]["upper"].set_object(
            g.Line(g.PointsGeometry(upper_arm_points),
                   g.MeshBasicMaterial(color=0xffaa00, linewidth=4))
        )

        # 肘部到手腕的线段（橙色）
        forearm_points = np.array([target_elbow, target_wrist]).T
        self.vis["arm_segments"]["forearm"].set_object(
            g.Line(g.PointsGeometry(forearm_points),
                   g.MeshBasicMaterial(color=0xff6600, linewidth=4))
        )

        # 4. 更新轨迹
        self.trajectory_points.append(target_wrist.copy())
        if len(self.trajectory_points) > self.max_trajectory_points:
            self.trajectory_points.pop(0)

        if len(self.trajectory_points) > 1:
            points = np.array(self.trajectory_points).T
            self.vis["trajectory"].set_object(
                g.Line(g.PointsGeometry(points),
                       g.MeshBasicMaterial(color=0x00ffff, linewidth=2))
            )

    def run(self, duration=300.0):
        """运行仿真循环"""
        print("\n🚀 开始仿真...")
        print("   提示：")
        print("   1. 确保视觉节点正在运行")
        print(f"   2. 在浏览器中打开: {self.vis.url()}")
        print("   3. 移动手臂，观察机器人和目标球的变化")
        print("   4. 按 Ctrl+C 停止\n")

        start_time = time.time()
        frame_count = 0
        success_count = 0
        last_print_time = time.time()

        # 统计信息
        elbow_angle_errors = []
        position_errors = []

        try:
            while time.time() - start_time < duration:
                # 接收 UDP 数据
                try:
                    data, _ = self.sock.recvfrom(self.config.udp_buffer_size)
                    packet = json.loads(data.decode('utf-8'))

                    if 'keypoints' in packet:
                        human_kps = packet['keypoints']
                    else:
                        human_kps = packet

                    # 检查关键点是否完整
                    if 'wrist' not in human_kps or 'elbow' not in human_kps or 'shoulder' not in human_kps:
                        time.sleep(0.01)
                        continue

                    # ==========================================
                    # 核心流程：视觉 → 映射 → 几何解析解 → 可视化
                    # ==========================================

                    # Step 1: 运动映射
                    result = self.mapper.human_to_robot(human_kps)
                    if result is None:
                        time.sleep(0.01)
                        continue

                    target_pos, target_quat, debug_info = result
                    target_elbow = debug_info['elbow_pos']
                    target_shoulder = self.config.robot_shoulder_position

                    # 工作空间检查
                    dist_to_shoulder = np.linalg.norm(target_pos - target_shoulder)
                    max_reach = self.config.robot_arm_lengths['upper'] + \
                                self.config.robot_arm_lengths['forearm']

                    # 如果超出工作空间，跳过
                    if dist_to_shoulder > max_reach * 0.95:
                        if frame_count % 30 == 0:
                            print(f"⚠️ 目标位置超出工作空间 ({dist_to_shoulder:.3f}m > {max_reach*0.95:.3f}m)，跳过")
                        time.sleep(0.01)
                        continue

                    # Step 2: 使用几何解析解计算关节角度
                    try:
                        q_solution = self.geo_solver.solve(
                            target_shoulder,
                            target_elbow,
                            target_pos,
                            target_orientation=None  # 暂时不考虑姿态
                        )

                        success_count += 1

                        # 扩展到完整模型维度
                        q_full = pin.neutral(self.ik_solver.model).copy()
                        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                            if i < len(q_solution) and ctrl_idx < len(q_full):
                                q_full[ctrl_idx] = q_solution[i]
                        self.q_current = q_full

                        # 计算人体肘部角度（用于验证）
                        vec_upper = target_elbow - target_shoulder
                        vec_lower = target_pos - target_elbow
                        cos_angle = np.dot(vec_upper, vec_lower) / (
                            np.linalg.norm(vec_upper) * np.linalg.norm(vec_lower) + 1e-6
                        )
                        human_elbow_angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
                        robot_elbow_angle = q_solution[3]  # 索引3 = Elbow_Pitch

                        # 记录误差
                        elbow_angle_error = abs(robot_elbow_angle - human_elbow_angle)
                        elbow_angle_errors.append(elbow_angle_error)

                        # 验证正运动学
                        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
                        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
                        ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
                        robot_wrist_pos = ee_placement.translation
                        position_error = np.linalg.norm(robot_wrist_pos - target_pos)
                        position_errors.append(position_error)

                    except Exception as e:
                        if frame_count % 30 == 0:
                            print(f"⚠️ 几何求解失败: {e}")
                        time.sleep(0.01)
                        continue

                    # Step 3: 更新可视化
                    self.update_visualization(
                        q=self.q_current,
                        target_wrist=target_pos,
                        target_elbow=target_elbow
                    )

                    frame_count += 1

                    # 每秒打印一次状态
                    if time.time() - last_print_time >= 1.0:
                        success_rate = (success_count / frame_count * 100) if frame_count > 0 else 0

                        # 计算平均误差
                        avg_elbow_error = np.mean(elbow_angle_errors[-30:]) if elbow_angle_errors else 0
                        avg_pos_error = np.mean(position_errors[-30:]) if position_errors else 0

                        status_msg = f"✅ 帧数: {frame_count} | 成功率: {success_rate:.1f}%"
                        status_msg += f" | 肘部角度误差: {np.degrees(avg_elbow_error):.2f}°"
                        status_msg += f" | 位置误差: {avg_pos_error*1000:.1f}mm"
                        status_msg += f" | 目标: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]"

                        print(status_msg)
                        last_print_time = time.time()

                except BlockingIOError:
                    # 没有数据，继续等待
                    time.sleep(0.01)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析错误: {e}")
                except Exception as e:
                    print(f"⚠️ 处理数据时出错: {e}")
                    import traceback
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")

        finally:
            self.sock.close()
            print(f"\n📊 统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   成功次数: {success_count}")
            if frame_count > 0:
                print(f"   成功率: {success_count / frame_count * 100:.1f}%")
            if elbow_angle_errors:
                print(f"   平均肘部角度误差: {np.degrees(np.mean(elbow_angle_errors)):.2f}°")
                print(f"   最大肘部角度误差: {np.degrees(np.max(elbow_angle_errors)):.2f}°")
            if position_errors:
                print(f"   平均位置误差: {np.mean(position_errors)*1000:.1f}mm")
                print(f"   最大位置误差: {np.max(position_errors)*1000:.1f}mm")
            print(f"   运行时长: {time.time() - start_time:.1f}秒")
            print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")
            print("\n✅ 仿真器已退出")

def main():
    simulator = GeometricArmRealtimeSimulator()
    simulator.run(duration=300.0)  # 运行5分钟

if __name__ == "__main__":
    main()
