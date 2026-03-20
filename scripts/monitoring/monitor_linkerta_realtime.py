#!/usr/bin/env python3
"""
LinkerTA 实时数据监控工具
显示关节角度、频率、数据质量等信息

使用方法:
    python3 monitor_linkerta_realtime.py [话题名称]

示例:
    python3 monitor_linkerta_realtime.py /left_arm_joint_control
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
import sys
import time
from collections import deque
from datetime import datetime

class LinkerTAMonitor(Node):
    def __init__(self, topic_name):
        super().__init__('linkerta_monitor')

        self.topic_name = topic_name
        self.get_logger().info('=' * 80)
        self.get_logger().info(f'LinkerTA 实时数据监控')
        self.get_logger().info(f'话题: {topic_name}')
        self.get_logger().info('=' * 80)

        # 订阅话题
        self.subscription = self.create_subscription(
            JointState,
            topic_name,
            self.data_callback,
            10
        )

        # 统计数据
        self.message_count = 0
        self.start_time = time.time()
        self.last_message_time = None
        self.timestamps = deque(maxlen=100)  # 用于计算频率

        # 关节数据历史
        self.joint_history = deque(maxlen=100)
        self.last_position = None

        # 数据质量监控
        self.min_values = None
        self.max_values = None
        self.zero_count = 0
        self.large_jump_count = 0

        # 定时打印统计
        self.timer = self.create_timer(1.0, self.print_statistics)

        self.get_logger().info('等待数据...')
        self.get_logger().info('按 Ctrl+C 停止监控')
        self.get_logger().info('')

    def data_callback(self, msg):
        """接收数据回调"""
        current_time = time.time()
        self.message_count += 1
        self.timestamps.append(current_time)

        # 提取关节位置
        if len(msg.position) > 0:
            positions = np.array(msg.position)
            self.joint_history.append(positions)

            # 更新最小最大值
            if self.min_values is None:
                self.min_values = positions.copy()
                self.max_values = positions.copy()
            else:
                self.min_values = np.minimum(self.min_values, positions)
                self.max_values = np.maximum(self.max_values, positions)

            # 检测异常
            if np.all(positions == 0):
                self.zero_count += 1

            # 检测大跳变
            if self.last_position is not None:
                delta = np.abs(positions - self.last_position)
                if np.any(delta > 30):  # 假设角度单位，30度为大跳变
                    self.large_jump_count += 1
                    self.get_logger().warn(f'检测到大跳变: {delta[delta > 30]}')

            self.last_position = positions.copy()

        self.last_message_time = current_time

    def calculate_frequency(self):
        """计算接收频率"""
        if len(self.timestamps) < 2:
            return 0.0

        time_span = self.timestamps[-1] - self.timestamps[0]
        if time_span <= 0:
            return 0.0

        return (len(self.timestamps) - 1) / time_span

    def print_statistics(self):
        """打印统计信息"""
        if self.message_count == 0:
            self.get_logger().warn('⚠️  未接收到任何数据！')
            self.get_logger().info('   请检查:')
            self.get_logger().info('   1. LinkerTA驱动是否启动')
            self.get_logger().info('   2. 话题名称是否正确')
            self.get_logger().info(f'   3. 运行: ros2 topic list | grep arm')
            return

        # 计算运行时间
        elapsed_time = time.time() - self.start_time

        # 计算频率
        freq = self.calculate_frequency()

        # 计算平均频率
        avg_freq = self.message_count / elapsed_time if elapsed_time > 0 else 0

        # 清屏（可选）
        # print('\033[2J\033[H', end='')

        print('\n' + '=' * 80)
        print(f'LinkerTA 数据监控 - {datetime.now().strftime("%H:%M:%S")}')
        print('=' * 80)

        print(f'\n📊 基本统计:')
        print(f'  运行时间: {elapsed_time:.1f}s')
        print(f'  消息总数: {self.message_count}')
        print(f'  当前频率: {freq:.2f} Hz')
        print(f'  平均频率: {avg_freq:.2f} Hz')

        if self.last_message_time:
            delay = time.time() - self.last_message_time
            print(f'  最后接收: {delay:.3f}s 前')

        # 关节数据
        if len(self.joint_history) > 0:
            current_pos = self.joint_history[-1]
            print(f'\n🎯 当前关节角度 (共{len(current_pos)}个关节):')

            # 判断单位（角度 vs 弧度）
            max_val = np.max(np.abs(current_pos))
            unit = '°' if max_val > 10 else 'rad'

            for i, pos in enumerate(current_pos):
                print(f'  关节{i+1}: {pos:8.3f} {unit}', end='')
                if (i + 1) % 3 == 0:
                    print()
            print()

            # 显示范围
            if self.min_values is not None:
                print(f'\n📈 关节运动范围:')
                for i in range(len(current_pos)):
                    range_val = self.max_values[i] - self.min_values[i]
                    print(f'  关节{i+1}: [{self.min_values[i]:7.2f}, {self.max_values[i]:7.2f}] (范围: {range_val:.2f})')

        # 数据质量
        print(f'\n🔍 数据质量:')
        zero_rate = (self.zero_count / self.message_count * 100) if self.message_count > 0 else 0
        jump_rate = (self.large_jump_count / self.message_count * 100) if self.message_count > 0 else 0

        print(f'  全零数据: {self.zero_count} ({zero_rate:.1f}%)', end='')
        if zero_rate > 10:
            print(' ⚠️  异常！')
        else:
            print(' ✓')

        print(f'  大跳变: {self.large_jump_count} ({jump_rate:.1f}%)', end='')
        if jump_rate > 5:
            print(' ⚠️  异常！')
        else:
            print(' ✓')

        # 频率健康检查
        print(f'\n💚 健康状态:')
        if freq < 10:
            print(f'  频率: ⚠️  过低 ({freq:.1f} Hz < 10 Hz)')
        elif freq < 50:
            print(f'  频率: ⚠️  偏低 ({freq:.1f} Hz < 50 Hz)')
        else:
            print(f'  频率: ✓ 正常 ({freq:.1f} Hz)')

        if delay > 1.0:
            print(f'  延迟: ⚠️  数据停止 ({delay:.1f}s)')
        elif delay > 0.1:
            print(f'  延迟: ⚠️  偏高 ({delay*1000:.0f}ms)')
        else:
            print(f'  延迟: ✓ 正常 ({delay*1000:.0f}ms)')

        print('=' * 80)

def main(args=None):
    # 获取话题名称
    if len(sys.argv) > 1:
        topic_name = sys.argv[1]
    else:
        topic_name = '/left_arm_joint_control'
        print(f'未指定话题，使用默认: {topic_name}')
        print(f'用法: python3 {sys.argv[0]} <话题名称>')
        print()

    rclpy.init(args=args)

    try:
        monitor = LinkerTAMonitor(topic_name)
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        print('\n\n监控停止')
    finally:
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()