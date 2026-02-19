#!/usr/bin/env python3
"""
VIST 全流程可视化仿真脚本

功能：
1. 接收视觉节点的 UDP 数据
2. 通过 motion_mapper 进行坐标转换
3. 使用 IK 求解器计算关节角度
4. 使用 MeshCat 进行实时可视化

可视化元素：
- 机器人本体：实时显示 IK 解算后的关节状态
- 红色球：目标末端（手腕）位置
- 绿色球：目标肘部位置
- 坐标系：机器人基座坐标系
- 轨迹线：末端运动轨迹

目的：数字孪生验证，在不通电真机的情况下测试完整控制流程
"""

import os
import sys
import time
import socket
import json
import numpy as np
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
import pinocchio as pin

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper
from src.core.ik_solver import PinocchioIKSolver
from src.config import get_config


class FullFlowSimulator:
    """全流程仿真器：视觉 → 映射 → IK → 可视化"""

    def __init__(self):
        """初始化仿真器"""
        print("=" * 80)
        print("🎮 VIST 全流程可视化仿真")
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
        self.ik_solver = PinocchioIKSolver(
            urdf_path=urdf_path,
            end_effector_frame="Right_Wrist_Roll_Link"
        )
        print("✅ IK 求解器初始化完成")

        # 3.5 根据配置选择求解策略
        ik_strategy = self.config.ik_strategy
        print(f"\n🎯 IK 策略: {ik_strategy}")

        if ik_strategy == "vist":
            # 使用 VIST 卡尔曼滤波
            print("🔬 初始化 VIST Kalman Filter...")
            from src.core.vist_kalman_filter import VISTKalmanFilter
            from src.core.geometric_arm_solver import GeometricArmSolver

            # 初始化几何求解器（如果配置启用）
            geometric_solver = None
            if self.config.vist_geometric_solver_enabled:
                print("   🧮 启用几何解析求解器...")
                geometric_solver = GeometricArmSolver(
                    model=self.ik_solver.model,
                    data=self.ik_solver.data,
                    controlled_joints=self.ik_solver.controlled_indices,
                    ee_frame_id=self.ik_solver.ee_frame_id,
                    config=self.config  # 传递配置以读取关节方向
                )
                print(f"   ✅ 几何求解器初始化完成 (trust_weight={self.config.vist_geometric_solver_trust_weight})")

            # 初始化 VIST 滤波器
            self.solver = VISTKalmanFilter(
                self.ik_solver,
                self.config,
                geometric_solver=geometric_solver
            )
            print("✅ VIST Kalman Filter 初始化完成")
            print(f"   意图检测: 启用")

            # 检查参数覆盖模式
            if hasattr(self.config, 'vist_simulation_use_parameter_override') and \
               self.config.vist_simulation_use_parameter_override:
                print(f"   🎛️  参数覆盖模式: 启用（仿真专用）")
                print(f"      - α将从参数覆盖管理器读取，而不是从视觉数据计算")
                print(f"      - 可通过debug_interface.py实时调整参数")
            else:
                print(f"   参数覆盖模式: 禁用（从视觉数据计算α）")

            diff_ik_status = "禁用" if self.config.vist_geometric_solver_disable_differential_ik else "启用"
            print(f"   微分 IK: {diff_ik_status}")
            print(f"   肘部约束: 启用")
            print(f"   几何求解器: {'启用' if self.config.vist_geometric_solver_enabled else '禁用'}")
            print(f"   仿生观测: {'启用' if self.config.vist_biomimetic_enabled else '禁用'}")
            if self.config.vist_biomimetic_enabled:
                print(f"      肘部权重: {self.config.vist_biomimetic_elbow_weight}")
                print(f"      臂平面权重: {self.config.vist_biomimetic_swivel_weight}")
        else:
            # 使用传统 IK 求解器
            self.solver = self.ik_solver
            print(f"✅ 使用传统 {ik_strategy} IK 求解器")

        # 4. 初始化 MeshCat 可视化
        print("\n🎨 初始化 MeshCat 可视化...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat 服务器启动: {self.vis.url()}")
        print(f"   请在浏览器中打开: {self.vis.url()}")

        # 4.5 初始化 Pinocchio 可视化器（加载真实机械臂模型）
        print("\n🤖 加载机械臂 URDF 模型...")
        try:
            from pinocchio.visualize import MeshcatVisualizer
            self.robot_viz = MeshcatVisualizer(
                self.ik_solver.model,
                self.ik_solver.collision_model,
                self.ik_solver.visual_model
            )
            self.robot_viz.initViewer(viewer=self.vis)
            # 注意：loadViewerModel 会在 _setup_scene() 之后调用
            # 因为 _setup_scene() 会清空场景
            print("✅ 机械臂可视化器初始化成功")
        except Exception as e:
            print(f"⚠️ 机械臂可视化器初始化失败: {e}")
            print("   将使用简化可视化")
            self.robot_viz = None

        # 5. 设置 UDP 接收
        print("\n📡 设置 UDP 接收...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.config.udp_host, self.config.udp_port))
        self.sock.setblocking(False)
        print(f"✅ UDP 接收器就绪 ({self.config.udp_host}:{self.config.udp_port})")

        # 6. 初始化可视化场景
        self._setup_scene()

        # 6.5 初始化角度显示窗口
        print("\n📊 初始化角度显示窗口...")
        try:
            from src.utils.angle_display_window import get_angle_window
            self.angle_window = get_angle_window()
            self.angle_window.start()
            print("✅ 角度显示窗口已启动")
        except Exception as e:
            print(f"⚠️ 角度显示窗口启动失败: {e}")
            print("   将继续运行但不显示角度信息")
            self.angle_window = None

        # 6.6 加载机器人模型（在场景设置之后）
        if self.robot_viz is not None:
            print("\n🤖 加载机械臂 3D 模型...")
            try:
                self.robot_viz.loadViewerModel(rootNodeName="robot")
                print("✅ 机械臂模型加载成功")
            except Exception as e:
                print(f"⚠️ 机械臂模型加载失败: {e}")
                self.robot_viz = None

        # 7. 初始化状态
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.trajectory_points = []
        self.max_trajectory_points = 100

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)

    def _setup_scene(self):
        """设置可视化场景"""
        # 清空场景
        self.vis.delete()

        # ==========================================
        # 1. 机械臂模型已在初始化时加载
        # ==========================================
        print("\n🎨 设置可视化场景...")

        # ==========================================
        # 2. 添加坐标系（机器人基座）
        # ==========================================
        axis_length = 0.3

        # X轴 - 红色（向前）
        x_axis_points = np.array([[0, 0, 0], [axis_length, 0, 0]]).T
        self.vis["robot_frame"]["x_axis"].set_object(
            g.Line(g.PointsGeometry(x_axis_points),
                   g.MeshBasicMaterial(color=0xff0000, linewidth=5))
        )

        # Y轴 - 绿色（向左）
        y_axis_points = np.array([[0, 0, 0], [0, axis_length, 0]]).T
        self.vis["robot_frame"]["y_axis"].set_object(
            g.Line(g.PointsGeometry(y_axis_points),
                   g.MeshBasicMaterial(color=0x00ff00, linewidth=5))
        )

        # Z轴 - 蓝色（向上）
        z_axis_points = np.array([[0, 0, 0], [0, 0, axis_length]]).T
        self.vis["robot_frame"]["z_axis"].set_object(
            g.Line(g.PointsGeometry(z_axis_points),
                   g.MeshBasicMaterial(color=0x0000ff, linewidth=5))
        )

        # ==========================================
        # 3. 添加目标标记
        # ==========================================
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

        # ==========================================
        # 4. 添加肩部标记
        # ==========================================
        shoulder_pos = self.config.robot_shoulder_position
        self.vis["shoulder"].set_object(
            g.Sphere(0.02),
            g.MeshLambertMaterial(color=0xffff00)
        )
        self.vis["shoulder"].set_transform(
            tf.translation_matrix(shoulder_pos)
        )

        print("✅ 场景设置完成")

    def update_visualization(self, q, target_wrist, target_elbow):
        """
        更新可视化

        Args:
            q: 关节角度
            target_wrist: 目标手腕位置
            target_elbow: 目标肘部位置
        """
        # 1. 更新机器人姿态（使用Pinocchio可视化器）
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

        # 2.5 绘制手臂线段（肩部→肘部→手腕）
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

        # 3. 更新轨迹
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
        """
        运行仿真循环

        Args:
            duration: 运行时长（秒）
        """
        print("\n🚀 开始仿真...")
        print("   提示：")
        print("   1. 确保视觉节点正在运行")
        print(f"   2. 在浏览器中打开: {self.vis.url()}")
        print("   3. 移动手臂，观察机器人和目标球的变化")
        print("   4. 按 Ctrl+C 停止\n")

        start_time = time.time()
        frame_count = 0
        ik_success_count = 0
        last_print_time = time.time()

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
                    if 'wrist' not in human_kps or 'elbow' not in human_kps:
                        time.sleep(0.01)
                        continue

                    # 【调试】打印原始关键点数据（每30帧一次）
                    if frame_count % 30 == 0:
                        print(f"\n🔍 原始关键点数据（Shoulder Frame）:")
                        for key in ['shoulder', 'elbow', 'wrist']:
                            if key in human_kps:
                                kp = np.array(human_kps[key])
                                print(f"   {key:8s}: [{kp[0]:7.4f}, {kp[1]:7.4f}, {kp[2]:7.4f}]")

                        # 计算臂长
                        if 'shoulder' in human_kps and 'elbow' in human_kps and 'wrist' in human_kps:
                            shoulder = np.array(human_kps['shoulder'])
                            elbow = np.array(human_kps['elbow'])
                            wrist = np.array(human_kps['wrist'])
                            upper_len = np.linalg.norm(elbow - shoulder)
                            fore_len = np.linalg.norm(wrist - elbow)
                            total_len = upper_len + fore_len
                            print(f"   上臂长度: {upper_len:.4f}m")
                            print(f"   前臂长度: {fore_len:.4f}m")
                            print(f"   总臂长: {total_len:.4f}m")
                            print(f"   机器人上臂: {self.config.robot_arm_lengths['upper']:.4f}m")
                            print(f"   机器人前臂: {self.config.robot_arm_lengths['forearm']:.4f}m")

                    # ==========================================
                    # 核心流程：视觉 → 映射 → IK → 可视化
                    # ==========================================

                    # Step 1: 运动映射
                    result = self.mapper.human_to_robot(human_kps)
                    if result is None:
                        time.sleep(0.01)
                        continue

                    target_pos, target_quat, debug_info = result
                    target_elbow = debug_info['elbow_pos']

                    # 更新角度显示窗口
                    if hasattr(self, 'angle_window') and self.angle_window is not None:
                        self.angle_window.update(debug_info)

                    # 工作空间检查
                    shoulder_pos = self.config.robot_shoulder_position
                    dist_to_shoulder = np.linalg.norm(target_pos - shoulder_pos)
                    max_reach = self.config.robot_arm_lengths['upper'] + \
                                self.config.robot_arm_lengths['forearm']

                    # 打印调试信息（每秒一次）
                    if frame_count % 30 == 0:
                        print(f"\n📍 目标位置分析:")
                        print(f"   肩部位置: [{shoulder_pos[0]:.3f}, {shoulder_pos[1]:.3f}, {shoulder_pos[2]:.3f}]")
                        print(f"   目标位置: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]")
                        print(f"   距离肩部: {dist_to_shoulder:.3f}m")
                        print(f"   最大伸展: {max_reach:.3f}m")
                        print(f"   工作空间: {'✅ 在范围内' if dist_to_shoulder < max_reach * 0.95 else '❌ 超出范围'}")

                    # 如果超出工作空间，跳过
                    if dist_to_shoulder > max_reach * 0.95:
                        if frame_count % 30 == 0:
                            print(f"⚠️ 目标位置超出工作空间，跳过IK求解")
                        time.sleep(0.01)
                        continue

                    # Step 2: IK 求解（使用配置的求解器）
                    if self.config.ik_strategy == "vist":
                        # VIST Kalman Filter 求解
                        # 传递肘部和肩部位置以支持几何求解器
                        q_solution, success, error = self.solver.solve(
                            target_pos=target_pos,
                            target_quat=target_quat,
                            q_init=self.q_current,
                            elbow_pos=target_elbow,
                            shoulder_pos=shoulder_pos
                        )
                    else:
                        # 传统 IK 求解
                        q_solution, success, error = self.solver.solve(
                            target_pos=target_pos,
                            target_quat=target_quat,
                            q_init=self.q_current,
                            max_iter=self.config.ik_max_iter,
                            tol=self.config.ik_tolerance,
                            damping=self.config.ik_damping
                        )

                    if success:
                        ik_success_count += 1

                        # VIST 返回受控关节角度（7维），需要扩展到完整模型（14维）
                        if self.config.ik_strategy == "vist":
                            # 扩展到完整模型维度
                            q_full = pin.neutral(self.ik_solver.model).copy()
                            for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                                if i < len(q_solution) and ctrl_idx < len(q_full):
                                    q_full[ctrl_idx] = q_solution[i]
                            self.q_current = q_full

                            # 添加实际电机角度到debug_info（第4个关节，索引3）
                            if len(q_solution) > 3:
                                debug_info['actual_motor_angle'] = np.degrees(q_solution[3])
                        else:
                            self.q_current = q_solution.copy()

                        # 更新角度显示窗口（包含实际角度）
                        if hasattr(self, 'angle_window') and self.angle_window is not None:
                            self.angle_window.update(debug_info)

                    # Step 3: 更新可视化
                    self.update_visualization(
                        q=self.q_current,
                        target_wrist=target_pos,
                        target_elbow=target_elbow
                    )

                    frame_count += 1

                    # 每秒打印一次状态
                    if time.time() - last_print_time >= 1.0:
                        ik_success_rate = (ik_success_count / frame_count * 100) if frame_count > 0 else 0
                        status_msg = f"✅ 帧数: {frame_count} | IK成功率: {ik_success_rate:.1f}%"

                        # VIST 特有信息
                        if self.config.ik_strategy == "vist" and hasattr(self.solver, 'alpha_smoothed'):
                            status_msg += f" | 意图因子: {self.solver.alpha_smoothed:.2f}"

                            # 显示参数覆盖状态
                            if hasattr(self.config, 'vist_simulation_use_parameter_override') and \
                               self.config.vist_simulation_use_parameter_override:
                                override = self.solver.override_manager.get_override()
                                if override.alpha_override is not None:
                                    status_msg += f" [覆盖: {override.alpha_override:.2f}]"

                        status_msg += f" | 目标位置: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]"
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

            # 关闭角度显示窗口
            if hasattr(self, 'angle_window') and self.angle_window is not None:
                self.angle_window.stop()

            print(f"\n📊 统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   IK成功次数: {ik_success_count}")
            if frame_count > 0:
                print(f"   IK成功率: {ik_success_count / frame_count * 100:.1f}%")
            print(f"   运行时长: {time.time() - start_time:.1f}秒")
            print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")
            print("\n✅ 仿真器已退出")


def main():
    simulator = FullFlowSimulator()
    simulator.run(duration=300.0)  # 运行5分钟


if __name__ == "__main__":
    main()
