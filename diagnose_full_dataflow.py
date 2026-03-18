#!/usr/bin/env python3
"""
完整的数据流诊断 - 从LinkerTA到可视化
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np

class FullDataFlowDiagnostic(Node):
    def __init__(self):
        super().__init__('full_data_flow_diagnostic')

        # 订阅所有相关话题
        self.left_raw_sub = self.create_subscription(
            JointState, '/left_arm_joint_control',
            lambda msg: self.callback(msg, 'LinkerTA左臂'), 10
        )

        self.right_raw_sub = self.create_subscription(
            JointState, '/right_arm_joint_control',
            lambda msg: self.callback(msg, 'LinkerTA右臂'), 10
        )

        self.left_filtered_sub = self.create_subscription(
            JointState, '/filtered_left_joint_control',
            lambda msg: self.callback(msg, '滤波左臂'), 10
        )

        self.right_filtered_sub = self.create_subscription(
            JointState, '/filtered_right_joint_control',
            lambda msg: self.callback(msg, '滤波右臂'), 10
        )

        self.counts = {}
        self.get_logger().info('=' * 70)
        self.get_logger().info('完整数据流诊断')
        self.get_logger().info('=' * 70)

    def callback(self, msg, source):
        if source not in self.counts:
            self.counts[source] = 0

        self.counts[source] += 1

        if self.counts[source] == 1:
            self.get_logger().info('')
            self.get_logger().info(f'【{source}】首次数据:')
            self.get_logger().info(f'  关节数量: {len(msg.position)}')
            self.get_logger().info(f'  关节名称: {msg.name if msg.name else "无"}')
            self.get_logger().info(f'  关节角度:')
            for i, pos in enumerate(msg.position):
                self.get_logger().info(f'    [{i}]: {pos:8.3f}')

        if self.counts[source] % 80 == 0:
            self.get_logger().info(f'【{source}】已接收 {self.counts[source]} 条消息')

def main():
    rclpy.init()
    diagnostic = FullDataFlowDiagnostic()

    print('')
    print('提示:')
    print('1. 观察每个话题的关节数量')
    print('2. 移动遥操臂，观察数据变化')
    print('3. 按Ctrl+C停止')
    print('')

    try:
        rclpy.spin(diagnostic)
    except KeyboardInterrupt:
        print('\n诊断完成')
    finally:
        diagnostic.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()