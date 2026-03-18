#!/usr/bin/env python3
"""
双臂可视化调试工具
输出详细的调试信息，帮助诊断问题
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np

class VisualizationDebugger(Node):
    def __init__(self):
        super().__init__('visualization_debugger')

        self.get_logger().info('=' * 60)
        self.get_logger().info('双臂可视化调试工具')
        self.get_logger().info('=' * 60)

        # 订阅左臂
        self.left_sub = self.create_subscription(
            JointState,
            '/filtered_left_joint_control',
            self.left_callback,
            10
        )

        # 订阅右臂
        self.right_sub = self.create_subscription(
            JointState,
            '/filtered_right_joint_control',
            self.right_callback,
            10
        )

        self.left_count = 0
        self.right_count = 0

        self.get_logger().info('等待数据...')
        self.get_logger().info('订阅话题:')
        self.get_logger().info('  - /filtered_left_joint_control')
        self.get_logger().info('  - /filtered_right_joint_control')
        self.get_logger().info('=' * 60)

    def left_callback(self, msg):
        self.left_count += 1

        if self.left_count == 1:
            self.get_logger().info('✓ 收到第一条左臂数据！')
            self.get_logger().info(f'  关节数量: {len(msg.position)}')
            self.get_logger().info(f'  关节角度: {msg.position}')
            self.get_logger().info(f'  最大值: {np.max(np.abs(msg.position)):.2f}')

            # 判断单位
            max_val = np.max(np.abs(msg.position))
            if max_val > 10:
                self.get_logger().info(f'  单位: 角度 (degree)')
            else:
                self.get_logger().info(f'  单位: 弧度 (radian)')

        if self.left_count % 80 == 0:
            self.get_logger().info(f'左臂: 已接收 {self.left_count} 条消息')

    def right_callback(self, msg):
        self.right_count += 1

        if self.right_count == 1:
            self.get_logger().info('✓ 收到第一条右臂数据！')
            self.get_logger().info(f'  关节数量: {len(msg.position)}')
            self.get_logger().info(f'  关节角度: {msg.position}')
            self.get_logger().info(f'  最大值: {np.max(np.abs(msg.position)):.2f}')

            # 判断单位
            max_val = np.max(np.abs(msg.position))
            if max_val > 10:
                self.get_logger().info(f'  单位: 角度 (degree)')
            else:
                self.get_logger().info(f'  单位: 弧度 (radian)')

        if self.right_count % 80 == 0:
            self.get_logger().info(f'右臂: 已接收 {self.right_count} 条消息')

def main():
    rclpy.init()
    debugger = VisualizationDebugger()

    try:
        rclpy.spin(debugger)
    except KeyboardInterrupt:
        print('\n调试器停止')
    finally:
        debugger.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
