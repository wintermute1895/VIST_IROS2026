#!/usr/bin/env python3
"""
ROS2适配器：将现有节点接入统一的joint_follow话题

功能：
1. 纯视觉控制节点 → /vision_control/joint_follow
2. 仿真节点 → /simulation/joint_follow
3. 遥操臂 → /exo_control/joint_follow

这样就可以在同一个话题格式下对比性能
"""

import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.msg import FollowJoint
from sensor_msgs.msg import JointState
import socket
import json
import numpy as np


class VisionToROS2Adapter(Node):
    """纯视觉控制UDP → ROS2适配器"""

    def __init__(self):
        super().__init__('vision_to_ros2_adapter')

        # 参数
        self.declare_parameter('udp_port', 5005)
        self.declare_parameter('output_topic', '/vision_control/joint_follow')

        udp_port = self.get_parameter('udp_port').value
        output_topic = self.get_parameter('output_topic').value

        # 创建UDP接收器
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', udp_port))
        self.sock.settimeout(0.01)  # 10ms超时

        # 创建ROS2发布器
        self.publisher = self.create_publisher(
            FollowJoint,
            output_topic,
            10
        )

        # 创建定时器检查UDP数据
        self.timer = self.create_timer(0.001, self.check_udp_data)  # 1ms检查一次

        self.get_logger().info(f'纯视觉控制适配器已启动')
        self.get_logger().info(f'  UDP端口: {udp_port}')
        self.get_logger().info(f'  输出话题: {output_topic}')

    def check_udp_data(self):
        """检查并处理UDP数据"""
        try:
            data, addr = self.sock.recvfrom(4096)
            # 解析JSON数据
            vision_data = json.loads(data.decode('utf-8'))

            # 提取关节角度（假设你的视觉节点输出包含joint_angles字段）
            if 'joint_angles' in vision_data:
                joint_angles = vision_data['joint_angles']

                # 发布到ROS2
                msg = FollowJoint()
                msg.joints = joint_angles
                self.publisher.publish(msg)

        except socket.timeout:
            # 没有数据，正常情况
            pass
        except Exception as e:
            self.get_logger().warn(f'处理UDP数据失败: {e}')


class SimulationToROS2Adapter(Node):
    """仿真节点 → ROS2适配器"""

    def __init__(self):
        super().__init__('simulation_to_ros2_adapter')

        # 参数
        self.declare_parameter('input_topic', '/joint_states')
        self.declare_parameter('output_topic', '/simulation/joint_follow')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value

        # 订阅仿真节点的JointState
        self.subscription = self.create_subscription(
            JointState,
            input_topic,
            self.joint_state_callback,
            10
        )

        # 发布到统一的FollowJoint话题
        self.publisher = self.create_publisher(
            FollowJoint,
            output_topic,
            10
        )

        self.get_logger().info(f'仿真适配器已启动')
        self.get_logger().info(f'  输入话题: {input_topic}')
        self.get_logger().info(f'  输出话题: {output_topic}')

    def joint_state_callback(self, msg):
        """将JointState转换为FollowJoint"""
        follow_msg = FollowJoint()

        # 使用position字段（如果是角度数据）
        if len(msg.position) > 0:
            follow_msg.joints = list(msg.position)
            self.publisher.publish(follow_msg)


class ExoToROS2Adapter(Node):
    """遥操臂 → ROS2适配器（如果需要重新映射话题）"""

    def __init__(self):
        super().__init__('exo_to_ros2_adapter')

        # 参数
        self.declare_parameter('input_topic', '/left_joint_follow')
        self.declare_parameter('output_topic', '/exo_control/joint_follow')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value

        # 订阅遥操臂原始话题
        self.subscription = self.create_subscription(
            FollowJoint,
            input_topic,
            self.follow_joint_callback,
            10
        )

        # 发布到统一话题
        self.publisher = self.create_publisher(
            FollowJoint,
            output_topic,
            10
        )

        self.get_logger().info(f'遥操臂适配器已启动')
        self.get_logger().info(f'  输入话题: {input_topic}')
        self.get_logger().info(f'  输出话题: {output_topic}')

    def follow_joint_callback(self, msg):
        """直接转发（可以在这里添加单位转换等）"""
        # 如果遥操臂输出是角度，需要转换为弧度
        converted_msg = FollowJoint()
        converted_msg.joints = [np.deg2rad(j) for j in msg.joints]
        self.publisher.publish(converted_msg)


def main():
    rclpy.init()

    import sys
    if len(sys.argv) < 2:
        print("用法: python3 ros2_adapters.py [vision|simulation|exo]")
        sys.exit(1)

    adapter_type = sys.argv[1]

    if adapter_type == 'vision':
        node = VisionToROS2Adapter()
    elif adapter_type == 'simulation':
        node = SimulationToROS2Adapter()
    elif adapter_type == 'exo':
        node = ExoToROS2Adapter()
    else:
        print(f"未知适配器类型: {adapter_type}")
        sys.exit(1)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()