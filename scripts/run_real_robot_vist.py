#!/usr/bin/env python3
"""
VIST 真机控制主程序
基于 simulate_full_flow.py，完整集成 VIST 框架到真机

核心组件：
1. VIST 卡尔曼滤波器 (VISTKalmanFilter)
2. 几何解析求解器 (GeometricArmSolver)
3. 安全控制器 (SafeRobotController)
4. 真机驱动 (RealArmDriver)

功能：
- 接收视觉节点的 UDP 数据
- 通过 motion_mapper 进行坐标转换
- 使用 VIST 框架计算关节角度
- 安全控制后发送到真机
- 可选的 MeshCat 可视化

Author: VIST Project
Date: 2026-02-07
"""

import os
import sys
import time
import socket
import json
import numpy as np
import pinocchio as pin

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper
from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.geometric_arm_solver import GeometricArmSolver
from src.control.safe_robot_controller import SafeRobotController
from src.robot.arm_driver import RealArmDriver
from src.config import get_config


class RealRobotVIST:
    """VIST 真机控制器：完整的 VIST 框架 + 真机驱动"""

    def __init__(self, robot_ip="192.168.1.183", arm_side="right", enable_visualization=False):
        """
        初始化真机控制器

        Args:
            robot_ip: 机器人控制器 IP 地址
            arm_side: 使用哪个手臂 ("left" 或 "right")
            enable_visualization: 是否启用 MeshCat 可视化（调试用）
        """
        print("=" * 80)
        print("🦾 VIST 真机控制系统")
        print("=" * 80)

        # 1. 加载配置
        print("\n📁 加载系统配置...")
        self.config = get_config()
        print("✅ 配置加载完成")

        # 2. 初始化运动映射器
        print("\n🗺️  初始化运动映射器...")
        self.mapper = ArmMotionMapper()
        print("✅ 运动映射器初始化完成")

        # 3. 初始化 IK 求解器（用于 VIST 框架）
        print("\n🧠 初始化 IK 求解器...")
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
        self.ik_solver = PinocchioIKSolver(
            urdf_path=urdf_path,
            end_effector_frame="Right_Wrist_Roll_Link"
        )
        print("✅ IK 求解器初始化完成")

        # 4. 初始化 VIST 框架
        print("\n🔬 初始化 VIST 框架...")

        # 4.1 初始化几何求解器
        geometric_solver = None
        if self.config.vist_geometric_solver_enabled:
            print("   🧮 启用几何解析求解器...")
            geometric_solver = GeometricArmSolver(
                model=self.ik_solver.model,
                data=self.ik_solver.data,
                controlled_joints=self.ik_solver.controlled_indices,
                ee_frame_id=self.ik_solver.ee_frame_id,
                config=self.config
            )
            print(f"   ✅ 几何求解器初始化完成 (trust_weight={self.config.vist_geometric_solver_trust_weight})")

        # 4.2 初始化 VIST 卡尔曼滤波器
        self.vist_filter = VISTKalmanFilter(
            self.ik_solver,
            self.config,
            geometric_solver=geometric_solver
        )
        print("✅ VIST Kalman Filter 初始化完成")
        print(f"   意图检测: 启用")
        print(f"   几何求解器: {'启用' if self.config.vist_geometric_solver_enabled else '禁用'}")
        print(f"   仿生观测: {'启用' if self.config.vist_biomimetic_enabled else '禁用'}")

        # 5. 初始化安全控制器
        print("\n🛡️  初始化安全控制器...")
        self.safety_controller = SafeRobotController(
            config=self.config,
            enable_logging=True
        )
        print("✅ 安全控制器初始化完成")

        # 6. 初始化真机驱动
        print(f"\n🦾 初始化真机驱动 ({arm_side.upper()} arm)...")
        self.driver = RealArmDriver(
            ip=robot_ip,
            dof=7,
            arm_side=arm_side
        )
        print("✅ 真机驱动初始化完成")

        # 7. 设置 UDP 接收
        print("\n📡 设置 UDP 接收...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.config.udp_host, self.config.udp_port))
        self.sock.setblocking(False)
        print(f"✅ UDP 接收器就绪 ({self.config.udp_host}:{self.config.udp_port})")

        # 8. 可视化（可选）
        self.enable_visualization = enable_visualization
        self.vis = None
        self.robot_viz = None
        if enable_visualization:
            try:
                print("\n🎨 初始化 MeshCat 可视化...")
                import meshcat
                from pinocchio.visualize import MeshcatVisualizer

                self.vis = meshcat.Visualizer()
                print(f"✅ MeshCat 服务器启动: {self.vis.url()}")

                self.robot_viz = MeshcatVisualizer(
                    self.ik_solver.model,
                    self.ik_solver.collision_model,
                    self.ik_solver.visual_model
                )
                self.robot_viz.initViewer(viewer=self.vis)
                self.robot_viz.loadViewerModel(rootNodeName="robot")
                print("✅ 可视化初始化完成")
            except Exception as e:
                print(f"⚠️ 可视化初始化失败: {e}")
                print("   继续运行但不显示可视化")
                self.enable_visualization = False

        # 9. 初始化状态
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.data_timeout_count = 0
        self.max_data_timeout = self.config.max_data_timeout

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)

    def connect(self):
        """连接到真机"""
        print("\n🔌 连接机器人...")
        success = self.driver.connect()
        if not success:
            raise RuntimeError("❌ 连接机器人失败！")

        print("✅ 连接成功")

        # 读取当前状态
        print("\n📊 读取当前关节状态...")
        timestamp, q_pos, q_vel = self.driver.get_state()

        # 扩展到完整模型维度
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_pos) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_pos[i]

        self.q_current = q_full

        # 初始化安全控制器的当前状态
        self.safety_controller.q_current = q_pos.copy()

        print(f"当前关节角度（度）: {np.round(np.rad2deg(q_pos), 2)}")
        print("✅ 状态读取完成")

    def run(self, duration=300.0, countdown_seconds=10):
        """
        运行真机控制循环

        Args:
            duration: 运行时长（秒）
            countdown_seconds: 启动前倒计时（秒）
        """
        print("\n" + "=" * 80)
        print("🚀 准备启动真机控制...")
        print("=" * 80)

        print("\n⚠️  安全提示：")
        print("   1. 确保机器人周围无障碍物")
        print("   2. 确保紧急停止按钮可用")
        print("   3. 确保视觉节点正在运行")
        print("   4. 按 Ctrl+C 可随时停止")

        # 倒计时
        print(f"\n⏱️  {countdown_seconds}秒后开始...")
        for i in range(countdown_seconds, 0, -1):
            print(f"   {i}...", end='\r')
            time.sleep(1)
        print("   🚀 开始！" + " " * 20)

        start_time = time.time()
        frame_count = 0
        ik_success_count = 0
        safety_violation_count = 0
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                loop_start = time.time()

                # ==========================================
                # Step 1: 接收 UDP 数据
                # ==========================================
                try:
                    data, _ = self.sock.recvfrom(self.config.udp_buffer_size)
                    packet = json.loads(data.decode('utf-8'))

                    if 'keypoints' in packet:
                        human_kps = packet['keypoints']
                    else:
                        human_kps = packet

                    # 检查关键点是否完整
                    if 'wrist' not in human_kps or 'elbow' not in human_kps:
                        time.sleep(self.config.control_dt)
                        continue

                    self.data_timeout_count = 0

                except BlockingIOError:
                    # 没有数据
                    self.data_timeout_count += 1
                    if self.data_timeout_count >= self.max_data_timeout:
                        print(f"\n⚠️ 超过 {self.max_data_timeout} 帧未收到数据，停止运动")
                        # 发送当前位置（停止运动）
                        _, q_current_7dof, _ = self.driver.get_state()
                        self.driver.send_command(q_current_7dof)
                        self.data_timeout_count = 0
                    time.sleep(self.config.control_dt)
                    continue
                except Exception as e:
                    print(f"\n❌ 数据接收错误: {e}")
                    break

                # ==========================================
                # Step 2: 运动映射（Shoulder Frame → Robot Base Frame）
                # ==========================================
                result = self.mapper.human_to_robot(human_kps)
                if result is None:
                    time.sleep(self.config.control_dt)
                    continue

                target_pos, target_quat, debug_info = result
                target_elbow = debug_info['elbow_pos']

                # 工作空间检查
                shoulder_pos = self.config.robot_shoulder_position
                dist_to_shoulder = np.linalg.norm(target_pos - shoulder_pos)
                max_reach = self.config.robot_arm_lengths['upper'] + \
                            self.config.robot_arm_lengths['forearm']

                if dist_to_shoulder > max_reach * 0.95:
                    if frame_count % 30 == 0:
                        print(f"⚠️ 目标位置超出工作空间 ({dist_to_shoulder:.3f}m > {max_reach*0.95:.3f}m)")
                    time.sleep(self.config.control_dt)
                    continue

                # ==========================================
                # Step 3: VIST 卡尔曼滤波求解
                # ==========================================
                q_solution, success, error = self.vist_filter.solve(
                    target_pos=target_pos,
                    target_quat=target_quat,
                    q_init=self.q_current,
                    elbow_pos=target_elbow,
                    shoulder_pos=shoulder_pos
                )

                if not success:
                    if frame_count % 30 == 0:
                        print(f"⚠️ VIST 求解失败 (误差={error*1000:.2f}mm)")
                    time.sleep(self.config.control_dt)
                    continue

                ik_success_count += 1

                # ==========================================
                # Step 4: 安全控制器检查
                # ==========================================
                q_safe, safety_status = self.safety_controller.process_command(q_solution)

                # 检查安全违规
                if safety_status['emergency_stop']:
                    print("\n🚨 紧急停止激活！")
                    break

                if (safety_status['velocity_limited'] or
                    safety_status['acceleration_limited'] or
                    safety_status['position_limited']):
                    safety_violation_count += 1

                # ==========================================
                # Step 5: 发送到真机
                # ==========================================
                self.driver.send_command(q_safe)

                # ==========================================
                # Step 6: 更新状态
                # ==========================================
                # 扩展到完整模型维度（用于可视化）
                q_full = pin.neutral(self.ik_solver.model).copy()
                for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                    if i < len(q_safe) and ctrl_idx < len(q_full):
                        q_full[ctrl_idx] = q_safe[i]
                self.q_current = q_full

                # 可视化更新
                if self.enable_visualization and self.robot_viz is not None:
                    self.robot_viz.display(self.q_current)

                frame_count += 1

                # ==========================================
                # Step 7: 状态显示（每秒一次）
                # ==========================================
                if time.time() - last_print_time >= 1.0:
                    ik_success_rate = (ik_success_count / frame_count * 100) if frame_count > 0 else 0

                    status_msg = f"✅ 帧数: {frame_count} | IK成功率: {ik_success_rate:.1f}%"

                    # VIST 意图因子
                    if hasattr(self.vist_filter, 'alpha_smoothed'):
                        status_msg += f" | 意图: {self.vist_filter.alpha_smoothed:.2f}"

                    # 安全状态
                    if safety_violation_count > 0:
                        status_msg += f" | 安全限制: {safety_violation_count}次"

                    # 目标位置
                    status_msg += f" | 目标: [{target_pos[0]:.2f}, {target_pos[1]:.2f}, {target_pos[2]:.2f}]"

                    print(status_msg)
                    last_print_time = time.time()

                # 控制频率
                elapsed = time.time() - loop_start
                if elapsed < self.config.control_dt:
                    time.sleep(self.config.control_dt - elapsed)

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")
        except Exception as e:
            print(f"\n❌ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 停止运动（发送当前位置）
            print("\n🛑 停止运动...")
            try:
                _, q_current_7dof, _ = self.driver.get_state()
                self.driver.send_command(q_current_7dof)
                time.sleep(0.1)
            except Exception as e:
                print(f"⚠️ 发送停止指令失败: {e}")

            # 断开连接
            self.sock.close()
            self.driver.disconnect()

            # 统计信息
            print(f"\n📊 统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   IK成功次数: {ik_success_count}")
            if frame_count > 0:
                print(f"   IK成功率: {ik_success_count / frame_count * 100:.1f}%")
            print(f"   安全限制次数: {safety_violation_count}")
            print(f"   运行时长: {time.time() - start_time:.1f}秒")
            if frame_count > 0:
                print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")

            # 安全控制器统计
            safety_stats = self.safety_controller.get_statistics()
            print(f"\n🛡️  安全控制统计:")
            print(f"   速度限制: {safety_stats['velocity_limited_count']}次")
            print(f"   加速度限制: {safety_stats['acceleration_limited_count']}次")
            print(f"   位置限制: {safety_stats['position_limited_count']}次")

            print("\n✅ 真机控制器已退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VIST 真机控制系统")
    parser.add_argument("--ip", type=str, default="192.168.1.183",
                        help="机器人控制器 IP 地址")
    parser.add_argument("--arm", type=str, default="right", choices=["left", "right"],
                        help="使用哪个手臂")
    parser.add_argument("--duration", type=float, default=300.0,
                        help="运行时长（秒）")
    parser.add_argument("--countdown", type=int, default=10,
                        help="启动前倒计时（秒）")
    parser.add_argument("--viz", action="store_true",
                        help="启用 MeshCat 可视化")

    args = parser.parse_args()

    # 创建控制器
    controller = RealRobotVIST(
        robot_ip=args.ip,
        arm_side=args.arm,
        enable_visualization=args.viz
    )

    # 连接真机
    controller.connect()

    # 运行控制循环
    controller.run(
        duration=args.duration,
        countdown_seconds=args.countdown
    )


if __name__ == "__main__":
    main()
