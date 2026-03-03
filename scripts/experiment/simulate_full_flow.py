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
import numpy as np
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
import pinocchio as pin

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper
from src.core.ik_solver import PinocchioIKSolver
from src.config import get_config
from src.communication.udp_receiver import UDPReceiver
from src.control.trajectory_interpolator import TrajectoryInterpolator
from src.utils.data_logger import VISTDataLogger
from src.utils.performance_monitor import TeleopMetrics

# 添加ROS2发布和高频插值支持
sys.path.insert(0, os.path.join(project_root, 'scripts'))
from simulation_ros2_publisher import SimulationPublisherWrapper
from high_frequency_publisher import HighFrequencyPublisher


class FullFlowSimulator:
    """全流程仿真器：视觉 → 映射 → IK → 可视化"""

    def __init__(self, enable_logging=None, experiment_name=None):
        """初始化仿真器

        Args:
            enable_logging: 是否启用数据记录（None则从配置读取）
            experiment_name: 实验名称（None则从配置读取或自动生成）
        """
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
        urdf_path = os.path.join(project_root, "config", "urdf", "lkls73_o2_dual_arm_description.urdf")
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
            from src.control.safe_robot_controller import SafeRobotController

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

            # 初始化安全控制器（模拟真机限制）
            print("🛡️  初始化安全控制器（模拟真机限制）...")
            self.safety_controller = SafeRobotController(self.config)
            print(f"   速度限制: {self.config.max_joint_velocity} rad/s")
            print(f"   加速度限制: {self.config.max_joint_acceleration} rad/s²")

            # 初始化轨迹插值器（平滑稀疏UDP数据）
            print("📈 初始化轨迹插值器...")
            self.interpolator = TrajectoryInterpolator(
                max_velocity=self.config.max_joint_velocity,
                max_acceleration=self.config.max_joint_acceleration,
                dt=self.config.control_dt
            )
            print(f"   ✅ 轨迹插值器初始化完成")

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
        self.udp_receiver = UDPReceiver(
            host=self.config.udp_host,
            port=self.config.udp_port,
            buffer_size=self.config.udp_buffer_size
        )
        self.udp_receiver.connect()
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

        # 8. 初始化数据记录器和性能监控
        # 从配置或参数读取是否启用
        if enable_logging is None:
            enable_logging = getattr(self.config, 'data_logging_enable_logging', True)
        if experiment_name is None:
            experiment_name = getattr(self.config, 'data_logging_experiment_name', '')

        self.enable_logging = enable_logging
        self.data_logger = None
        self.metrics = None

        if self.enable_logging:
            print("\n📊 初始化数据记录...")
            self.data_logger = VISTDataLogger(
                config=self.config,
                experiment_name=experiment_name if experiment_name else None
            )
            print(f"✅ 数据记录器初始化完成")
            print(f"   实验ID: {self.data_logger.experiment_id}")
            print(f"   保存路径: {self.data_logger.save_dir}")

            # 初始化性能监控
            if getattr(self.config, 'data_logging_enable_performance_monitoring', True):
                print("\n📈 初始化性能监控...")
                self.metrics = TeleopMetrics()
                print("✅ 性能监控初始化完成")
        else:
            print("\n⚠️  数据记录已禁用")

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)

        # 9. 初始化ROS2发布器和高频插值
        print("\n📡 初始化ROS2高频发布系统...")

        # 9.1 创建基础ROS2发布器
        enable_ros2 = getattr(self.config, 'simulation_enable_ros2_publish', True)
        publish_rate = getattr(self.config, 'vision_fps', 30.0)

        self.ros2_publisher = SimulationPublisherWrapper(
            publish_rate=publish_rate,
            enable_ros2=enable_ros2
        )

        # 9.2 创建高频发布器（250Hz）
        if enable_ros2 and self.ros2_publisher.node is not None:
            target_freq = 250.0  # 目标频率
            interpolation = 'linear'  # 简单线性插值

            self.high_freq_pub = HighFrequencyPublisher(
                ros2_publisher=self.ros2_publisher,
                target_freq=target_freq,
                interpolation=interpolation
            )
            print(f"✅ 高频发布系统初始化完成")
            print(f"   主循环频率: {publish_rate} Hz")
            print(f"   发布频率: {target_freq} Hz")
            print(f"   插值方法: {interpolation}")
        else:
            self.high_freq_pub = None
            print("⚠️  ROS2发布已禁用，跳过高频发布器")

        # 9.3 初始化简单滤波器（EMA - 指数移动平均）
        self.enable_simple_filter = getattr(self.config, 'enable_simple_filter', True)
        if self.enable_simple_filter:
            self.filter_alpha = getattr(self.config, 'simple_filter_alpha', 0.3)
            self.q_filtered = None
            print(f"✅ 简单滤波器已启用 (EMA, α={self.filter_alpha})")
        else:
            print("⚠️  简单滤波器已禁用")

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
        # 4. 添加肩部标记（蓝色球）
        # ==========================================
        shoulder_pos = self.config.robot_shoulder_position
        self.vis["shoulder"].set_object(
            g.Sphere(0.03),
            g.MeshLambertMaterial(color=0x0000ff, opacity=0.7)
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

    def run(self, duration=300.0, limit_frequency=False, countdown_seconds=5):
        """
        运行仿真循环

        Args:
            duration: 运行时长（秒）
            limit_frequency: 是否限制控制频率（模拟真机）
            countdown_seconds: 启动前倒计时（秒）
        """
        print("\n🚀 准备开始仿真...")
        print("   提示：")
        print("   1. 确保视觉节点正在运行")
        print(f"   2. 在浏览器中打开: {self.vis.url()}")
        print("   3. 移动手臂，观察机器人和目标球的变化")
        print("   4. 按 Ctrl+C 停止")
        if limit_frequency:
            print(f"   5. 频率限制: {1.0/self.config.control_dt:.1f} Hz（模拟真机）")
        else:
            print(f"   5. 频率限制: 无（最大性能）")

        # 重置所有滤波器状态（确保每次运行都从干净状态开始）
        print("\n🔄 重置滤波器状态...")
        if hasattr(self, 'solver') and hasattr(self.solver, 'reset'):
            self.solver.reset()
            print("   ✅ VIST Kalman Filter 已重置")
        if hasattr(self, 'safety_controller') and hasattr(self.safety_controller, 'reset'):
            self.safety_controller.reset()
            print("   ✅ SafeRobotController 已重置")

            # 初始化安全控制器的当前状态（使用当前关节角度）
            q_init = self.q_current[self.ik_solver.controlled_indices]
            self.safety_controller.q_current = q_init.copy()
            self.safety_controller.q_previous = q_init.copy()
            self.safety_controller.q_dot_current = np.zeros(7)
            self.safety_controller.q_dot_previous = np.zeros(7)
            self.safety_controller.last_update_time = time.time()
            print("   ✅ SafeRobotController 状态已初始化")

        if hasattr(self, 'interpolator') and hasattr(self.interpolator, 'reset'):
            # 使用当前关节角度初始化插值器
            self.interpolator.reset(self.q_current[self.ik_solver.controlled_indices])
            print("   ✅ TrajectoryInterpolator 已重置")
        # Motion mapper的One-Euro滤波器会在第一次调用时自动初始化，无需手动重置
        print("   ✅ 所有滤波器状态已重置")

        # 倒计时（给操作员时间走到摄像头前）
        if countdown_seconds > 0:
            print(f"\n⏱️  {countdown_seconds} 秒后开始仿真")
            print("   请准备：")
            print("  1. 站到摄像头前")
            print("  2. 调整站位，确保身体在摄像头中心")
            print("  3. 确认手臂在摄像头视野内")
            print("  4. 准备开始操作")
            print("\n倒计时：")

            for i in range(countdown_seconds, 0, -1):
                print(f"   {i}...", end='\r', flush=True)
                time.sleep(1)
            print("   🚀 倒计时结束！" + " " * 20)
        print()

        # 等待第一个UDP包（确保第一帧对齐）
        print("⏳ 等待第一个UDP数据包...")
        print("   ⚠️  这确保了第一帧对齐，避免突然的大幅运动")
        print("   ⚠️  请在另一个终端启动数据回放器或视觉节点")

        first_packet = None
        while first_packet is None:
            first_packet = self.udp_receiver.receive()
            if first_packet is None:
                time.sleep(0.01)  # 短暂休眠，避免CPU占用过高

        print("   ✅ 收到第一个数据包，开始仿真！\n")

        # ✅ 关键修复：重置SafeRobotController的时间戳
        # 避免倒计时和等待UDP包期间的时间累积导致第一帧dt_actual异常
        if hasattr(self, 'safety_controller'):
            self.safety_controller.last_update_time = time.time()

        # 收到第一个包后才开始计时
        start_time = time.time()
        frame_count = 0
        ik_success_count = 0
        last_print_time = time.time()
        last_robot_update = time.time()  # 上次更新机械臂的时间

        # 启动高频发布器
        if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
            init_q = self.q_current[self.ik_solver.controlled_indices]
            self.high_freq_pub.start(q_init=init_q)
            print("✅ 高频发布器已启动 (250Hz)")
            print()

        # 缓存最新的UDP数据（使用第一个包初始化）
        if 'keypoints' in first_packet:
            cached_keypoints = first_packet['keypoints']
        else:
            cached_keypoints = first_packet
        cached_timestamp = time.time()

        # 性能指标追踪
        metrics = {
            'target_positions': [],      # 目标位置序列
            'actual_positions': [],      # 实际末端位置序列
            'joint_angles': [],          # 关节角度序列
            'joint_velocities': [],      # 关节速度序列
            'joint_accelerations': [],   # 关节加速度序列
            'tracking_errors': [],       # 跟踪误差序列
            'control_loop_times': [],    # 控制循环时间
            'ik_solve_times': [],        # IK求解时间
            'safety_stats': {
                'velocity_limited': 0,
                'acceleration_limited': 0,
                'position_limited': 0
            },
            'timestamps': [],             # 时间戳
            'udp_receive_times': [],      # UDP接收间隔
            'loop_iteration_times': [],   # 循环迭代时间
            'udp_receive_count': 0,       # UDP接收计数
            'robot_update_count': 0       # 机器人更新计数
        }
        last_q = self.q_current.copy()
        last_velocity = np.zeros(7)
        last_update_time = time.time()
        last_udp_time = time.time()  # 上次收到UDP数据的时间

        try:
            while time.time() - start_time < duration:
                loop_start = time.time()

                # ==========================================
                # Phase 1: 接收UDP数据（非阻塞，更新缓存）
                # ==========================================
                packet = self.udp_receiver.receive()

                if packet is not None:
                    # 记录UDP接收间隔
                    if metrics['udp_receive_count'] > 0:
                        udp_interval = (time.time() - last_udp_time) * 1000
                        metrics['udp_receive_times'].append(udp_interval)
                    last_udp_time = time.time()
                    metrics['udp_receive_count'] += 1

                    # 提取关键点数据（兼容新旧格式）
                    if 'keypoints' in packet:
                        human_kps = packet['keypoints']
                    else:
                        human_kps = packet

                    # 检查关键点是否完整
                    if 'wrist' in human_kps and 'elbow' in human_kps:
                        # 更新缓存
                        cached_keypoints = human_kps
                        cached_timestamp = time.time()

                # ==========================================
                # Phase 2: 检查是否需要更新机器人
                # ==========================================
                should_update_robot = True
                if limit_frequency:
                    time_since_last_update = time.time() - last_robot_update
                    should_update_robot = time_since_last_update >= self.config.control_dt

                    # 如果还没到更新时间，精确休眠到下一个更新时刻
                    if not should_update_robot:
                        time_until_next_update = self.config.control_dt - time_since_last_update
                        if time_until_next_update > 0.001:  # 如果还有超过1ms，就休眠
                            # 休眠到距离目标时间还剩0.5ms（更精确）
                            sleep_time = max(0, time_until_next_update - 0.0005)
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                        continue

                # 如果没有缓存数据，跳过本次迭代
                if cached_keypoints is None:
                    time.sleep(0.001)  # 短暂休眠1ms，避免空转
                    continue

                # ==========================================
                # Phase 3: 更新机器人（使用缓存的数据）
                # ==========================================
                try:
                    metrics['robot_update_count'] += 1

                    # 【调试】打印原始关键点数据（每30帧一次）
                    if frame_count % 30 == 0:
                        print(f"\n🔍 原始关键点数据（Shoulder Frame）:")
                        for key in ['shoulder', 'elbow', 'wrist']:
                            if key in cached_keypoints:
                                kp = np.array(cached_keypoints[key])
                                print(f"   {key:8s}: [{kp[0]:7.4f}, {kp[1]:7.4f}, {kp[2]:7.4f}]")

                        # 计算臂长
                        if 'shoulder' in cached_keypoints and 'elbow' in cached_keypoints and 'wrist' in cached_keypoints:
                            shoulder = np.array(cached_keypoints['shoulder'])
                            elbow = np.array(cached_keypoints['elbow'])
                            wrist = np.array(cached_keypoints['wrist'])
                            upper_len = np.linalg.norm(elbow - shoulder)
                            fore_len = np.linalg.norm(wrist - elbow)
                            total_len = upper_len + fore_len
                            print(f"   上臂长度: {upper_len:.4f}m")
                            print(f"   前臂长度: {fore_len:.4f}m")
                            print(f"   总臂长: {total_len:.4f}m")
                            print(f"   机器人上臂: {self.config.robot_arm_lengths['upper']:.4f}m")
                            print(f"   机器人前臂: {self.config.robot_arm_lengths['forearm']:.4f}m")

                    # Step 1: 运动映射
                    result = self.mapper.human_to_robot(cached_keypoints)
                    if result is None:
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
                        print(f"   工作空间: {'✅ 在范围内' if dist_to_shoulder < max_reach * 0.98 else '❌ 超出范围'}")

                    # 如果超出工作空间，跳过（使用98%作为安全边界）
                    if dist_to_shoulder > max_reach * 0.98:
                        if frame_count % 30 == 0:
                            print(f"⚠️ 目标位置超出工作空间，跳过IK求解")
                        # 仍然更新红球和绿球（实时显示目标）
                        self.vis["targets"]["wrist"].set_transform(
                            tf.translation_matrix(target_pos)
                        )
                        self.vis["targets"]["elbow"].set_transform(
                            tf.translation_matrix(target_elbow)
                        )
                        time.sleep(0.01)
                        continue

                    # 检查是否需要更新机械臂（频率限制）
                    should_update_robot = True
                    if limit_frequency:
                        time_since_last_update = time.time() - last_robot_update
                        should_update_robot = time_since_last_update >= self.config.control_dt

                    # Step 2: IK 求解（只在需要更新机械臂时）
                    if should_update_robot:
                        ik_start_time = time.time()

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

                        ik_solve_time = time.time() - ik_start_time
                        metrics['ik_solve_times'].append(ik_solve_time * 1000)  # 转换为ms

                        if success:
                            ik_success_count += 1

                            # VIST 返回受控关节角度（7维），需要扩展到完整模型（14维）
                            if self.config.ik_strategy == "vist":
                                # 应用简单滤波（EMA）
                                if hasattr(self, 'enable_simple_filter') and self.enable_simple_filter:
                                    if self.q_filtered is None:
                                        self.q_filtered = q_solution.copy()
                                    else:
                                        # EMA滤波: q_filtered = α * q_new + (1-α) * q_old
                                        self.q_filtered = (self.filter_alpha * q_solution +
                                                          (1 - self.filter_alpha) * self.q_filtered)
                                    q_to_publish = self.q_filtered
                                else:
                                    q_to_publish = q_solution

                                # 更新高频发布器（250Hz插值发布）
                                if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
                                    self.high_freq_pub.update_target(q_to_publish)

                                # 步骤1: 使用轨迹插值器生成平滑的中间点
                                # ✅ 传递实际dt给插值器
                                if hasattr(self, 'interpolator'):
                                    # 测量实际控制周期
                                    current_time = time.time()
                                    dt_actual = current_time - last_robot_update
                                    if dt_actual > 1.0 or dt_actual < 0.001:
                                        dt_actual = self.config.control_dt
                                    q_interpolated = self.interpolator.interpolate(q_solution, dt_actual=dt_actual)
                                else:
                                    q_interpolated = q_solution

                                # 步骤2: 应用安全控制器（模拟真机限制）
                                safety_status = {}
                                if hasattr(self, 'safety_controller'):
                                    q_safe, safety_status = self.safety_controller.process_command(q_interpolated)

                                    # 统计安全限制触发次数
                                    if safety_status.get('velocity_limited'):
                                        metrics['safety_stats']['velocity_limited'] += 1
                                    if safety_status.get('acceleration_limited'):
                                        metrics['safety_stats']['acceleration_limited'] += 1
                                    if safety_status.get('position_limited'):
                                        metrics['safety_stats']['position_limited'] += 1

                                    # 记录安全限制触发情况
                                    if frame_count % 30 == 0 and any([
                                        safety_status.get('velocity_limited'),
                                        safety_status.get('acceleration_limited'),
                                        safety_status.get('position_limited')
                                    ]):
                                        print(f"   🛡️  安全限制触发: 速度={safety_status.get('velocity_limited')}, "
                                              f"加速度={safety_status.get('acceleration_limited')}")
                                else:
                                    q_safe = q_interpolated

                                # 记录数据到VISTDataLogger
                                if self.enable_logging and self.data_logger is not None:
                                    # 获取VIST滤波器的内部状态
                                    if hasattr(self.solver, 'alpha_smoothed'):
                                        alpha = self.solver.alpha_smoothed
                                    else:
                                        alpha = 0.0

                                    # 记录数据
                                    self.data_logger.record_frame(
                                        timestamp=time.time(),
                                        human_input=q_solution,  # IK原始解
                                        filtered_output=q_safe,  # 经过插值和安全控制的输出
                                        alpha_value=alpha,
                                        Q_matrix=getattr(self.solver, 'Q', None),
                                        R_matrix=getattr(self.solver, 'R', None),
                                        P_matrix=getattr(self.solver, 'P', None)
                                    )

                                # 扩展到完整模型维度
                                q_full = pin.neutral(self.ik_solver.model).copy()
                                for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                                    if i < len(q_safe) and ctrl_idx < len(q_full):
                                        q_full[ctrl_idx] = q_safe[i]
                                self.q_current = q_full

                                # 计算关节速度和加速度（仅对受控关节）
                                current_time = time.time()
                                dt = current_time - last_update_time
                                if dt > 0:
                                    current_velocity = (q_safe - last_q[:len(q_safe)]) / dt
                                    current_acceleration = (current_velocity - last_velocity) / dt

                                    metrics['joint_velocities'].append(current_velocity.copy())
                                    metrics['joint_accelerations'].append(current_acceleration.copy())

                                    last_velocity = current_velocity.copy()
                                    last_update_time = current_time

                                # 记录关节角度
                                metrics['joint_angles'].append(q_safe.copy())
                                last_q[:len(q_safe)] = q_safe.copy()

                                # 添加实际电机角度到debug_info（第4个关节，索引3）
                                if len(q_safe) > 3:
                                    debug_info['actual_motor_angle'] = np.degrees(q_safe[3])
                            else:
                                self.q_current = q_solution.copy()

                            # 计算实际末端位置和跟踪误差
                            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, self.q_current)
                            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
                            actual_pos = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id].translation
                            tracking_error = np.linalg.norm(target_pos - actual_pos)

                            metrics['target_positions'].append(target_pos.copy())
                            metrics['actual_positions'].append(actual_pos.copy())
                            metrics['tracking_errors'].append(tracking_error)
                            metrics['timestamps'].append(current_time - start_time)

                            # 记录性能指标到TeleopMetrics
                            if self.enable_logging and self.metrics is not None:
                                self.metrics.record_tracking_error(tracking_error)
                                self.metrics.record_control_loop_time(loop_time * 1000)  # 转换为ms

                            # 记录控制循环时间
                            loop_time = time.time() - ik_start_time
                            metrics['control_loop_times'].append(loop_time * 1000)  # 转换为ms

                            # 更新角度显示窗口（包含实际角度）
                            if hasattr(self, 'angle_window') and self.angle_window is not None:
                                self.angle_window.update(debug_info)

                            # 更新机械臂可视化
                            if self.robot_viz is not None:
                                self.robot_viz.display(self.q_current)

                            last_robot_update = time.time()
                            frame_count += 1

                            # Step 3: 更新红球、绿球和骨骼连线
                            self.vis["targets"]["wrist"].set_transform(
                                tf.translation_matrix(target_pos)
                            )
                            self.vis["targets"]["elbow"].set_transform(
                                tf.translation_matrix(target_elbow)
                            )

                            # 更新骨骼连线（肩部→肘部→手腕）
                            shoulder_pos = self.config.robot_shoulder_position
                            upper_arm_points = np.array([shoulder_pos, target_elbow]).T
                            self.vis["arm_segments"]["upper"].set_object(
                                g.Line(g.PointsGeometry(upper_arm_points),
                                       g.MeshBasicMaterial(color=0xffaa00, linewidth=4))
                            )
                            forearm_points = np.array([target_elbow, target_pos]).T
                            self.vis["arm_segments"]["forearm"].set_object(
                                g.Line(g.PointsGeometry(forearm_points),
                                       g.MeshBasicMaterial(color=0xff6600, linewidth=4))
                            )

                    # 每秒打印一次状态
                    if time.time() - last_print_time >= 1.0:
                        ik_success_rate = (ik_success_count / frame_count * 100) if frame_count > 0 else 0
                        actual_fps = frame_count / (time.time() - start_time)

                        # 计算UDP接收频率
                        if len(metrics['udp_receive_times']) > 0:
                            avg_udp_interval = np.mean(metrics['udp_receive_times'][-100:])  # 最近100个
                            udp_fps = 1000 / avg_udp_interval if avg_udp_interval > 0 else 0
                        else:
                            udp_fps = 0

                        status_msg = f"✅ 帧数: {frame_count} | IK成功率: {ik_success_rate:.1f}% | "
                        status_msg += f"机器人频率: {actual_fps:.1f} Hz | UDP接收: {udp_fps:.1f} Hz"

                        # VIST 特有信息
                        if self.config.ik_strategy == "vist" and hasattr(self.solver, 'alpha_smoothed'):
                            status_msg += f" | 意图因子: {self.solver.alpha_smoothed:.2f}"

                            # 显示参数覆盖状态
                            if hasattr(self.config, 'vist_simulation_use_parameter_override') and \
                               self.config.vist_simulation_use_parameter_override:
                                override = self.solver.override_manager.get_override()
                                if override.alpha_override is not None:
                                    status_msg += f" [覆盖: {override.alpha_override:.2f}]"

                        print(status_msg)
                        last_print_time = time.time()

                except Exception as e:
                    print(f"⚠️ 处理数据时出错: {e}")
                    import traceback
                    traceback.print_exc()

                # 记录循环迭代时间
                loop_time = (time.time() - loop_start) * 1000
                metrics['loop_iteration_times'].append(loop_time)

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")

        finally:
            # 清理高频发布器
            if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
                print("\n🔌 停止高频发布器...")
                self.high_freq_pub.stop()

            # 清理ROS2发布器
            if hasattr(self, 'ros2_publisher'):
                print("🔌 关闭ROS2发布器...")
                self.ros2_publisher.shutdown()

            # 关闭UDP接收器
            self.udp_receiver.close()

            # 关闭角度显示窗口
            if hasattr(self, 'angle_window') and self.angle_window is not None:
                self.angle_window.stop()

            # 保存数据和性能指标
            if self.enable_logging:
                print("\n💾 保存实验数据...")
                try:
                    if self.data_logger is not None:
                        self.data_logger.save()
                        print(f"✅  保存到: {self.data_logger.save_dir}")

                    if self.metrics is not None:
                        # 保存性能指标报告
                        report_path = self.data_logger.save_dir / "performance_metrics.txt"
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write("=" * 80 + "\n")
                            f.write("性能评价指标\n")
                            f.write("=" * 80 + "\n\n")
                            f.write(self.metrics.get_summary())
                        print(f"✅ 性能指标已保存到: {report_path}")
                except Exception as e:
                    print(f"⚠️  保存数据时出错: {e}")
                    import traceback
                    traceback.print_exc()

            # 计算并打印性能指标
            self._print_performance_metrics(metrics, frame_count, ik_success_count, start_time)

            print("\n✅ 仿真器已退出")

    def _print_performance_metrics(self, metrics, frame_count, ik_success_count, start_time):
        """计算并打印性能指标"""
        print(f"\n{'='*80}")
        print(f"📊 性能评价指标")
        print(f"{'='*80}")

        total_time = time.time() - start_time

        # ==========================================
        # 1. 基础统计
        # ==========================================
        print(f"\n【基础统计】")
        print(f"   总帧数: {frame_count}")
        print(f"   IK成功次数: {ik_success_count}")
        if frame_count > 0:
            print(f"   IK成功率: {ik_success_count / frame_count * 100:.1f}%")
        print(f"   运行时长: {total_time:.1f}秒")
        print(f"   平均帧率: {frame_count / total_time:.1f} Hz")

        # UDP接收统计
        if len(metrics['udp_receive_times']) > 1:
            udp_times = np.array(metrics['udp_receive_times'][1:])  # 跳过第一个（可能很大）
            avg_udp_interval = np.mean(udp_times)
            udp_fps = 1000 / avg_udp_interval if avg_udp_interval > 0 else 0
            print(f"\n【UDP接收统计】")
            print(f"   平均接收间隔: {avg_udp_interval:.1f} ms")
            print(f"   UDP接收频率: {udp_fps:.1f} Hz")
            print(f"   P50间隔: {np.percentile(udp_times, 50):.1f} ms")
            print(f"   P95间隔: {np.percentile(udp_times, 95):.1f} ms")

        # 循环迭代统计
        if len(metrics['loop_iteration_times']) > 0:
            loop_times = np.array(metrics['loop_iteration_times'])
            print(f"\n【循环迭代统计】")
            print(f"   平均迭代时间: {np.mean(loop_times):.1f} ms")
            print(f"   P50迭代时间: {np.percentile(loop_times, 50):.1f} ms")
            print(f"   P95迭代时间: {np.percentile(loop_times, 95):.1f} ms")
            print(f"   最大迭代时间: {np.max(loop_times):.1f} ms")

        # ==========================================
        # 2. 跟踪误差统计
        # ==========================================
        if len(metrics['tracking_errors']) > 0:
            errors = np.array(metrics['tracking_errors']) * 1000  # 转换为mm
            print(f"\n【跟踪误差】(目标位置 vs 实际末端位置)")
            print(f"   平均误差: {np.mean(errors):.2f} mm")
            print(f"   最大误差: {np.max(errors):.2f} mm")
            print(f"   误差标准差: {np.std(errors):.2f} mm")
            print(f"   P50误差: {np.percentile(errors, 50):.2f} mm")
            print(f"   P95误差: {np.percentile(errors, 95):.2f} mm")
            print(f"   P99误差: {np.percentile(errors, 99):.2f} mm")

        # ==========================================
        # 3. 轨迹平滑度指标
        # ==========================================
        if len(metrics['target_positions']) > 2:
            positions = np.array(metrics['target_positions'])
            timestamps = np.array(metrics['timestamps'])

            print(f"\n【轨迹平滑度】(末端轨迹)")

            # 计算速度（一阶导数）
            velocities = []
            for i in range(1, len(positions)):
                dt = timestamps[i] - timestamps[i-1]
                if dt > 0:
                    v = np.linalg.norm(positions[i] - positions[i-1]) / dt
                    velocities.append(v)

            if len(velocities) > 0:
                velocities = np.array(velocities)
                print(f"   平均速度: {np.mean(velocities):.4f} m/s")
                print(f"   最大速度: {np.max(velocities):.4f} m/s")
                print(f"   速度标准差: {np.std(velocities):.4f} m/s")

            # 计算加速度（二阶导数）
            accelerations = []
            for i in range(1, len(velocities)):
                dt = timestamps[i+1] - timestamps[i]
                if dt > 0:
                    a = abs(velocities[i] - velocities[i-1]) / dt
                    accelerations.append(a)

            if len(accelerations) > 0:
                accelerations = np.array(accelerations)
                print(f"   平均加速度: {np.mean(accelerations):.4f} m/s²")
                print(f"   最大加速度: {np.max(accelerations):.4f} m/s²")

            # 计算Jerk（三阶导数）- 平滑度的关键指标
            jerks = []
            for i in range(1, len(accelerations)):
                dt = timestamps[i+2] - timestamps[i+1]
                if dt > 0:
                    j = abs(accelerations[i] - accelerations[i-1]) / dt
                    jerks.append(j)

            if len(jerks) > 0:
                jerks = np.array(jerks)
                print(f"   平均Jerk: {np.mean(jerks):.4f} m/s³")
                print(f"   最大Jerk: {np.max(jerks):.4f} m/s³")

                # 归一化Jerk（Spectral Arc Length）
                if len(jerks) > 1:
                    jerk_rms = np.sqrt(np.mean(jerks**2))
                    print(f"   Jerk RMS: {jerk_rms:.4f} m/s³")

        # ==========================================
        # 4. 关节运动统计
        # ==========================================
        if len(metrics['joint_velocities']) > 0:
            joint_vels = np.array(metrics['joint_velocities'])
            joint_accels = np.array(metrics['joint_accelerations'])

            print(f"\n【关节运动统计】")
            print(f"   关节速度 (rad/s):")
            for i in range(joint_vels.shape[1]):
                vels = np.abs(joint_vels[:, i])
                print(f"      关节{i}: 平均={np.mean(vels):.3f}, 最大={np.max(vels):.3f}, "
                      f"P95={np.percentile(vels, 95):.3f}")

            print(f"   关节加速度 (rad/s²):")
            for i in range(joint_accels.shape[1]):
                accels = np.abs(joint_accels[:, i])
                print(f"      关节{i}: 平均={np.mean(accels):.3f}, 最大={np.max(accels):.3f}, "
                      f"P95={np.percentile(accels, 95):.3f}")

        # ==========================================
        # 5. 控制性能统计
        # ==========================================
        if len(metrics['control_loop_times']) > 0:
            loop_times = np.array(metrics['control_loop_times'])
            ik_times = np.array(metrics['ik_solve_times'])

            print(f"\n【控制性能】")
            print(f"   控制循环时间 (ms):")
            print(f"      平均: {np.mean(loop_times):.2f} ms")
            print(f"      P50: {np.percentile(loop_times, 50):.2f} ms")
            print(f"      P95: {np.percentile(loop_times, 95):.2f} ms")
            print(f"      P99: {np.percentile(loop_times, 99):.2f} ms")
            print(f"      最大: {np.max(loop_times):.2f} ms")

            print(f"   IK求解时间 (ms):")
            print(f"      平均: {np.mean(ik_times):.2f} ms")
            print(f"      P50: {np.percentile(ik_times, 50):.2f} ms")
            print(f"      P95: {np.percentile(ik_times, 95):.2f} ms")
            print(f"      最大: {np.max(ik_times):.2f} ms")

        # ==========================================
        # 6. 安全控制器统计
        # ==========================================
        if hasattr(self, 'safety_controller') and frame_count > 0:
            stats = metrics['safety_stats']
            total_interventions = sum(stats.values())

            print(f"\n【安全控制器】")
            print(f"   总干预次数: {total_interventions}")
            print(f"   干预率: {total_interventions / frame_count * 100:.1f}%")
            print(f"   速度限制触发: {stats['velocity_limited']} 次 "
                  f"({stats['velocity_limited']/frame_count*100:.1f}%)")
            print(f"   加速度限制触发: {stats['acceleration_limited']} 次 "
                  f"({stats['acceleration_limited']/frame_count*100:.1f}%)")
            print(f"   位置限制触发: {stats['position_limited']} 次 "
                  f"({stats['position_limited']/frame_count*100:.1f}%)")
        elif hasattr(self, 'safety_controller'):
            print(f"\n【安全控制器】")
            print(f"   ⚠️ 无有效帧数据，无法计算统计信息")

        print(f"\n{'='*80}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VIST 全流程仿真")
    parser.add_argument("--duration", type=float, default=300.0,
                       help="运行时长（秒），默认300秒")
    parser.add_argument("--limit-freq", action="store_true",
                       help="限制控制频率（模拟真机行为）")
    parser.add_argument("--countdown", type=int, default=5,
                       help="启动前倒计时（秒），默认5秒")
    parser.add_argument("--no-logging", action="store_true",
                       help="禁用数据记录")
    parser.add_argument("--experiment-name", type=str, default="",
                       help="实验名称（可选）")
    args = parser.parse_args()

    simulator = FullFlowSimulator(
        enable_logging=not args.no_logging,
        experiment_name=args.experiment_name if args.experiment_name else None
    )
    simulator.run(duration=args.duration,
                  limit_frequency=args.limit_freq,
                  countdown_seconds=args.countdown)


if __name__ == "__main__":
    main()
