#!/usr/bin/env python3
"""
数据流完整诊断工具
对比滤波节点发布的数据和可视化节点接收的数据
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
from collections import deque

class DataFlowDiagnostic(Node):
    def __init__(self):
        super().__init__('data_flow_diagnostic')

        # 存储最近的数据
        self.left_filtered_data = deque(maxlen=5)
        self.right_filtered_data = deque(maxlen=5)

        # 订阅滤波后的话题（这是滤波节点发布的）
        self.left_filtered_sub = self.create_subscription(
            JointState,
            '/filtered_left_joint_control',
            self.left_filtered_callback,
            10
        )

        self.right_filtered_sub = self.create_subscription(
            JointState,
            '/filtered_right_joint_control',
            self.right_filtered_callback,
            10
        )

        self.sample_count = 0

        print('=' * 80)
        print('数据流诊断工具')
        print('=' * 80)
        print('订阅话题:')
        print('  - /filtered_left_joint_control')
        print('  - /filtered_right_joint_control')
        print('')
        print('每5秒打印一次数据样本')
        print('=' * 80)

        # 定时打印
        self.timer = self.create_timer(5.0, self.print_samples)

    def left_filtered_callback(self, msg):
        """接收左臂滤波后的数据"""
        self.left_filtered_data.append(np.array(msg.position[:7]))

    def right_filtered_callback(self, msg):
        """接收右臂滤波后的数据"""
        self.right_filtered_data.append(np.array(msg.position[:7]))

    def print_samples(self):
        """打印数据样本"""
        self.sample_count += 1

        print(f'\n{"=" * 80}')
        print(f'样本 #{self.sample_count}')
        print(f'{"=" * 80}')

        if len(self.left_filtered_data) > 0:
            left_latest = self.left_filtered_data[-1]
            print(f'\n【左臂】滤波后的数据:')
            print(f'  关节0: {left_latest[0]:8.3f}')
            print(f'  关节1: {left_latest[1]:8.3f}')
            print(f'  关节2: {left_latest[2]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节3: {left_latest[3]:8.3f}')
            print(f'  关节4: {left_latest[4]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节5: {left_latest[5]:8.3f}')
            print(f'  关节6: {left_latest[6]:8.3f}')
        else:
            print('\n【左臂】无数据')

        if len(self.right_filtered_data) > 0:
            right_latest = self.right_filtered_data[-1]
            print(f'\n【右臂】滤波后的数据:')
            print(f'  关节0: {right_latest[0]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节1: {right_latest[1]:8.3f}')
            print(f'  关节2: {right_latest[2]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节3: {right_latest[3]:8.3f}')
            print(f'  关节4: {right_latest[4]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节5: {right_latest[5]:8.3f} ← 应该反转（配置=-1）')
            print(f'  关节6: {right_latest[6]:8.3f}')
        else:
            print('\n【右臂】无数据')

        print(f'\n提示: 移动遥操臂，观察数值变化')
        print(f'     如果标记"应该反转"的关节数值符号正确，说明方向修正生效')

def main():
    rclpy.init()
    diagnostic = DataFlowDiagnostic()

    print('\n按 Ctrl+C 停止\n')

    try:
        rclpy.spin(diagnostic)
    except KeyboardInterrupt:
        print('\n\n诊断完成')
    finally:
        diagnostic.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
