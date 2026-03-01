#!/usr/bin/env python3
"""
高频重采样节点测试脚本
用于验证节点是否正常工作
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from lbot_arm_interfaces.msg import FollowJoint
import math
import time

class ResamplerTester(Node):
    def __init__(self):
        super().__init__('resampler_tester')

        # 发布模拟视觉数据 (20Hz)
        self.vision_pub = self.create_publisher(
            JointState, '/left_arm_joint_control', 10)

        # 订阅重采样后的数据 (200Hz)
        self.resampled_sub = self.create_subscription(
            FollowJoint, '/robot1/left_arm/joint_follow',
            self.resampled_callback, 10)

        # 定时器: 20Hz 发布
        self.timer = self.create_timer(0.05, self.publish_vision_data)

        self.t = 0.0
        self.resampled_count = 0
        self.last_print_time = time.time()

        self.get_logger().info('Resampler Tester started')
        self.get_logger().info('Publishing vision data at 20Hz...')
        self.get_logger().info('Expecting resampled data at ~200Hz...')

    def publish_vision_data(self):
        """发布模拟的正弦波关节数据"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        # 生成7个关节的正弦波 (角度制)
        msg.position = [
            30.0 * math.sin(self.t),           # Joint 0
            20.0 * math.sin(self.t + 0.5),     # Joint 1
            25.0 * math.sin(self.t + 1.0),     # Joint 2
            15.0 * math.sin(self.t + 1.5),     # Joint 3
            20.0 * math.sin(self.t + 2.0),     # Joint 4
            10.0 * math.sin(self.t + 2.5),     # Joint 5
            15.0 * math.sin(self.t + 3.0),     # Joint 6
        ]

        self.vision_pub.publish(msg)
        self.t += 0.1  # 增加时间

    def resampled_callback(self, msg):
        """接收重采样后的数据"""
        self.resampled_count += 1

        # 每秒打印一次统计
        now = time.time()
        if now - self.last_print_time >= 1.0:
            freq = self.resampled_count / (now - self.last_print_time)
            self.get_logger().info(
                f'Resampled frequency: {freq:.1f} Hz | '
                f'Joints: [{msg.joints[0]:.3f}, {msg.joints[1]:.3f}, ...] | '
                f'Follow: {msg.follow}'
            )
            self.resampled_count = 0
            self.last_print_time = now

def main(args=None):
    rclpy.init(args=args)
    node = ResamplerTester()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
