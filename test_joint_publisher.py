#!/usr/bin/env python3
"""
测试关节数据发布器
用于测试滤波节点，发布 7 个关节的测试数据
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np


class TestJointPublisher(Node):
    def __init__(self):
        super().__init__('test_joint_publisher')

        # 创建发布器
        self.publisher = self.create_publisher(
            JointState,
            '/left_arm_joint_control',
            10
        )

        # 创建定时器（50Hz）
        self.timer = self.create_timer(0.02, self.timer_callback)

        # 初始化关节角度（7个关节）
        self.joint_angles = np.array([0.0, -2.7, -0.7, -6.5, 2.7, -0.7, -0.5])
        self.time = 0.0

        self.get_logger().info('Test Joint Publisher started')
        self.get_logger().info('Publishing to: /left_arm_joint_control')
        self.get_logger().info('Frequency: 50 Hz')

    def timer_callback(self):
        """发布测试关节数据"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.name = [f'joint_{i+1}' for i in range(7)]

        # 生成缓慢变化的关节角度（正弦波）
        self.time += 0.02
        variation = 0.1 * np.sin(self.time)
        msg.position = (self.joint_angles + variation).tolist()

        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TestJointPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()