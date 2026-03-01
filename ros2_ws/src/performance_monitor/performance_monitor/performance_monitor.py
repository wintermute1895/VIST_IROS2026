#!/usr/bin/env python3
"""
ROS2遥操作性能监控节点

功能：
1. 监控话题发布频率
2. 计算端到端延迟
3. 记录性能数据到CSV文件
4. 实时显示统计信息
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
import time
import csv
import os
from collections import deque
from datetime import datetime
import statistics


class PerformanceMonitor(Node):
    def __init__(self):
        super().__init__('performance_monitor')

        # 声明参数
        self.declare_parameter('input_topic', '/cb_left_hand_control_cmd')
        self.declare_parameter('output_topic', '')  # 如果有反馈话题
        self.declare_parameter('output_file', 'performance_log.csv')
        self.declare_parameter('window_size', 100)  # 统计窗口大小
        self.declare_parameter('print_interval', 5.0)  # 打印间隔（秒）

        # 获取参数
        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.output_file = self.get_parameter('output_file').value
        self.window_size = self.get_parameter('window_size').value
        self.print_interval = self.get_parameter('print_interval').value

        # 数据存储
        self.input_timestamps = deque(maxlen=self.window_size)
        self.output_timestamps = deque(maxlen=self.window_size)
        self.latencies = deque(maxlen=self.window_size)
        self.frequencies = deque(maxlen=self.window_size)

        self.last_input_time = None
        self.last_output_time = None
        self.last_print_time = time.time()

        self.message_count = 0
        self.start_time = time.time()

        # 创建订阅者
        self.input_sub = self.create_subscription(
            JointState,
            self.input_topic,
            self.input_callback,
            10
        )

        if self.output_topic:
            self.output_sub = self.create_subscription(
                JointState,
                self.output_topic,
                self.output_callback,
                10
            )

        # 创建CSV文件
        self.csv_file = open(self.output_file, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp',
            'message_count',
            'frequency_hz',
            'latency_ms',
            'avg_frequency',
            'std_frequency',
            'avg_latency',
            'std_latency',
            'min_latency',
            'max_latency'
        ])

        self.get_logger().info(f'性能监控节点已启动')
        self.get_logger().info(f'监控话题: {self.input_topic}')
        if self.output_topic:
            self.get_logger().info(f'反馈话题: {self.output_topic}')
        self.get_logger().info(f'输出文件: {self.output_file}')

    def input_callback(self, msg):
        """处理输入话题消息"""
        current_time = time.time()
        self.message_count += 1

        # 计算频率
        if self.last_input_time is not None:
            dt = current_time - self.last_input_time
            if dt > 0:
                freq = 1.0 / dt
                self.frequencies.append(freq)

        self.last_input_time = current_time
        self.input_timestamps.append(current_time)

        # 计算延迟（如果消息有时间戳）
        if msg.header.stamp.sec > 0 or msg.header.stamp.nanosec > 0:
            msg_time = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            now = self.get_clock().now()
            now_sec = now.seconds_nanoseconds()[0] + now.seconds_nanoseconds()[1] * 1e-9
            latency = (now_sec - msg_time) * 1000  # 转换为毫秒
            if latency >= 0 and latency < 10000:  # 过滤异常值
                self.latencies.append(latency)

        # 记录数据
        self.record_data(current_time, freq if self.last_input_time else 0,
                        self.latencies[-1] if self.latencies else 0)

        # 定期打印统计信息
        if current_time - self.last_print_time >= self.print_interval:
            self.print_statistics()
            self.last_print_time = current_time

    def output_callback(self, msg):
        """处理输出话题消息（如果有）"""
        current_time = time.time()
        self.output_timestamps.append(current_time)
        self.last_output_time = current_time

    def record_data(self, timestamp, frequency, latency):
        """记录数据到CSV文件"""
        # 计算统计指标
        avg_freq = statistics.mean(self.frequencies) if self.frequencies else 0
        std_freq = statistics.stdev(self.frequencies) if len(self.frequencies) > 1 else 0
        avg_lat = statistics.mean(self.latencies) if self.latencies else 0
        std_lat = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
        min_lat = min(self.latencies) if self.latencies else 0
        max_lat = max(self.latencies) if self.latencies else 0

        self.csv_writer.writerow([
            timestamp,
            self.message_count,
            frequency,
            latency,
            avg_freq,
            std_freq,
            avg_lat,
            std_lat,
            min_lat,
            max_lat
        ])

    def print_statistics(self):
        """打印统计信息"""
        if not self.frequencies:
            return

        elapsed_time = time.time() - self.start_time
        avg_freq = statistics.mean(self.frequencies)
        std_freq = statistics.stdev(self.frequencies) if len(self.frequencies) > 1 else 0

        self.get_logger().info('=' * 60)
        self.get_logger().info(f'性能统计 (运行时间: {elapsed_time:.1f}秒)')
        self.get_logger().info(f'消息总数: {self.message_count}')
        self.get_logger().info(f'平均频率: {avg_freq:.2f} Hz (±{std_freq:.2f})')

        if self.latencies:
            avg_lat = statistics.mean(self.latencies)
            std_lat = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
            min_lat = min(self.latencies)
            max_lat = max(self.latencies)
            self.get_logger().info(f'平均延迟: {avg_lat:.2f} ms (±{std_lat:.2f})')
            self.get_logger().info(f'延迟范围: [{min_lat:.2f}, {max_lat:.2f}] ms')

        self.get_logger().info('=' * 60)

    def destroy_node(self):
        """清理资源"""
        self.print_statistics()
        self.csv_file.close()
        self.get_logger().info(f'性能数据已保存到: {self.output_file}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    monitor = PerformanceMonitor()

    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
