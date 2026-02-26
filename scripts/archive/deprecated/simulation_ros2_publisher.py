#!/usr/bin/env python3
"""
为 simulate_full_flow.py 添加 ROS2 发布功能

用途：
1. 让仿真脚本发布关节角度到 ROS2 话题
2. 统一数据格式为 FollowJoint
3. 可以与遥操臂数据直接对比

使用方法：
    在 simulate_full_flow.py 中导入并使用这个模块
"""

import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.msg import FollowJoint
from sensor_msgs.msg import JointState
import numpy as np


class SimulationPublisher(Node):
    """仿真数据发布节点"""

    def __init__(self, publish_rate=30.0):
        """
        初始化发布节点

        Args:
            publish_rate: 发布频率 (Hz)
        """
        super().__init__('simulation_publisher')

        # 创建发布器 - FollowJoint格式（与遥操臂一致）
        self.follow_joint_pub = self.create_publisher(
            FollowJoint,
            '/vision_control/joint_follow',
            10
        )

        # 创建发布器 - JointState格式（标准ROS格式）
        self.joint_state_pub = self.create_publisher(
            JointState,
            '/vision_control/joint_states',
            10
        )

        self.publish_rate = publish_rate
        self.get_logger().info(f'仿真发布节点已启动 (频率: {publish_rate} Hz)')
        self.get_logger().info(f'  发布话题: /vision_control/joint_follow')
        self.get_logger().info(f'  发布话题: /vision_control/joint_states')

    def publish_joint_angles(self, joint_angles, joint_names=None):
        """
        发布关节角度

        Args:
            joint_angles: 关节角度数组 (弧度)
            joint_names: 关节名称列表（可选）
        """
        # 发布 FollowJoint 消息
        follow_msg = FollowJoint()
        follow_msg.joints = list(joint_angles)
        self.follow_joint_pub.publish(follow_msg)

        # 发布 JointState 消息
        joint_state_msg = JointState()
        joint_state_msg.header.stamp = self.get_clock().now().to_msg()
        joint_state_msg.position = list(joint_angles)

        if joint_names is not None:
            joint_state_msg.name = joint_names
        else:
            # 默认关节名称
            joint_state_msg.name = [f'joint_{i+1}' for i in range(len(joint_angles))]

        self.joint_state_pub.publish(joint_state_msg)


class SimulationPublisherWrapper:
    """
    仿真发布器包装类

    用于在非ROS2环境中也能正常运行（优雅降级）
    """

    def __init__(self, publish_rate=30.0, enable_ros2=True):
        """
        初始化包装器

        Args:
            publish_rate: 发布频率 (Hz)
            enable_ros2: 是否启用ROS2发布
        """
        self.enable_ros2 = enable_ros2
        self.node = None

        if enable_ros2:
            try:
                # 尝试初始化ROS2
                if not rclpy.ok():
                    rclpy.init()

                self.node = SimulationPublisher(publish_rate)
                print(f"✅ ROS2发布已启用 (频率: {publish_rate} Hz)")

            except Exception as e:
                print(f"⚠️  ROS2初始化失败: {e}")
                print("   将继续运行但不发布ROS2消息")
                self.enable_ros2 = False
        else:
            print("ℹ️  ROS2发布已禁用")

    def publish(self, joint_angles, joint_names=None):
        """
        发布关节角度

        Args:
            joint_angles: 关节角度数组 (弧度)
            joint_names: 关节名称列表（可选）
        """
        if self.enable_ros2 and self.node is not None:
            try:
                self.node.publish_joint_angles(joint_angles, joint_names)
                # 处理ROS2回调
                rclpy.spin_once(self.node, timeout_sec=0.0)
            except Exception as e:
                print(f"⚠️  发布失败: {e}")

    def shutdown(self):
        """关闭发布器"""
        if self.node is not None:
            self.node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


# ============================================
# 使用示例（在 simulate_full_flow.py 中）
# ============================================

def example_usage():
    """
    在 simulate_full_flow.py 中的使用示例
    """
    # 在 FullFlowSimulator.__init__ 中添加：
    """
    # 初始化ROS2发布器
    print("\\n📡 初始化ROS2发布器...")
    from scripts.simulation_ros2_publisher import SimulationPublisherWrapper

    enable_ros2 = getattr(self.config, 'simulation_enable_ros2_publish', True)
    publish_rate = getattr(self.config, 'vision_fps', 30.0)

    self.ros2_publisher = SimulationPublisherWrapper(
        publish_rate=publish_rate,
        enable_ros2=enable_ros2
    )
    """

    # 在主循环中发布数据（run方法中）：
    """
    # 在计算出关节角度后
    if hasattr(self, 'ros2_publisher'):
        self.ros2_publisher.publish(q_solution)
    """

    # 在退出时清理：
    """
    def cleanup(self):
        if hasattr(self, 'ros2_publisher'):
            self.ros2_publisher.shutdown()
    """


if __name__ == '__main__':
    # 测试发布器
    print("测试仿真发布器...")

    wrapper = SimulationPublisherWrapper(publish_rate=30.0)

    # 模拟发布一些数据
    import time
    for i in range(10):
        joint_angles = np.random.randn(7) * 0.1  # 随机关节角度
        wrapper.publish(joint_angles)
        print(f"发布第 {i+1} 条数据")
        time.sleep(1.0 / 30.0)  # 30Hz

    wrapper.shutdown()
    print("测试完成")