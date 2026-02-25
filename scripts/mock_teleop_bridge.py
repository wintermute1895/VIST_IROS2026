#!/usr/bin/env python3
"""
模拟teleop_bridge节点
用于测试joint_follow频率，不需要连接真机
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from lbot_arm_interfaces.msg import FollowJoint


class MockTeleopBridge(Node):
    def __init__(self):
        super().__init__('mock_teleop_bridge')

        # 订阅外骨骼数据
        self.sub = self.create_subscription(
            JointState,
            '/right_arm_joint_control',
            self.exo_callback,
            10
        )

        # 发布joint_follow命令（模拟发送到真机）
        self.pub = self.create_publisher(
            FollowJoint,
            '/robot1/right_arm/joint_follow',
            10
        )

        self.get_logger().info('模拟teleop_bridge已启动')
        self.get_logger().info('订阅: /right_arm_joint_control')
        self.get_logger().info('发布: /robot1/right_arm/joint_follow')

    def exo_callback(self, msg):
        """接收外骨骼数据，转换并发布"""
        # 转换为FollowJoint消息
        follow_msg = FollowJoint()
        follow_msg.joints = list(msg.position)
        follow_msg.follow = True

        # 发布
        self.pub.publish(follow_msg)


def main():
    rclpy.init()

    try:
        node = MockTeleopBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\n停止')
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()