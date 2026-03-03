#!/usr/bin/env python3
"""
VIST Filter ROS2 Node
将VIST核心算法集成到ROS2控制流中

功能:
1. 订阅外骨骼和视觉的关节控制话题
2. 使用策略模式支持5种Baseline算法切换 (GELLO/OneEuro/VIST/FSM/APF)
3. 支持可配置的意图因子组合
4. 发布滤波后的控制指令和性能指标

作者: VIST Team
日期: 2026-02-28 (重构版本)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray, String
import numpy as np
from pathlib import Path
import sys
import yaml
from typing import Optional, Dict, List
import threading
import time
from collections import deque

# 添加项目路径
# 当前文件: /home/ilex/Dev/VIST/ros2_ws/src/nodes/vist_filter_node.py
# ros2_ws 根目录: /home/ilex/Dev/VIST/ros2_ws (用于导入 src.core 等模块)
# VIST 项目根目录: /home/ilex/Dev/VIST (用于访问 config 等目录)
ros2_ws_root = Path(__file__).parent.parent.parent  # /home/ilex/Dev/VIST/ros2_ws
project_root = ros2_ws_root.parent  # /home/ilex/Dev/VIST
sys.path.insert(0, str(ros2_ws_root))

# 导入VIST核心算法
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.intent_detector import ContinuousIntentDetector, IntentFactors
from src.core.ik_solver import PinocchioIKSolver
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.one_euro_filter import OneEuroFilter
from src.core.tcp_compensation import TCPCompensation
from src.config.config_loader import get_config
import pinocchio as pin

# 导入策略模式滤波器架构
from src.filters import FilterFactory, BaseTeleopFilter


# ==================== 频率监控类 ====================

class FrequencyMonitor:
    """频率监控器 - 用于实时监控话题频率"""

    def __init__(self, window_size: int = 100, name: str = "Unknown"):
        """
        初始化频率监控器

        Args:
            window_size: 滑动窗口大小（用于计算平均频率）
            name: 监控器名称
        """
        self.name = name
        self.window_size = window_size
        self.timestamps = deque(maxlen=window_size)
        self.count = 0
        self.last_print_time = time.time()
        self.lock = threading.Lock()

    def tick(self):
        """记录一次事件"""
        with self.lock:
            current_time = time.time()
            self.timestamps.append(current_time)
            self.count += 1

    def get_frequency(self) -> float:
        """
        计算当前频率

        Returns:
            频率 (Hz)
        """
        with self.lock:
            if len(self.timestamps) < 2:
                return 0.0

            time_span = self.timestamps[-1] - self.timestamps[0]
            if time_span <= 0:
                return 0.0

            return (len(self.timestamps) - 1) / time_span

    def get_stats(self) -> Dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            freq = self.get_frequency()
            return {
                'name': self.name,
                'frequency': freq,
                'total_count': self.count,
                'window_size': len(self.timestamps)
            }

    def reset(self):
        """重置统计"""
        with self.lock:
            self.timestamps.clear()
            self.count = 0


# ==================== VIST Filter Node ====================

class VISTFilterNode(Node):
    """VIST滤波ROS2节点"""

    def __init__(self):
        super().__init__('vist_filter_node')

        # 声明参数
        self.declare_node_parameters()

        # 加载配置
        self.load_config()

        # 初始化状态
        self.exo_data: Optional[JointState] = None
        self.vision_data: Optional[JointState] = None
        self.robot_data: Optional[JointState] = None  # 机械臂真实反馈数据
        self.current_state: Optional[np.ndarray] = None
        self.last_update_time = self.get_clock().now()

        # 性能监控状态
        self.last_position: Optional[np.ndarray] = None
        self.last_velocity: Optional[np.ndarray] = None
        self.last_timestamp: Optional[float] = None

        # 线程锁
        self.exo_lock = threading.Lock()
        self.vision_lock = threading.Lock()
        self.robot_lock = threading.Lock()  # 机械臂数据锁
        self.state_lock = threading.Lock()

        # 频率监控器
        self.freq_exo_receive = FrequencyMonitor(window_size=100, name="外骨骼接收")
        self.freq_vision_receive = FrequencyMonitor(window_size=100, name="视觉接收")
        self.freq_filter_output = FrequencyMonitor(window_size=100, name="滤波输出")
        self.freq_robot_feedback = FrequencyMonitor(window_size=100, name="机械臂反馈")
        self.freq_timer_callback = FrequencyMonitor(window_size=100, name="定时器回调")

        # 频率打印定时器（每秒打印一次）
        self.freq_print_timer = None
        self.freq_print_interval = 1.0  # 秒

        # 初始化VIST核心算法
        self.initialize_vist_components()

        # 创建订阅器
        self.create_subscribers()

        # 创建发布器
        self.create_publishers()

        # 创建定时器 (高频控制循环)
        timer_period = 1.0 / self.output_freq_hz
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.get_logger().info(f'Timer created with period: {timer_period:.4f}s ({self.output_freq_hz}Hz)')

        # 立即测试定时器是否会被调用
        self.get_logger().info('⏰ Testing if timer will be called...')
        self._timer_test_flag = False

        # 频率打印定时器已禁用 - 用户使用rqt查看频率
        # self.freq_print_timer = self.create_timer(self.freq_print_interval, self.print_frequencies)

        self.get_logger().info('VIST Filter Node initialized')
        self.print_config()

    def declare_node_parameters(self):
        """
        声明ROS2参数

        从 baseline_filters_config.yaml 加载默认值
        启动命令示例：
            python3 src/nodes/vist_filter_node.py --ros-args --params-file config/baseline_filters_config.yaml
        """
        # 加载默认配置文件
        default_config_path = project_root / "config" / "baseline_filters_config.yaml"
        default_params = self._load_default_params(default_config_path)

        # 使用配置文件中的值声明参数
        for param_name, default_value in default_params.items():
            self.declare_parameter(param_name, default_value)

    def _load_default_params(self, config_path: Path) -> Dict:
        """
        从 YAML 配置文件加载默认参数

        Args:
            config_path: 配置文件路径

        Returns:
            参数字典
        """
        import yaml

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # 提取 /vist_filter_node 下的参数（支持带/不带斜杠）
            node_params = config.get('/vist_filter_node', config.get('vist_filter_node', {})).get('ros__parameters', {})

            # 展平嵌套的参数（如 oneeuro.min_cutoff）
            flat_params = {}
            for key, value in node_params.items():
                if isinstance(value, dict):
                    # 嵌套参数（如 oneeuro: {min_cutoff: 1.0}）
                    for sub_key, sub_value in value.items():
                        flat_params[f"{key}.{sub_key}"] = sub_value
                else:
                    flat_params[key] = value

            # 调试：打印 filter_type 的值
            if 'filter_type' in flat_params:
                self.get_logger().info(f'🔍 DEBUG: 配置文件中的 filter_type = "{flat_params["filter_type"]}"')
            else:
                self.get_logger().warn('⚠️ DEBUG: 配置文件中没有找到 filter_type 参数！')

            self.get_logger().info(f'从配置文件加载了 {len(flat_params)} 个参数')
            return flat_params

        except FileNotFoundError:
            self.get_logger().warn(f'配置文件未找到: {config_path}，使用硬编码默认值')
            # 返回最小必需参数
            return {
                'filter_type': 'gello',
                'output_freq_hz': 80.0,
                'arm_side': 'left',
                'exo_left_topic': '/left_arm_joint_control',
                'filtered_left_topic': '/filtered_left_joint_control',
                'vist_config_path': 'config/system_config.yaml',
                'enable_performance_monitoring': True,
                'performance_topic': '/vist_performance'
            }
        except Exception as e:
            self.get_logger().error(f'加载配置文件失败: {e}')
            raise

    def load_config(self):
        """加载配置参数"""
        # 话题配置
        self.exo_left_topic = self.get_parameter('exo_left_topic').value
        self.exo_right_topic = self.get_parameter('exo_right_topic').value
        self.vision_left_topic = self.get_parameter('vision_left_topic').value
        self.vision_right_topic = self.get_parameter('vision_right_topic').value
        self.filtered_left_topic = self.get_parameter('filtered_left_topic').value
        self.filtered_right_topic = self.get_parameter('filtered_right_topic').value

        # 控制参数
        self.output_freq_hz = self.get_parameter('output_freq_hz').value
        self.arm_side = self.get_parameter('arm_side').value

        # 滤波器类型
        self.filter_type = self.get_parameter('filter_type').value

        # 调试：打印实际读取的 filter_type
        self.get_logger().info(f'🔍 DEBUG: 从参数读取的 filter_type = "{self.filter_type}" (type: {type(self.filter_type).__name__})')

        # 意图因子
        self.intent_factors = {
            'distance': self.get_parameter('enable_distance_factor').value,
            'velocity': self.get_parameter('enable_velocity_factor').value,
            'alignment': self.get_parameter('enable_alignment_factor').value,
            'conflict': self.get_parameter('enable_conflict_detection').value
        }

        # 目标位姿（用于FSM和APF）
        self.target_pose = np.array([
            self.get_parameter('target_pose.x').value,
            self.get_parameter('target_pose.y').value,
            self.get_parameter('target_pose.z').value,
            self.get_parameter('target_pose.rx').value,
            self.get_parameter('target_pose.ry').value,
            self.get_parameter('target_pose.rz').value
        ])

        # VIST配置
        vist_config_path = self.get_parameter('vist_config_path').value
        self.vist_config = get_config(project_root / vist_config_path)

        # 性能监控
        self.enable_performance_monitoring = self.get_parameter('enable_performance_monitoring').value
        self.performance_topic = self.get_parameter('performance_topic').value

    def initialize_vist_components(self):
        """初始化VIST核心组件 - 使用策略模式"""
        self.get_logger().info(f'Initializing VIST components with filter type: {self.filter_type}')

        # 初始化IK求解器
        urdf_path = project_root / "config" / self.vist_config.robot_model_urdf_file
        end_effector_frame = self.vist_config.robot_model_end_effector_frame

        # 根据 arm_side 选择正确的控制关节
        if self.arm_side == 'left':
            controlled_joints = [
                'Left_Shoulder_Pitch_Joint',
                'Left_Shoulder_Roll_Joint',
                'Left_Shoulder_Yaw_Joint',
                'Left_Elbow_Pitch_Joint',
                'Left_Wrist_Yaw_Joint',
                'Left_Wrist_Pitch_Joint',
                'Left_Wrist_Roll_Joint'
            ]
        else:  # right
            controlled_joints = [
                'Right_Shoulder_Pitch_Joint',
                'Right_Shoulder_Roll_Joint',
                'Right_Shoulder_Yaw_Joint',
                'Right_Elbow_Pitch_Joint',
                'Right_Wrist_Yaw_Joint',
                'Right_Wrist_Pitch_Joint',
                'Right_Wrist_Roll_Joint'
            ]

        self.ik_solver = PinocchioIKSolver(
            urdf_path=str(urdf_path),
            end_effector_frame=end_effector_frame,
            controlled_joints=controlled_joints
        )

        # 初始化TCP补偿器
        self.tcp_compensation = TCPCompensation()

        # 初始化意图检测器（用于FSM）
        self.intent_detector = ContinuousIntentDetector(self.vist_config)

        # 使用工厂模式创建滤波器
        self.current_filter = self._create_filter_strategy()
        self.get_logger().info(f'Filter strategy created: {self.filter_type}')

    def _create_filter_strategy(self) -> BaseTeleopFilter:
        """
        使用工厂模式创建滤波器策略

        Returns:
            滤波器实例
        """
        # 准备通用参数
        common_kwargs = {
            'ik_solver': self.ik_solver,
            'tcp_compensation': self.tcp_compensation,
            'target_pose': self.target_pose
        }

        # 根据滤波器类型添加特定参数
        if self.filter_type == 'oneeuro':
            common_kwargs.update({
                'min_cutoff': self.get_parameter('oneeuro.min_cutoff').value,
                'beta': self.get_parameter('oneeuro.beta').value
            })

        elif self.filter_type == 'vist':
            # VIST 需要完整的配置对象和几何求解器
            geometric_solver = None
            if self.vist_config.vist_geometric_solver_enabled:
                geometric_solver = GeometricArmSolver(
                    model=self.ik_solver.model,
                    data=self.ik_solver.data,
                    controlled_joints=self.ik_solver.controlled_indices,
                    ee_frame_id=self.ik_solver.ee_frame_id,
                    config=self.vist_config
                )
            common_kwargs.update({
                'vist_config': self.vist_config,
                'geometric_solver': geometric_solver
            })

        elif self.filter_type == 'fsm':
            # 虚拟夹具FSM参数
            common_kwargs.update({
                'socket_center_xy': self.get_parameter('fsm.socket_center_xy').value,
                'cylinder_radius': self.get_parameter('fsm.cylinder_radius').value,
                'xy_scale_factor': self.get_parameter('fsm.xy_scale_factor').value,
                'z_scale_factor': self.get_parameter('fsm.z_scale_factor').value,
                'arm_side': self.arm_side  # 传递机械臂侧信息
            })

        elif self.filter_type == 'apf':
            common_kwargs.update({
                'attractive_gain': self.get_parameter('apf.attractive_gain').value,
                'repulsive_gain': self.get_parameter('apf.repulsive_gain').value,
                'obstacle_positions': []  # 可以从参数或话题动态加载
            })

        # 使用工厂创建滤波器
        try:
            return FilterFactory.create_filter(self.filter_type, **common_kwargs)
        except ValueError as e:
            self.get_logger().error(str(e))
            self.get_logger().warn('回退到 GELLO 直通模式')
            return FilterFactory.create_filter('gello', **common_kwargs)

    def create_subscribers(self):
        """创建订阅器"""
        # 选择对应臂的话题
        exo_topic = self.exo_left_topic if self.arm_side == 'left' else self.exo_right_topic
        vision_topic = self.vision_left_topic if self.arm_side == 'left' else self.vision_right_topic

        self.exo_sub = self.create_subscription(
            JointState,
            exo_topic,
            self.exo_callback,
            10
        )

        self.vision_sub = self.create_subscription(
            JointState,
            vision_topic,
            self.vision_callback,
            10
        )

        # 订阅机械臂反馈话题（用于 FSM 的 FK 计算）
        # lbot_driver 发布的话题：robot1/left_arm/joint_states 或 robot1/right_arm/joint_states
        robot_feedback_topic = f'robot1/{self.arm_side}_arm/joint_states'
        self.robot_feedback_sub = self.create_subscription(
            JointState,
            robot_feedback_topic,
            self.robot_feedback_callback,
            10
        )

        self.get_logger().info(f'Subscribed to: {exo_topic}, {vision_topic}, {robot_feedback_topic}')

    def create_publishers(self):
        """创建发布器"""
        # 选择对应臂的话题
        filtered_topic = self.filtered_left_topic if self.arm_side == 'left' else self.filtered_right_topic

        self.filtered_pub = self.create_publisher(
            JointState,
            filtered_topic,
            10
        )

        # 性能监控发布器
        if self.enable_performance_monitoring:
            self.performance_pub = self.create_publisher(
                Float64MultiArray,
                self.performance_topic,
                10
            )

        # 意图因子发布器（用于可视化）
        self.intent_pub = self.create_publisher(
            Float64MultiArray,
            '/vist_intent_factors',
            10
        )

        self.get_logger().info(f'Publishing to: {filtered_topic}')

    def exo_callback(self, msg: JointState):
        """外骨骼数据回调"""
        with self.exo_lock:
            self.exo_data = msg
            self.latest_exo_data = msg
            self.freq_exo_receive.tick()  # 记录接收频率

    def vision_callback(self, msg: JointState):
        """视觉数据回调"""
        with self.vision_lock:
            self.vision_data = msg
            self.freq_vision_receive.tick()  # 记录接收频率

    def robot_feedback_callback(self, msg: JointState):
        """机械臂反馈数据回调（保存真实关节角）"""
        with self.robot_lock:
            self.robot_data = msg
            self.freq_robot_feedback.tick()  # 记录机械臂反馈频率

    def timer_callback(self):
        """高频控制循环 - 使用策略模式统一处理"""
        # 首次调用时打印
        if not hasattr(self, '_timer_test_flag') or not self._timer_test_flag:
            self.get_logger().info('🎉 Timer callback IS BEING CALLED!')
            self._timer_test_flag = True

        # 记录定时器回调频率
        self.freq_timer_callback.tick()

        # 获取数据副本
        with self.exo_lock:
            exo_data = self.exo_data
        with self.vision_lock:
            vision_data = self.vision_data
        with self.robot_lock:
            robot_data = self.robot_data  # 获取机械臂真实反馈数据

        # 检查数据有效性 - 如果没有数据，使用默认零位姿态
        if exo_data is None and vision_data is None:
            # 使用默认零位姿态（7个关节，全部为0）
            q_in = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        else:
            # 选择数据源（优先外骨骼）
            source_data = exo_data if exo_data is not None else vision_data
            if source_data is None:
                return

            # 提取输入关节角
            q_in = list(source_data.position)

        # 计算时间步长
        current_time = self.get_clock().now().nanoseconds / 1e9
        if self.last_timestamp is None:
            dt = 1.0 / self.output_freq_hz
        else:
            dt = current_time - self.last_timestamp
            if dt <= 0 or dt > 1.0:
                dt = 1.0 / self.output_freq_hz
        self.last_timestamp = current_time

        # 验证输入维度
        if len(q_in) != 7:
            self.get_logger().error(
                f'❌ 输入关节数量不正确: {len(q_in)}, 期望 7 个关节'
            )
            return

        # 使用策略模式应用滤波器
        try:
            # 对于 FSM 滤波器，计算机械臂真实法兰位置
            robot_joints = None
            if self.filter_type == 'fsm' and robot_data is not None:
                try:
                    # 直接传递关节角，不在这里计算 FK
                    # 提取机械臂真实关节角
                    robot_q = np.array(robot_data.position)

                    # 🔍 单位检测：如果数值很大（>10），很可能是角度而非弧度
                    if len(robot_q) == 7:
                        max_val = np.max(np.abs(robot_q))
                        if max_val > 10:
                            # 很可能是角度，转换为弧度
                            self.get_logger().warn(f'⚠️ 检测到关节角可能是角度（最大值={max_val:.1f}），自动转换为弧度')
                            robot_q = np.deg2rad(robot_q)

                        # 将单臂关节角赋值给 robot_joints（FSM 内部会处理扩展）
                        robot_joints = robot_q

                except Exception as e:
                    self.get_logger().warn(f'⚠️ 无法提取机械臂真实关节角: {e}')

            # 调用滤波器（FSM 会使用 robot_joints，其他滤波器会忽略）
            # 🔍 VIST滤波器单位转换：LinkerTA输出的是角度（degree），需要转换为弧度
            if self.filter_type == 'vist':
                q_in_array = np.array(q_in)
                q_in_rad = np.deg2rad(q_in_array)

                # 🔧 关节方向修正：反转第3和第5关节（索引2和4）
                q_in_rad[2] = -q_in_rad[2]
                q_in_rad[4] = -q_in_rad[4]

                # 转换回列表
                q_in_rad = q_in_rad.tolist()

                # 首次转换时打印日志
                if not hasattr(self, '_vist_unit_conversion_logged'):
                    self.get_logger().info('✓ VIST滤波器：遥操臂输入单位转换（角度 → 弧度）')
                    self.get_logger().info('✓ VIST滤波器：关节方向修正（反转索引2和4）')
                    self._vist_unit_conversion_logged = True

                if robot_joints is not None:
                    q_out = self.current_filter.update(q_in_rad, dt, robot_joints=robot_joints)
                else:
                    q_out = self.current_filter.update(q_in_rad, dt)
            else:
                # 其他滤波器（FSM等）保持原始单位
                if robot_joints is not None:
                    q_out = self.current_filter.update(q_in, dt, robot_joints=robot_joints)
                else:
                    q_out = self.current_filter.update(q_in, dt)

            if q_out is None:
                self.get_logger().error('❌ Filter returned None!')
                q_out = q_in

            filtered_state = np.array(q_out)

            # 🔍 关节序号验证（每100帧打印一次）
            if not hasattr(self, '_joint_mapping_check_count'):
                self._joint_mapping_check_count = 0
            self._joint_mapping_check_count += 1

            if self._joint_mapping_check_count % 100 == 0:
                self.get_logger().info(f'\n🔍 关节序号验证 (第{self._joint_mapping_check_count}帧):')
                self.get_logger().info(f'  输入 q_in:  {[f"{x:6.3f}" for x in q_in]}')
                self.get_logger().info(f'  输出 q_out: {[f"{x:6.3f}" for x in q_out]}')
                delta = np.array(q_out) - np.array(q_in if self.filter_type != "vist" else q_in_rad)
                self.get_logger().info(f'  差值 Δq:    {[f"{x:6.3f}" for x in delta]}')
                self.get_logger().info(f'  最大变化: Joint {np.argmax(np.abs(delta))}, Δ={np.max(np.abs(delta)):.3f}')

            # 发布滤波后的状态
            self.publish_filtered_state(filtered_state)

            # 发布性能数据和意图因子
            self.publish_metrics(filtered_state, q_in, dt)

        except Exception as e:
            import traceback
            self.get_logger().error(f'❌ Error in timer callback: {e}')
            self.get_logger().error(f'Traceback: {traceback.format_exc()}')
            # 失败时直通
            self.get_logger().warn('⚠️ Falling back to passthrough mode')
            self.publish_filtered_state(np.array(q_in))

    def publish_filtered_state(self, filtered_state: np.ndarray):
        """
        发布滤波后的关节状态

        Args:
            filtered_state: 滤波后的关节角度数组
        """
        try:
            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'base_link'
            msg.name = [f'joint_{i}' for i in range(len(filtered_state))]
            msg.position = filtered_state.tolist()

            # 发布滤波后的数据
            self.filtered_pub.publish(msg)

            # 记录发布频率
            self.freq_filter_output.tick()

        except Exception as e:
            self.get_logger().error(f'❌ Error in publish_filtered_state: {e}')
            import traceback
            self.get_logger().error(f'Traceback: {traceback.format_exc()}')

    def publish_metrics(self, filtered_state: np.ndarray, input_state: list, dt: float):
        """
        发布性能指标和意图因子（适用于所有滤波器类型）

        Args:
            filtered_state: 滤波后的关节状态
            input_state: 输入关节状态
            dt: 时间步长
        """
        try:
            # 默认意图因子值
            alpha = 0.0
            alpha_geo = 0.0
            alpha_vel = 0.0
            alpha_alignment = 0.0
            Q_norm = 0.0
            R_norm = 0.0
            K_norm = 0.0

            # 尝试从滤波器获取意图因子和协方差范数
            if self.filter_type == 'vist' and hasattr(self.current_filter, 'vist_filter'):
                vist_filter = self.current_filter.vist_filter
                if hasattr(vist_filter, 'alpha'):
                    alpha = float(vist_filter.alpha)
                    alpha_geo = float(getattr(vist_filter, 'alpha_geo', 0.0))
                    alpha_vel = float(getattr(vist_filter, 'alpha_vel', 0.0))
                    alpha_alignment = float(getattr(vist_filter, 'alpha_alignment', 0.0))
                    Q_norm = float(getattr(vist_filter, 'Q_norm', 0.0))
                    R_norm = float(getattr(vist_filter, 'R_norm', 0.0))
                    K_norm = float(getattr(vist_filter, 'K_norm', 0.0))

            # 发布意图因子和协方差范数
            intent_msg = Float64MultiArray()
            intent_msg.data = [alpha, alpha_geo, alpha_vel, alpha_alignment, Q_norm, R_norm, K_norm]
            self.intent_pub.publish(intent_msg)

            # 发布性能数据
            if self.enable_performance_monitoring:
                perf_msg = Float64MultiArray()

                # 计算性能指标
                position_error = np.linalg.norm(filtered_state - np.array(input_state))

                # 计算速度（如果有历史数据）
                if self.last_position is not None:
                    velocity = np.linalg.norm(filtered_state - self.last_position) / dt
                else:
                    velocity = 0.0

                # 计算加速度（如果有历史速度）
                if self.last_velocity is not None:
                    acceleration = abs(velocity - self.last_velocity) / dt
                else:
                    acceleration = 0.0

                # 更新历史数据
                self.last_position = filtered_state.copy()
                self.last_velocity = velocity

                perf_msg.data = [
                    float(position_error),  # 位置误差
                    float(velocity),  # 速度
                    float(acceleration),  # 加速度
                    float(dt * 1000),  # 时间步长(ms)
                    float(alpha)  # 意图因子
                ]
                self.performance_pub.publish(perf_msg)

        except Exception as e:
            # 静默失败，不影响主控制循环
            pass

    def print_frequencies(self):
        """定期打印所有频率信息"""
        try:
            # 获取所有频率统计
            exo_stats = self.freq_exo_receive.get_stats()
            vision_stats = self.freq_vision_receive.get_stats()
            output_stats = self.freq_filter_output.get_stats()
            robot_stats = self.freq_robot_feedback.get_stats()
            timer_stats = self.freq_timer_callback.get_stats()

            # 使用 logger 而不是 print，避免输出缓冲问题
            self.get_logger().info('='*80)
            self.get_logger().info(f"{'频率监控报告':^80}")
            self.get_logger().info('='*80)
            self.get_logger().info(f"外骨骼接收: {exo_stats['frequency']:>10.2f} Hz (总计: {exo_stats['total_count']})")
            self.get_logger().info(f"视觉接收:   {vision_stats['frequency']:>10.2f} Hz (总计: {vision_stats['total_count']})")
            self.get_logger().info(f"定时器回调: {timer_stats['frequency']:>10.2f} Hz (总计: {timer_stats['total_count']})")
            self.get_logger().info(f"滤波输出:   {output_stats['frequency']:>10.2f} Hz (总计: {output_stats['total_count']})")
            self.get_logger().info(f"机械臂反馈: {robot_stats['frequency']:>10.2f} Hz (总计: {robot_stats['total_count']})")
            self.get_logger().info('='*80)

            # 检测频率异常
            expected_freq = self.output_freq_hz
            tolerance = 0.1  # 10% 容差

            if abs(timer_stats['frequency'] - expected_freq) > expected_freq * tolerance:
                self.get_logger().warn(f"⚠️ 定时器回调频率异常: {timer_stats['frequency']:.2f} Hz (期望: {expected_freq:.2f} Hz)")

            if abs(output_stats['frequency'] - expected_freq) > expected_freq * tolerance:
                self.get_logger().warn(f"⚠️ 滤波输出频率异常: {output_stats['frequency']:.2f} Hz (期望: {expected_freq:.2f} Hz)")

            # 检测低频率异常
            if exo_stats['frequency'] < 1.0:
                self.get_logger().warn(f"⚠️ 外骨骼数据接收频率过低: {exo_stats['frequency']:.2f} Hz")

            if robot_stats['frequency'] < 1.0:
                self.get_logger().warn(f"⚠️ 机械臂反馈频率过低: {robot_stats['frequency']:.2f} Hz")

        except Exception as e:
            self.get_logger().error(f'❌ Error in print_frequencies: {e}')
            import traceback
            self.get_logger().error(f'Traceback: {traceback.format_exc()}')

    def switch_filter(self, new_filter_type: str):
        """
        动态切换滤波器（可通过服务调用）

        Args:
            new_filter_type: 新的滤波器类型
        """
        self.get_logger().info(f'切换滤波器: {self.filter_type} -> {new_filter_type}')

        # 重置当前滤波器
        self.current_filter.reset()

        # 更新参数
        self.set_parameters([
            rclpy.parameter.Parameter('filter_type', rclpy.Parameter.Type.STRING, new_filter_type)
        ])

        # 重新创建滤波器
        self.filter_type = new_filter_type
        self.current_filter = self._create_filter_strategy()

        self.get_logger().info(f'滤波器切换完成: {new_filter_type}')

    def print_config(self):
        """打印配置信息"""
        self.get_logger().info('========== VIST Filter Node Config ==========')
        self.get_logger().info(f'Arm side: {self.arm_side}')
        self.get_logger().info(f'Filter type: {self.filter_type}')
        self.get_logger().info(f'Output frequency: {self.output_freq_hz} Hz')
        self.get_logger().info(f'Target pose: {self.target_pose}')
        self.get_logger().info(f'Intent factors: {self.intent_factors}')
        self.get_logger().info(f'Performance monitoring: {self.enable_performance_monitoring}')
        self.get_logger().info('=============================================')


def main(args=None):
    rclpy.init(args=args)
    node = VISTFilterNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 保存监控数据（如果使用VIST滤波器）
        if hasattr(node, 'current_filter') and hasattr(node.current_filter, 'save_monitor_data'):
            node.get_logger().info('正在保存监控数据...')
            node.current_filter.save_monitor_data()

        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

