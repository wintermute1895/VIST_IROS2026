#!/usr/bin/env python3
"""
测试插值和话题统一的脚本
用途：验证纯视觉控制和遥操臂数据能否在同一话题上比较
"""

import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.msg import FollowJoint
import numpy as np
from scipy.interpolate import interp1d
import time


class TrajectoryPublisherTest(Node):
    """测试轨迹发布节点"""

    def __init__(self):
        super().__init__('trajectory_publisher_test')

        # 创建发布器 - 统一发布到 joint_follow 话题
        self.vision_pub = self.create_publisher(
            FollowJoint,
            '/vision_control/joint_follow',
            10
        )

        self.exo_pub = self.create_publisher(
            FollowJoint,
            '/exo_control/joint_follow',
            10
        )

        # 测试参数
        self.test_duration = 10.0  # 秒
        self.vision_freq = 30.0  # Hz (纯视觉控制频率)
        self.exo_freq = 241.75  # Hz (遥操臂频率)

        # 生成测试轨迹
        self.generate_test_trajectory()

        # 创建定时器
        self.vision_timer = self.create_timer(
            1.0 / self.vision_freq,
            self.publish_vision_trajectory
        )

        self.exo_timer = self.create_timer(
            1.0 / self.exo_freq,
            self.publish_exo_trajectory
        )

        self.start_time = time.time()
        self.vision_idx = 0
        self.exo_idx = 0

        self.get_logger().info('轨迹发布测试节点已启动')
        self.get_logger().info(f'纯视觉控制频率: {self.vision_freq} Hz')
        self.get_logger().info(f'遥操臂频率: {self.exo_freq} Hz')

    def generate_test_trajectory(self):
        """生成测试轨迹 - 正弦波"""
        # 时间序列
        t = np.linspace(0, self.test_duration, 1000)

        # 生成7个关节的正弦轨迹（不同频率和相位）
        self.reference_trajectory = np.zeros((len(t), 7))
        for i in range(7):
            freq = 0.5 + i * 0.1  # 不同关节不同频率
            phase = i * np.pi / 7  # 不同相位
            amplitude = 0.3  # 幅度（弧度）
            self.reference_trajectory[:, i] = amplitude * np.sin(2 * np.pi * freq * t + phase)

        self.reference_time = t

        # 为纯视觉控制创建插值器（30Hz采样）
        vision_t = np.linspace(0, self.test_duration, int(self.test_duration * self.vision_freq))
        self.vision_trajectory = np.zeros((len(vision_t), 7))
        for i in range(7):
            interpolator = interp1d(t, self.reference_trajectory[:, i], kind='cubic')
            self.vision_trajectory[:, i] = interpolator(vision_t)

        # 为遥操臂创建插值器（241.75Hz采样）
        exo_t = np.linspace(0, self.test_duration, int(self.test_duration * self.exo_freq))
        self.exo_trajectory = np.zeros((len(exo_t), 7))
        for i in range(7):
            interpolator = interp1d(t, self.reference_trajectory[:, i], kind='cubic')
            self.exo_trajectory[:, i] = interpolator(exo_t)

        self.get_logger().info(f'生成测试轨迹: {len(vision_t)} 个视觉样本, {len(exo_t)} 个遥操样本')

    def publish_vision_trajectory(self):
        """发布纯视觉控制轨迹"""
        if self.vision_idx >= len(self.vision_trajectory):
            self.get_logger().info('纯视觉控制轨迹发布完成')
            self.vision_timer.cancel()
            return

        msg = FollowJoint()
        msg.joints = self.vision_trajectory[self.vision_idx].tolist()
        self.vision_pub.publish(msg)

        self.vision_idx += 1

    def publish_exo_trajectory(self):
        """发布遥操臂轨迹"""
        if self.exo_idx >= len(self.exo_trajectory):
            self.get_logger().info('遥操臂轨迹发布完成')
            self.exo_timer.cancel()
            return

        msg = FollowJoint()
        msg.joints = self.exo_trajectory[self.exo_idx].tolist()
        self.exo_pub.publish(msg)

        self.exo_idx += 1


class TrajectoryComparator(Node):
    """轨迹对比节点"""

    def __init__(self):
        super().__init__('trajectory_comparator')

        # 订阅两个话题
        self.vision_sub = self.create_subscription(
            FollowJoint,
            '/vision_control/joint_follow',
            self.vision_callback,
            10
        )

        self.exo_sub = self.create_subscription(
            FollowJoint,
            '/exo_control/joint_follow',
            self.exo_callback,
            10
        )

        # 数据缓存
        self.vision_data = []
        self.exo_data = []
        self.vision_timestamps = []
        self.exo_timestamps = []

        self.start_time = None

        self.get_logger().info('轨迹对比节点已启动')

    def vision_callback(self, msg):
        """接收纯视觉控制数据"""
        if self.start_time is None:
            self.start_time = time.time()

        timestamp = time.time() - self.start_time
        self.vision_data.append(np.array(msg.joints))
        self.vision_timestamps.append(timestamp)

    def exo_callback(self, msg):
        """接收遥操臂数据"""
        if self.start_time is None:
            self.start_time = time.time()

        timestamp = time.time() - self.start_time
        self.exo_data.append(np.array(msg.joints))
        self.exo_timestamps.append(timestamp)

    def analyze_and_save(self):
        """分析并保存结果"""
        if len(self.vision_data) == 0 or len(self.exo_data) == 0:
            self.get_logger().warn('没有接收到数据')
            return

        self.get_logger().info(f'接收到 {len(self.vision_data)} 个视觉样本')
        self.get_logger().info(f'接收到 {len(self.exo_data)} 个遥操样本')

        # 计算频率
        vision_freq = len(self.vision_data) / (self.vision_timestamps[-1] - self.vision_timestamps[0])
        exo_freq = len(self.exo_data) / (self.exo_timestamps[-1] - self.exo_timestamps[0])

        self.get_logger().info(f'纯视觉控制实际频率: {vision_freq:.2f} Hz')
        self.get_logger().info(f'遥操臂实际频率: {exo_freq:.2f} Hz')

        # 保存数据
        import pickle
        data = {
            'vision_data': np.array(self.vision_data),
            'vision_timestamps': np.array(self.vision_timestamps),
            'exo_data': np.array(self.exo_data),
            'exo_timestamps': np.array(self.exo_timestamps)
        }

        with open('data/test_trajectory_comparison.pkl', 'wb') as f:
            pickle.dump(data, f)

        self.get_logger().info('数据已保存到 data/test_trajectory_comparison.pkl')


def main():
    rclpy.init()

    import sys
    if len(sys.argv) < 2:
        print("用法: python3 test_trajectory_comparison.py [publisher|comparator]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'publisher':
        node = TrajectoryPublisherTest()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()

    elif mode == 'comparator':
        node = TrajectoryComparator()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            # 保存数据
            node.analyze_and_save()
        finally:
            node.destroy_node()

    else:
        print(f"未知模式: {mode}")
        sys.exit(1)

    rclpy.shutdown()


if __name__ == '__main__':
    main()