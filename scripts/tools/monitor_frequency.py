#!/usr/bin/env python3
"""
实时频率监控工具
监控所有相关话题的发布频率
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import time
from collections import deque
import threading


class FrequencyMonitor(Node):
    def __init__(self):
        super().__init__('frequency_monitor')

        # 监控的话题列表
        self.topics = {
            '/right_arm_joint_control': JointState,
            '/left_arm_joint_control': JointState,
            '/filtered_right_joint_control': JointState,
        }

        # 存储每个话题的时间戳
        self.timestamps = {topic: deque(maxlen=100) for topic in self.topics}
        self.locks = {topic: threading.Lock() for topic in self.topics}

        # 创建订阅器
        self.subscribers = {}
        for topic, msg_type in self.topics.items():
            self.subscribers[topic] = self.create_subscription(
                msg_type,
                topic,
                lambda msg, t=topic: self.callback(t, msg),
                10
            )

        # 创建定时器，每秒打印一次统计
        self.timer = self.create_timer(1.0, self.print_statistics)

        self.get_logger().info('频率监控器已启动')
        self.get_logger().info(f'监控话题: {list(self.topics.keys())}')

    def callback(self, topic, msg):
        """记录消息到达时间"""
        with self.locks[topic]:
            self.timestamps[topic].append(time.time())

    def calculate_frequency(self, topic):
        """计算话题的频率"""
        with self.locks[topic]:
            timestamps = list(self.timestamps[topic])

        if len(timestamps) < 2:
            return None, None, None

        # 计算时间间隔
        intervals = [timestamps[i] - timestamps[i-1]
                     for i in range(1, len(timestamps))]

        if not intervals:
            return None, None, None

        # 计算频率
        avg_interval = sum(intervals) / len(intervals)
        min_interval = min(intervals)
        max_interval = max(intervals)

        avg_freq = 1.0 / avg_interval if avg_interval > 0 else 0
        min_freq = 1.0 / max_interval if max_interval > 0 else 0
        max_freq = 1.0 / min_interval if min_interval > 0 else 0

        return avg_freq, min_freq, max_freq

    def print_statistics(self):
        """打印频率统计"""
        print("\n" + "="*80)
        print(f"频率监控 - {time.strftime('%H:%M:%S')}")
        print("="*80)

        for topic in self.topics:
            avg_freq, min_freq, max_freq = self.calculate_frequency(topic)

            if avg_freq is not None:
                print(f"\n话题: {topic}")
                print(f"  平均频率: {avg_freq:.2f} Hz")
                print(f"  频率范围: {min_freq:.2f} - {max_freq:.2f} Hz")
                print(f"  样本数: {len(self.timestamps[topic])}")
            else:
                print(f"\n话题: {topic}")
                print(f"  状态: 无数据")


def main():
    rclpy.init()

    try:
        monitor = FrequencyMonitor()
        print("\n" + "="*80)
        print("频率监控器运行中...")
        print("按 Ctrl+C 停止")
        print("="*80)
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    finally:
        if 'monitor' in locals():
            monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()