#!/usr/bin/env python3
"""
统一滤波节点 - 支持消融实验和对比试验
Unified Filter Node for Ablation Studies and Comparison Experiments

功能:
1. 统一的滤波器接口，避免代码重复
2. 支持多种滤波算法切换（none/ema/one_euro/vist_kalman）
3. 单一数据源输入，单一滤波输出
4. 避免话题碰撞问题
5. 支持性能监控和数据记录

作者: VIST Team
日期: 2026-02-25
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
import numpy as np
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.control.filters.filter_factory import FilterFactory


class UnifiedFilterNode(Node):
    """
    统一滤波ROS2节点

    设计原则:
    - 单一职责: 只负责滤波，不做融合
    - 统一接口: 所有滤波器通过FilterFactory创建
    - 避免重复: 消除simple_filter_node和vist_filter_node的重复逻辑
    """

    def __init__(self):
        super().__init__('unified_filter_node')

        # 声明参数
        self.setup_parameters()

        # 加载配置
        self.load_config()

        # 创建滤波器
        self.create_filter()

        # 创建订阅器和发布器
        self.create_subscribers()
        self.create_publishers()

        # 性能监控
        self.last_update_time = None
        self.update_count = 0
        self.total_latency = 0.0

        self.get_logger().info('=' * 80)
        self.get_logger().info('Unified Filter Node Initialized')
        self.print_config()
        self.get_logger().info('=' * 80)

    def setup_parameters(self):
        """声明ROS2参数"""
        # 话题配置
        self.declare_parameter('input_topic', '/right_arm_joint_control')
        self.declare_parameter('output_topic', '/filtered_right_joint_control')

        # 滤波器选择
        self.declare_parameter('filter_type', 'one_euro')

        # 通用参数
        self.declare_parameter('joint_dim', 7)

        # EMA参数
        self.declare_parameter('ema_alpha', 0.3)

        # One-Euro参数
        self.declare_parameter('one_euro_min_cutoff', 1.0)
        self.declare_parameter('one_euro_beta', 0.007)
        self.declare_parameter('one_euro_d_cutoff', 1.0)

        # 移动平均参数
        self.declare_parameter('ma_window_size', 5)

        # 性能监控
        self.declare_parameter('enable_performance_monitoring', True)
        self.declare_parameter('performance_topic', '/filter_performance')

    def load_config(self):
        """加载配置参数"""
        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.filter_type = self.get_parameter('filter_type').value
        self.joint_dim = self.get_parameter('joint_dim').value

        # 滤波器参数
        self.ema_alpha = self.get_parameter('ema_alpha').value
        self.one_euro_min_cutoff = self.get_parameter('one_euro_min_cutoff').value
        self.one_euro_beta = self.get_parameter('one_euro_beta').value
        self.one_euro_d_cutoff = self.get_parameter('one_euro_d_cutoff').value
        self.ma_window_size = self.get_parameter('ma_window_size').value

        # 性能监控
        self.enable_performance = self.get_parameter('enable_performance_monitoring').value
        self.performance_topic = self.get_parameter('performance_topic').value

    def create_filter(self):
        """创建滤波器实例"""
        try:
            # 准备滤波器参数
            filter_kwargs = {}

            if self.filter_type == 'ema':
                filter_kwargs['alpha'] = self.ema_alpha
            elif self.filter_type == 'one_euro':
                filter_kwargs['min_cutoff'] = self.one_euro_min_cutoff
                filter_kwargs['beta'] = self.one_euro_beta
                filter_kwargs['d_cutoff'] = self.one_euro_d_cutoff
            elif self.filter_type == 'moving_average':
                filter_kwargs['window_size'] = self.ma_window_size

            # 使用工厂创建滤波器
            self.filter = FilterFactory.create_filter(
                self.filter_type,
                self.joint_dim,
                **filter_kwargs
            )

            if self.filter is None:
                raise ValueError(f"滤波器类型 '{self.filter_type}' 需要特殊处理，"
                               "请使用vist_filter_node")

            self.get_logger().info(f'✓ 滤波器创建成功: {self.filter.get_name()}')

        except Exception as e:
            self.get_logger().error(f'✗ 滤波器创建失败: {e}')
            raise

    def create_subscribers(self):
        """创建订阅器"""
        self.sub = self.create_subscription(
            JointState,
            self.input_topic,
            self.filter_callback,
            10
        )
        self.get_logger().info(f'✓ 订阅话题: {self.input_topic}')

    def create_publishers(self):
        """创建发布器"""
        self.pub = self.create_publisher(
            JointState,
            self.output_topic,
            10
        )
        self.get_logger().info(f'✓ 发布话题: {self.output_topic}')

        if self.enable_performance:
            self.perf_pub = self.create_publisher(
                Float64MultiArray,
                self.performance_topic,
                10
            )
            self.get_logger().info(f'✓ 性能监控话题: {self.performance_topic}')

    def filter_callback(self, msg: JointState):
        """滤波回调函数"""
        if not msg.position or len(msg.position) == 0:
            return

        try:
            # 记录开始时间
            start_time = self.get_clock().now()

            # 获取关节位置
            joints = np.array(msg.position[:self.joint_dim])

            # 计算时间步长
            dt = None
            if self.last_update_time is not None:
                dt = (start_time - self.last_update_time).nanoseconds / 1e9
            self.last_update_time = start_time

            # 应用滤波
            filtered_joints = self.filter.update(joints, dt=dt)

            # 发布滤波后的数据
            output_msg = JointState()
            output_msg.header = msg.header
            output_msg.header.stamp = self.get_clock().now().to_msg()
            output_msg.name = msg.name[:self.joint_dim] if msg.name else []
            output_msg.position = filtered_joints.tolist()

            # 保留速度和力矩信息（如果有）
            if msg.velocity and len(msg.velocity) >= self.joint_dim:
                output_msg.velocity = msg.velocity[:self.joint_dim]
            if msg.effort and len(msg.effort) >= self.joint_dim:
                output_msg.effort = msg.effort[:self.joint_dim]

            self.pub.publish(output_msg)

            # 性能监控
            if self.enable_performance:
                end_time = self.get_clock().now()
                latency = (end_time - start_time).nanoseconds / 1e6  # ms
                self.publish_performance(latency, filtered_joints)

            self.update_count += 1

        except Exception as e:
            self.get_logger().error(f'滤波处理错误: {e}')

    def publish_performance(self, latency_ms, filtered_state):
        """发布性能指标"""
        try:
            velocity = self.filter.get_velocity()

            # 性能指标: [latency_ms, max_velocity, mean_velocity, update_count]
            perf_msg = Float64MultiArray()
            perf_msg.data = [
                float(latency_ms),
                float(np.max(np.abs(velocity))),
                float(np.mean(np.abs(velocity))),
                float(self.update_count)
            ]
            self.perf_pub.publish(perf_msg)

        except Exception as e:
            self.get_logger().warn(f'性能监控错误: {e}')

    def print_config(self):
        """打印配置信息"""
        self.get_logger().info(f'滤波器类型: {self.filter_type}')
        self.get_logger().info(f'  描述: {FilterFactory.get_filter_description(self.filter_type)}')
        self.get_logger().info(f'输入话题: {self.input_topic}')
        self.get_logger().info(f'输出话题: {self.output_topic}')
        self.get_logger().info(f'关节维度: {self.joint_dim}')

        if self.filter_type == 'ema':
            self.get_logger().info(f'EMA alpha: {self.ema_alpha}')
        elif self.filter_type == 'one_euro':
            self.get_logger().info(f'One-Euro min_cutoff: {self.one_euro_min_cutoff}')
            self.get_logger().info(f'One-Euro beta: {self.one_euro_beta}')
        elif self.filter_type == 'moving_average':
            self.get_logger().info(f'窗口大小: {self.ma_window_size}')

        self.get_logger().info(f'性能监控: {"启用" if self.enable_performance else "禁用"}')


def main(args=None):
    rclpy.init(args=args)

    try:
        node = UnifiedFilterNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\n⚠️  收到中断信号')
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()