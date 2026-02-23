#!/usr/bin/env python3
"""
手套到机器人手的数据桥接节点
将手套的关节角度转换为机器人手的控制指令
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import UInt8MultiArray
import numpy as np


class GloveToRobotBridge(Node):
    def __init__(self):
        super().__init__('glove_to_robot_bridge')

        # 订阅手套数据
        self.glove_sub = self.create_subscription(
            JointState,
            '/cb_left_hand_control_cmd',
            self.glove_callback,
            10
        )

        # 发布到机器人手
        self.robot_pub = self.create_publisher(
            UInt8MultiArray,
            '/robot1/left_hand/set_l10_joint',
            10
        )

        self.get_logger().info('手套到机器人手桥接节点已启动')
        self.get_logger().info('订阅: /cb_left_hand_control_cmd')
        self.get_logger().info('发布: /robot1/left_hand/set_l10_joint')

    def glove_callback(self, msg):
        """
        接收手套数据并转换为机器人手指令

        手套数据: 10个关节角度 (float, 单位可能是度或其他)
        机器人期望: 10个uint8值 (0-255)
        """
        if len(msg.position) < 10:
            self.get_logger().warn(f'手套数据不足10个关节: {len(msg.position)}')
            return

        # 创建机器人手指令
        robot_cmd = UInt8MultiArray()

        # 转换每个关节
        # 假设手套输出范围是0-255，直接映射
        # 如果手套输出是角度，需要根据实际范围调整
        for i in range(10):
            value = msg.position[i]

            # 限制在0-255范围
            value = max(0, min(255, value))

            robot_cmd.data.append(int(value))

        # 发布到机器人
        self.robot_pub.publish(robot_cmd)

        # 打印调试信息（可选）
        if self.get_clock().now().nanoseconds % 1000000000 < 100000000:  # 每秒打印一次
            self.get_logger().info(f'手套→机器人: {robot_cmd.data[:5]}...')


def main(args=None):
    rclpy.init(args=args)
    node = GloveToRobotBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()