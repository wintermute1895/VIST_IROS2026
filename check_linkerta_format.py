#!/usr/bin/env python3
"""
检查LinkerTA数据格式
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np

class DataFormatChecker(Node):
    def __init__(self):
        super().__init__('data_format_checker')

        self.subscription = self.create_subscription(
            JointState,
            '/left_arm_joint_control',
            self.callback,
            10
        )

        self.count = 0
        self.get_logger().info('等待LinkerTA数据...')

    def callback(self, msg):
        self.count += 1

        if self.count == 1:
            self.get_logger().info('=' * 60)
            self.get_logger().info('LinkerTA数据格式分析')
            self.get_logger().info('=' * 60)
            self.get_logger().info(f'关节数量: {len(msg.position)}')
            self.get_logger().info(f'关节名称: {msg.name}')
            self.get_logger().info('')
            self.get_logger().info('关节角度:')
            for i, (name, pos) in enumerate(zip(msg.name, msg.position)):
                self.get_logger().info(f'  [{i}] {name}: {pos:.3f}')
            self.get_logger().info('=' * 60)
            self.get_logger().info('')
            self.get_logger().info('请移动遥操臂的第1个关节（肩部俯仰）')
            self.get_logger().info('观察哪个索引的值在变化...')

        if self.count > 1 and self.count % 20 == 0:
            self.get_logger().info('')
            self.get_logger().info(f'当前关节角度 (样本 {self.count}):')
            for i, pos in enumerate(msg.position):
                self.get_logger().info(f'  [{i}]: {pos:7.3f}')

def main():
    rclpy.init()
    checker = DataFormatChecker()

    try:
        rclpy.spin(checker)
    except KeyboardInterrupt:
        print('\n检查器停止')
    finally:
        checker.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()