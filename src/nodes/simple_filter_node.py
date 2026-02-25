#!/usr/bin/env python3
"""
[DEPRECATED] 简化的滤波节点 - 只用于One-Euro和EMA滤波

⚠️  警告: 此节点已废弃，请使用 unified_filter_node.py
⚠️  原因: 代码重复，接口不统一，容易导致话题碰撞

推荐替代:
  python3 unified_filter_node.py --ros-args \\
    -p filter_type:=one_euro \\
    -p input_topic:=/right_arm_joint_control \\
    -p output_topic:=/filtered_right_joint_control

此文件保留仅用于向后兼容，将在未来版本中移除。

原始用法:
  python3 simple_filter_node.py --ros-args \\
    -p filter_type:=one_euro \\
    -p input_topic:=/right_arm_joint_control \\
    -p output_topic:=/filtered_right_joint_control
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.one_euro_filter import OneEuroFilter


class SimpleFilterNode(Node):
    """简化的滤波ROS2节点"""

    def __init__(self):
        super().__init__('simple_filter_node')

        # 发出废弃警告
        self.get_logger().warn('=' * 80)
        self.get_logger().warn('⚠️  警告: simple_filter_node 已废弃!')
        self.get_logger().warn('⚠️  请使用 unified_filter_node.py 替代')
        self.get_logger().warn('⚠️  原因: 避免代码重复和话题碰撞问题')
        self.get_logger().warn('=' * 80)

        # 声明参数
        self.declare_parameter('filter_type', 'one_euro')  # one_euro, ema, passthrough
        self.declare_parameter('input_topic', '/right_arm_joint_control')
        self.declare_parameter('output_topic', '/filtered_right_joint_control')
        self.declare_parameter('output_freq_hz', 100.0)

        # One-Euro参数
        self.declare_parameter('one_euro_min_cutoff', 1.0)
        self.declare_parameter('one_euro_beta', 0.007)

        # EMA参数
        self.declare_parameter('ema_alpha', 0.3)

        # 加载参数
        self.filter_type = self.get_parameter('filter_type').value
        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.output_freq_hz = self.get_parameter('output_freq_hz').value

        self.one_euro_min_cutoff = self.get_parameter('one_euro_min_cutoff').value
        self.one_euro_beta = self.get_parameter('one_euro_beta').value
        self.ema_alpha = self.get_parameter('ema_alpha').value

        # 初始化滤波器
        self.filters = None
        self.last_data = None
        self.last_timestamp = None

        # 创建订阅器和发布器
        self.sub = self.create_subscription(
            JointState,
            self.input_topic,
            self.callback,
            10
        )

        self.pub = self.create_publisher(
            JointState,
            self.output_topic,
            10
        )

        self.get_logger().info('=' * 80)
        self.get_logger().info(f'Simple Filter Node initialized')
        self.get_logger().info(f'  Filter type: {self.filter_type}')
        self.get_logger().info(f'  Input topic: {self.input_topic}')
        self.get_logger().info(f'  Output topic: {self.output_topic}')
        self.get_logger().info(f'  Output freq: {self.output_freq_hz} Hz')

        if self.filter_type == 'one_euro':
            self.get_logger().info(f'  One-Euro min_cutoff: {self.one_euro_min_cutoff}')
            self.get_logger().info(f'  One-Euro beta: {self.one_euro_beta}')
        elif self.filter_type == 'ema':
            self.get_logger().info(f'  EMA alpha: {self.ema_alpha}')

        self.get_logger().info('=' * 80)

    def callback(self, msg):
        """处理输入数据"""
        if not msg.position or len(msg.position) == 0:
            return

        # 转换为numpy数组
        joints = np.array(msg.position)
        n_joints = len(joints)

        # 初始化滤波器（首次接收数据时）
        if self.filters is None:
            if self.filter_type == 'one_euro':
                self.filters = [
                    OneEuroFilter(
                        min_cutoff=self.one_euro_min_cutoff,
                        beta=self.one_euro_beta
                    ) for _ in range(n_joints)
                ]
                self.get_logger().info(f'Initialized {n_joints} One-Euro filters')
            elif self.filter_type == 'ema':
                self.last_data = joints.copy()
                self.get_logger().info(f'Initialized EMA filter for {n_joints} joints')
            elif self.filter_type == 'passthrough':
                self.get_logger().info(f'Passthrough mode (no filtering)')
            else:
                self.get_logger().error(f'Unknown filter type: {self.filter_type}')
                return

        # 应用滤波
        current_time = self.get_clock().now().nanoseconds / 1e9

        if self.filter_type == 'one_euro':
            filtered_joints = np.array([
                self.filters[i](joints[i], current_time)
                for i in range(n_joints)
            ])
        elif self.filter_type == 'ema':
            # 指数移动平均
            filtered_joints = self.ema_alpha * joints + (1 - self.ema_alpha) * self.last_data
            self.last_data = filtered_joints.copy()
        elif self.filter_type == 'passthrough':
            # 直接透传
            filtered_joints = joints
        else:
            return

        # 发布滤波后的数据
        output_msg = JointState()
        output_msg.header = msg.header
        output_msg.header.stamp = self.get_clock().now().to_msg()
        output_msg.name = msg.name
        output_msg.position = filtered_joints.tolist()
        output_msg.velocity = msg.velocity
        output_msg.effort = msg.effort

        self.pub.publish(output_msg)


def main(args=None):
    rclpy.init(args=args)

    try:
        node = SimpleFilterNode()
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