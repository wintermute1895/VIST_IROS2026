#!/usr/bin/env python3
"""
手动测试可视化 - 发布测试数据
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
import time

class TestPublisher(Node):
    def __init__(self):
        super().__init__('test_publisher')

        # 创建发布器
        self.left_pub = self.create_publisher(
            JointState,
            '/filtered_left_joint_control',
            10
        )

        self.right_pub = self.create_publisher(
            JointState,
            '/filtered_right_joint_control',
            10
        )

        # 定时器
        self.timer = self.create_timer(0.0125, self.timer_callback)  # 80Hz

        self.count = 0

        self.get_logger().info('测试发布器已启动')
        self.get_logger().info('发布测试数据到:')
        self.get_logger().info('  - /filtered_left_joint_control')
        self.get_logger().info('  - /filtered_right_joint_control')

    def timer_callback(self):
        self.count += 1

        # 生成测试数据（正弦波）
        t = self.count * 0.0125
        amplitude = 30.0  # 度

        left_msg = JointState()
        left_msg.header.stamp = self.get_clock().now().to_msg()
        left_msg.position = [
            amplitude * np.sin(t),  # 关节1
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0
        ]

        right_msg = JointState()
        right_msg.header.stamp = self.get_clock().now().to_msg()
        right_msg.position = [
            0.0,
            amplitude * np.sin(t + np.pi),  # 关节2，相位相反
            0.0,
            0.0,
            0.0,
            0.0,
            0.0
        ]

        self.left_pub.publish(left_msg)
        self.right_pub.publish(right_msg)

        if self.count % 80 == 0:
            self.get_logger().info(f'已发布 {self.count} 条消息')

def main():
    rclpy.init()
    publisher = TestPublisher()

    try:
        rclpy.spin(publisher)
    except KeyboardInterrupt:
        print('\n测试发布器停止')
    finally:
        publisher.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()