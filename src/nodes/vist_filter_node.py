#!/usr/bin/env python3
"""
VIST Filter ROS2 Node
将VIST核心算法集成到ROS2控制流中

功能:
1. 订阅外骨骼和视觉的关节控制话题
2. 使用VIST卡尔曼滤波器融合双源数据
3. 支持可切换的滤波器类型 (EMA/OneEuro/VIST)
4. 支持可配置的意图因子组合
5. 发布滤波后的控制指令和性能指标

作者: VIST Team
日期: 2026-02-24
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

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入VIST核心算法
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.intent_detector import ContinuousIntentDetector, IntentFactors
from src.core.ik_solver import PinocchioIKSolver
from src.core.geometric_arm_solver import GeometricArmSolver
from src.core.one_euro_filter import OneEuroFilter
from src.config.config_loader import get_config
import pinocchio as pin


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
        self.current_state: Optional[np.ndarray] = None
        self.last_update_time = self.get_clock().now()

        # 性能监控状态
        self.last_position: Optional[np.ndarray] = None
        self.last_velocity: Optional[np.ndarray] = None
        self.last_timestamp: Optional[float] = None

        # 线程锁
        self.exo_lock = threading.Lock()
        self.vision_lock = threading.Lock()
        self.state_lock = threading.Lock()

        # 初始化VIST核心算法
        self.initialize_vist_components()

        # 创建订阅器
        self.create_subscribers()

        # 创建发布器
        self.create_publishers()

        # 创建定时器 (高频控制循环)
        timer_period = 1.0 / self.output_freq_hz
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.get_logger().info('VIST Filter Node initialized')
        self.print_config()

    def declare_node_parameters(self):
        """
        声明ROS2参数

        注意：这里的默认值仅作为后备值使用。
        实际运行时应通过 --params-file 参数传递配置文件来覆盖这些默认值。
        启动命令示例：
            python3 src/nodes/vist_filter_node.py --ros-args --params-file config/vist_filter_config.yaml
        """
        # 话题配置
        # 默认值与实际话题名称匹配（linkerta_node发布的话题）
        self.declare_parameter('exo_left_topic', '/left_arm_joint_control')
        self.declare_parameter('exo_right_topic', '/right_arm_joint_control')
        self.declare_parameter('vision_left_topic', '/vision_left_joint_control')
        self.declare_parameter('vision_right_topic', '/vision_right_joint_control')
        self.declare_parameter('filtered_left_topic', '/filtered_left_joint_control')
        self.declare_parameter('filtered_right_topic', '/filtered_right_joint_control')

        # 控制参数
        self.declare_parameter('output_freq_hz', 80.0)  # 匹配遥操臂频率（80Hz）
        self.declare_parameter('arm_side', 'left')  # 'left' or 'right'

        # 滤波器选择
        self.declare_parameter('filter_type', 'passthrough')  # passthrough, ema, one_euro, vist_kalman

        # 意图因子配置（默认关闭，用于baseline实验）
        self.declare_parameter('enable_distance_factor', False)
        self.declare_parameter('enable_velocity_factor', False)
        self.declare_parameter('enable_alignment_factor', False)
        self.declare_parameter('enable_conflict_detection', False)

        # EMA参数
        self.declare_parameter('ema_alpha', 0.3)

        # One Euro参数
        self.declare_parameter('one_euro_min_cutoff', 1.0)
        self.declare_parameter('one_euro_beta', 0.007)

        # VIST配置文件路径
        self.declare_parameter('vist_config_path', 'config/system_config.yaml')

        # 性能监控
        self.declare_parameter('enable_performance_monitoring', True)
        self.declare_parameter('performance_topic', '/vist_performance')

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

        # 意图因子
        self.intent_factors = {
            'distance': self.get_parameter('enable_distance_factor').value,
            'velocity': self.get_parameter('enable_velocity_factor').value,
            'alignment': self.get_parameter('enable_alignment_factor').value,
            'conflict': self.get_parameter('enable_conflict_detection').value
        }

        # 滤波器参数
        self.ema_alpha = self.get_parameter('ema_alpha').value
        self.one_euro_min_cutoff = self.get_parameter('one_euro_min_cutoff').value
        self.one_euro_beta = self.get_parameter('one_euro_beta').value

        # VIST配置
        vist_config_path = self.get_parameter('vist_config_path').value
        self.vist_config = get_config(project_root / vist_config_path)

        # 性能监控
        self.enable_performance_monitoring = self.get_parameter('enable_performance_monitoring').value
        self.performance_topic = self.get_parameter('performance_topic').value

    def initialize_vist_components(self):
        """初始化VIST核心组件"""
        self.get_logger().info(f'Initializing VIST components with filter type: {self.filter_type}')

        # 初始化IK求解器
        urdf_path = project_root / "config" / self.vist_config.robot_model_urdf_file
        # robot_model_end_effector_frame 会根据 hardware_arm_side 自动选择
        end_effector_frame = self.vist_config.robot_model_end_effector_frame

        self.ik_solver = PinocchioIKSolver(
            urdf_path=str(urdf_path),
            end_effector_frame=end_effector_frame
        )

        # 初始化几何求解器（如果启用）
        geometric_solver = None
        if self.vist_config.vist_geometric_solver_enabled:
            geometric_solver = GeometricArmSolver(
                model=self.ik_solver.model,
                data=self.ik_solver.data,
                controlled_joints=self.ik_solver.controlled_indices,
                ee_frame_id=self.ik_solver.ee_frame_id,
                config=self.vist_config
            )

        # 根据滤波器类型初始化
        if self.filter_type == 'vist_kalman':
            # VIST卡尔曼滤波器
            self.vist_filter = VISTKalmanFilter(
                self.ik_solver,
                self.vist_config,
                geometric_solver=geometric_solver
            )
            self.get_logger().info('VIST Kalman Filter initialized')

        elif self.filter_type == 'one_euro':
            # One Euro滤波器
            self.one_euro_filters = []
            for i in range(7):  # 7个关节
                self.one_euro_filters.append(
                    OneEuroFilter(
                        min_cutoff=self.one_euro_min_cutoff,
                        beta=self.one_euro_beta
                    )
                )
            self.get_logger().info('One Euro Filters initialized')

        elif self.filter_type == 'ema':
            # EMA滤波器（简单实现）
            self.ema_state = None
            self.get_logger().info(f'EMA Filter initialized (alpha={self.ema_alpha})')

        else:
            self.get_logger().warn(f'Unknown filter type: {self.filter_type}, using passthrough')

        # 初始化意图检测器（如果使用VIST）
        if self.filter_type == 'vist_kalman':
            self.intent_detector = ContinuousIntentDetector(self.vist_config)
            self.get_logger().info(f'Intent Detector initialized with factors: {self.intent_factors}')

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

        self.get_logger().info(f'Subscribed to: {exo_topic}, {vision_topic}')

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
            # self.get_logger().debug(f'Received exo data: {len(msg.position)} joints')

    def vision_callback(self, msg: JointState):
        """视觉数据回调"""
        with self.vision_lock:
            self.vision_data = msg
            # self.get_logger().debug(f'Received vision data: {len(msg.position)} joints')

    def timer_callback(self):
        """高频控制循环"""
        # 获取数据副本
        with self.exo_lock:
            exo_data = self.exo_data
        with self.vision_lock:
            vision_data = self.vision_data

        # 检查数据有效性
        if exo_data is None and vision_data is None:
            # self.get_logger().warn_throttle(1.0, 'No input data available')
            return

        # 根据滤波器类型处理
        try:
            if self.filter_type == 'vist_kalman':
                filtered_state = self.process_vist_kalman(exo_data, vision_data)
            elif self.filter_type == 'one_euro':
                filtered_state = self.process_one_euro(exo_data, vision_data)
            elif self.filter_type == 'ema':
                filtered_state = self.process_ema(exo_data, vision_data)
            else:
                # Passthrough
                filtered_state = self.process_passthrough(exo_data, vision_data)

            if filtered_state is not None:
                # 发布滤波后的状态
                self.publish_filtered_state(filtered_state)

                # 发布性能指标
                if self.enable_performance_monitoring:
                    self.publish_performance_metrics(filtered_state)

        except Exception as e:
            self.get_logger().error(f'Error in timer callback: {e}')

    def process_vist_kalman(self, exo_data: Optional[JointState],
                           vision_data: Optional[JointState]) -> Optional[np.ndarray]:
        """使用VIST卡尔曼滤波器处理"""
        # 双源融合逻辑
        if exo_data is not None and vision_data is not None:
            # 同时有外骨骼和视觉数据 - 完整的VIST融合
            q_exo = np.array(exo_data.position)
            q_vision = np.array(vision_data.position)

            # 计算意图因子
            intent_factor = self.compute_intent_factor(exo_data, vision_data)

            # 更新卡尔曼滤波器（双源观测）
            z = np.concatenate([q_exo, q_vision])
            self.vist_filter.update(z, intent_factor)

            # 发布意图因子（用于可视化）
            self.publish_intent_factors(intent_factor)

        elif exo_data is not None:
            # 只有外骨骼数据 - 高频本体感觉
            q_exo = np.array(exo_data.position)
            self.vist_filter.update_human_only(q_exo)

        elif vision_data is not None:
            # 只有视觉数据 - 低频意图
            q_vision = np.array(vision_data.position)
            self.vist_filter.update_vision_only(q_vision)

        # 获取滤波后的状态
        return self.vist_filter.get_state()[:7]  # 只返回位置部分

    def process_one_euro(self, exo_data: Optional[JointState],
                        vision_data: Optional[JointState]) -> Optional[np.ndarray]:
        """使用One Euro滤波器处理"""
        # 选择数据源（优先外骨骼）
        source_data = exo_data if exo_data is not None else vision_data
        if source_data is None:
            return None

        q = np.array(source_data.position)
        current_time = self.get_clock().now().nanoseconds / 1e9

        # 对每个关节应用One Euro滤波
        filtered_q = np.zeros_like(q)
        for i in range(min(len(q), len(self.one_euro_filters))):
            filtered_q[i] = self.one_euro_filters[i].filter(q[i], current_time)

        return filtered_q

    def process_ema(self, exo_data: Optional[JointState],
                   vision_data: Optional[JointState]) -> Optional[np.ndarray]:
        """使用EMA滤波器处理"""
        # 选择数据源（优先外骨骼）
        source_data = exo_data if exo_data is not None else vision_data
        if source_data is None:
            return None

        q = np.array(source_data.position)

        # EMA滤波: x_new = alpha * x_current + (1 - alpha) * x_prev
        if self.ema_state is None:
            self.ema_state = q
        else:
            self.ema_state = self.ema_alpha * q + (1 - self.ema_alpha) * self.ema_state

        return self.ema_state

    def process_passthrough(self, exo_data: Optional[JointState],
                          vision_data: Optional[JointState]) -> Optional[np.ndarray]:
        """直通模式（无滤波）"""
        source_data = exo_data if exo_data is not None else vision_data
        if source_data is None:
            return None
        return np.array(source_data.position)

    def compute_intent_factor(self, exo_data: JointState,
                              vision_data: JointState) -> float:
        """计算意图因子"""
        try:
            # 获取当前末端位置
            q_current = np.array(exo_data.position)
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_current)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            current_pos = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id].translation

            # 获取目标末端位置（从视觉数据）
            q_target = np.array(vision_data.position)
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_target)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            target_pos = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id].translation

            # 计算速度（如果有速度数据）
            if hasattr(exo_data, 'velocity') and len(exo_data.velocity) > 0:
                # 使用关节速度计算末端速度
                J = pin.computeFrameJacobian(
                    self.ik_solver.model,
                    self.ik_solver.data,
                    q_current,
                    self.ik_solver.ee_frame_id,
                    pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
                )
                q_dot = np.array(exo_data.velocity)
                velocity = J[:3, :] @ q_dot  # 只取线速度部分
            else:
                # 使用数值微分估计速度
                if self.last_position is not None and self.last_timestamp is not None:
                    dt = (self.get_clock().now().nanoseconds / 1e9) - self.last_timestamp
                    if dt > 0:
                        velocity = (current_pos - self.last_position) / dt
                    else:
                        velocity = np.zeros(3)
                else:
                    velocity = np.zeros(3)

            # 使用意图检测器计算意图因子
            intent_factors = self.intent_detector.detect_intent(
                current_pos=current_pos,
                target_pos=target_pos,
                velocity=velocity,
                smooth=True
            )

            # 根据配置的意图因子开关，选择性地应用
            alpha = 1.0
            if self.intent_factors['distance']:
                alpha *= intent_factors.alpha_geo
            if self.intent_factors['velocity']:
                alpha *= intent_factors.alpha_vel
            if self.intent_factors['alignment']:
                alpha *= intent_factors.alpha_dir

            # 更新状态用于下次计算
            self.last_position = current_pos.copy()
            self.last_timestamp = self.get_clock().now().nanoseconds / 1e9

            return float(np.clip(alpha, 0.0, 1.0))

        except Exception as e:
            self.get_logger().warn(f'Error computing intent factor: {e}')
            return 0.5  # 返回中性值

    def publish_filtered_state(self, filtered_state: np.ndarray):
        """发布滤波后的状态"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'vist_filtered'
        msg.position = filtered_state.tolist()

        self.filtered_pub.publish(msg)

    def publish_performance_metrics(self, filtered_state: np.ndarray):
        """发布性能指标"""
        try:
            current_time = self.get_clock().now().nanoseconds / 1e9

            # 计算速度（数值微分）
            if self.last_position is not None and self.last_timestamp is not None:
                dt = current_time - self.last_timestamp
                if dt > 0:
                    velocity = (filtered_state - self.last_position) / dt

                    # 计算加速度
                    if self.last_velocity is not None:
                        acceleration = (velocity - self.last_velocity) / dt

                        # 计算Jerk（加加速度）
                        jerk_norm = np.linalg.norm(acceleration) / dt if dt > 0 else 0.0

                        # 计算其他指标
                        velocity_norm = np.linalg.norm(velocity)
                        acceleration_norm = np.linalg.norm(acceleration)

                        # 发布性能指标
                        # 格式: [velocity_norm, acceleration_norm, jerk_norm, max_joint_velocity, max_joint_acceleration]
                        msg = Float64MultiArray()
                        msg.data = [
                            float(velocity_norm),
                            float(acceleration_norm),
                            float(jerk_norm),
                            float(np.max(np.abs(velocity))),
                            float(np.max(np.abs(acceleration)))
                        ]
                        self.performance_pub.publish(msg)

                        # 更新状态
                        self.last_velocity = velocity.copy()
                    else:
                        self.last_velocity = velocity.copy()

                    self.last_position = filtered_state.copy()
                    self.last_timestamp = current_time
            else:
                # 初始化
                self.last_position = filtered_state.copy()
                self.last_timestamp = current_time
                self.last_velocity = np.zeros_like(filtered_state)

        except Exception as e:
            self.get_logger().warn(f'Error computing performance metrics: {e}')

    def publish_intent_factors(self, intent_factor: float):
        """发布意图因子（用于可视化）"""
        msg = Float64MultiArray()
        msg.data = [intent_factor]
        self.intent_pub.publish(msg)

    def print_config(self):
        """打印配置信息"""
        self.get_logger().info('========== VIST Filter Node Config ==========')
        self.get_logger().info(f'Arm side: {self.arm_side}')
        self.get_logger().info(f'Filter type: {self.filter_type}')
        self.get_logger().info(f'Output frequency: {self.output_freq_hz} Hz')
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
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
