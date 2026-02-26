#!/usr/bin/env python3
"""
诊断数据手套和灵巧手之间的数据流
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

class HandDiagnostic(Node):
    def __init__(self):
        super().__init__('hand_diagnostic')

        self.glove_sub = self.create_subscription(
            JointState,
            '/cb_left_hand_control_cmd',
            self.glove_callback,
            10
        )

        self.hand_sub = self.create_subscription(
            JointState,
            '/cb_left_hand_state',
            self.hand_callback,
            10
        )

        self.glove_count = 0
        self.hand_count = 0
        self.last_glove_pos = None
        self.last_hand_pos = None

        self.timer = self.create_timer(2.0, self.print_status)

    def glove_callback(self, msg):
        self.glove_count += 1
        if self.last_glove_pos is None:
            self.last_glove_pos = msg.position
            self.get_logger().info(f'首次接收数据手套数据:')
            self.get_logger().info(f'  关节数量: {len(msg.position)}')
            self.get_logger().info(f'  关节名称: {msg.name}')
            self.get_logger().info(f'  位置值: {[f"{p:.2f}" for p in msg.position[:5]]}...')
        else:
            # 计算变化量
            changes = [abs(new - old) for new, old in zip(msg.position, self.last_glove_pos)]
            max_change = max(changes) if changes else 0
            if max_change > 1.0:
                self.get_logger().info(f'数据手套位置变化: 最大变化={max_change:.2f}')
            self.last_glove_pos = msg.position

    def hand_callback(self, msg):
        self.hand_count += 1
        if self.last_hand_pos is None:
            self.last_hand_pos = msg.position
            self.get_logger().info(f'首次接收灵巧手状态:')
            self.get_logger().info(f'  关节数量: {len(msg.position)}')
            self.get_logger().info(f'  关节名称: {msg.name}')
            self.get_logger().info(f'  位置值: {[f"{p:.2f}" for p in msg.position[:5]]}...')
        else:
            # 检查是否有变化
            changes = [abs(new - old) for new, old in zip(msg.position, self.last_hand_pos)]
            max_change = max(changes) if changes else 0
            if max_change > 0.1:
                self.get_logger().info(f'灵巧手位置变化: 最大变化={max_change:.2f}')
            self.last_hand_pos = msg.position

    def print_status(self):
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'数据手套消息数: {self.glove_count}')
        self.get_logger().info(f'灵巧手消息数: {self.hand_count}')
        if self.last_glove_pos:
            self.get_logger().info(f'数据手套当前位置: {[f"{p:.2f}" for p in self.last_glove_pos[:5]]}...')
        if self.last_hand_pos:
            self.get_logger().info(f'灵巧手当前位置: {[f"{p:.2f}" for p in self.last_hand_pos[:5]]}...')
        self.get_logger().info('=' * 60)

def main():
    rclpy.init()
    node = HandDiagnostic()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()