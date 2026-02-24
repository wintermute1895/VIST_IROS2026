#!/usr/bin/env python3
"""
ROS2遥操作性能监控节点（扩展版）

功能：
1. 监控话题发布频率
2. 计算端到端延迟
3. 计算速度、加速度、Jerk
4. 计算位置跟踪误差
5. 检测丢包率
6. 评估多关节同步性
7. 检测稳定性（振荡、超调）
8. 记录性能数据到CSV文件
9. 实时显示统计信息
10. 可配置化的指标开关
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
import time
import csv
import os
import numpy as np
from collections import deque
from datetime import datetime
import statistics


class PerformanceMonitorAdvanced(Node):
    def __init__(self):
        super().__init__('performance_monitor_advanced')

        # 声明基本参数
        self.declare_parameter('input_topic', '/cb_left_hand_control_cmd')
        self.declare_parameter('feedback_topic', '')  # 实际位置反馈话题
        self.declare_parameter('output_file', 'performance_log.csv')
        self.declare_parameter('window_size', 100)
        self.declare_parameter('print_interval', 5.0)

        # 声明指标开关参数
        self.declare_parameter('enable_frequency', True)
        self.declare_parameter('enable_latency', True)
        self.declare_parameter('enable_velocity', True)
        self.declare_parameter('enable_acceleration', True)
        self.declare_parameter('enable_jerk', True)
        self.declare_parameter('enable_tracking_error', True)
        self.declare_parameter('enable_packet_loss', True)
        self.declare_parameter('enable_synchronization', True)
        self.declare_parameter('enable_stability', True)

        # 获取参数
        self.input_topic = self.get_parameter('input_topic').value
        self.feedback_topic = self.get_parameter('feedback_topic').value
        self.output_file = self.get_parameter('output_file').value
        self.window_size = self.get_parameter('window_size').value
        self.print_interval = self.get_parameter('print_interval').value

        # 获取指标开关
        self.enable_frequency = self.get_parameter('enable_frequency').value
        self.enable_latency = self.get_parameter('enable_latency').value
        self.enable_velocity = self.get_parameter('enable_velocity').value
        self.enable_acceleration = self.get_parameter('enable_acceleration').value
        self.enable_jerk = self.get_parameter('enable_jerk').value
        self.enable_tracking_error = self.get_parameter('enable_tracking_error').value
        self.enable_packet_loss = self.get_parameter('enable_packet_loss').value
        self.enable_synchronization = self.get_parameter('enable_synchronization').value
        self.enable_stability = self.get_parameter('enable_stability').value

        # 数据存储
        self.timestamps = deque(maxlen=self.window_size)
        self.positions = deque(maxlen=self.window_size)  # 存储位置数据
        self.feedback_positions = deque(maxlen=self.window_size)  # 反馈位置

        # 指标数据
        self.frequencies = deque(maxlen=self.window_size)
        self.latencies = deque(maxlen=self.window_size)
        self.velocities = deque(maxlen=self.window_size)
        self.accelerations = deque(maxlen=self.window_size)
        self.jerks = deque(maxlen=self.window_size)
        self.tracking_errors = deque(maxlen=self.window_size)
        self.sync_errors = deque(maxlen=self.window_size)

        # 辅助变量
        self.last_time = None
        self.last_position = None
        self.last_velocity = None
        self.last_acceleration = None
        self.last_print_time = time.time()
        self.message_count = 0
        self.expected_seq = 0
        self.packet_loss_count = 0
        self.start_time = time.time()

        # 创建订阅者
        self.input_sub = self.create_subscription(
            JointState,
            self.input_topic,
            self.input_callback,
            10
        )

        if self.feedback_topic and self.enable_tracking_error:
            self.feedback_sub = self.create_subscription(
                JointState,
                self.feedback_topic,
                self.feedback_callback,
                10
            )

        # 创建CSV文件
        self.setup_csv_file()

        # 打印配置信息
        self.print_configuration()

    def setup_csv_file(self):
        """设置CSV文件和表头"""
        self.csv_file = open(self.output_file, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # 动态生成表头
        headers = ['timestamp', 'message_count']

        if self.enable_frequency:
            headers.extend(['frequency_hz', 'avg_frequency', 'std_frequency'])
        if self.enable_latency:
            headers.extend(['latency_ms', 'avg_latency', 'std_latency'])
        if self.enable_velocity:
            headers.extend(['velocity_max', 'avg_velocity', 'std_velocity'])
        if self.enable_acceleration:
            headers.extend(['acceleration_max', 'avg_acceleration', 'std_acceleration'])
        if self.enable_jerk:
            headers.extend(['jerk_max', 'avg_jerk', 'std_jerk'])
        if self.enable_tracking_error:
            headers.extend(['tracking_error_max', 'avg_tracking_error', 'std_tracking_error'])
        if self.enable_packet_loss:
            headers.extend(['packet_loss_rate'])
        if self.enable_synchronization:
            headers.extend(['sync_error_max', 'avg_sync_error'])
        if self.enable_stability:
            headers.extend(['oscillation_detected', 'stability_score'])

        self.csv_writer.writerow(headers)

    def print_configuration(self):
        """打印配置信息"""
        self.get_logger().info('=' * 60)
        self.get_logger().info('性能监控节点已启动（扩展版）')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'监控话题: {self.input_topic}')
        if self.feedback_topic:
            self.get_logger().info(f'反馈话题: {self.feedback_topic}')
        self.get_logger().info(f'输出文件: {self.output_file}')
        self.get_logger().info(f'窗口大小: {self.window_size}')
        self.get_logger().info('')
        self.get_logger().info('启用的指标:')
        if self.enable_frequency:
            self.get_logger().info('  ✓ 频率监控')
        if self.enable_latency:
            self.get_logger().info('  ✓ 延迟测量')
        if self.enable_velocity:
            self.get_logger().info('  ✓ 速度计算')
        if self.enable_acceleration:
            self.get_logger().info('  ✓ 加速度计算')
        if self.enable_jerk:
            self.get_logger().info('  ✓ Jerk计算')
        if self.enable_tracking_error:
            self.get_logger().info('  ✓ 跟踪误差')
        if self.enable_packet_loss:
            self.get_logger().info('  ✓ 丢包检测')
        if self.enable_synchronization:
            self.get_logger().info('  ✓ 同步性评估')
        if self.enable_stability:
            self.get_logger().info('  ✓ 稳定性分析')
        self.get_logger().info('=' * 60)

    def input_callback(self, msg):
        """处理输入话题消息"""
        current_time = time.time()
        self.message_count += 1

        # 存储时间戳和位置
        self.timestamps.append(current_time)
        if len(msg.position) > 0:
            self.positions.append(np.array(msg.position))

        # 1. 频率计算
        if self.enable_frequency and self.last_time is not None:
            dt = current_time - self.last_time
            if dt > 0:
                freq = 1.0 / dt
                self.frequencies.append(freq)

        # 2. 延迟计算
        if self.enable_latency:
            if msg.header.stamp.sec > 0 or msg.header.stamp.nanosec > 0:
                msg_time = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
                now = self.get_clock().now()
                now_sec = now.seconds_nanoseconds()[0] + now.seconds_nanoseconds()[1] * 1e-9
                latency = (now_sec - msg_time) * 1000
                if 0 <= latency < 10000:
                    self.latencies.append(latency)

        # 3-5. 速度、加速度、Jerk计算
        if len(msg.position) > 0 and self.last_time is not None:
            current_pos = np.array(msg.position)
            dt = current_time - self.last_time

            if dt > 0 and self.last_position is not None:
                # 速度 (一阶导数)
                if self.enable_velocity:
                    velocity = (current_pos - self.last_position) / dt
                    velocity_norm = np.linalg.norm(velocity)
                    self.velocities.append(velocity_norm)
                    current_velocity = velocity
                else:
                    current_velocity = (current_pos - self.last_position) / dt

                # 加速度 (二阶导数)
                if self.enable_acceleration and self.last_velocity is not None:
                    acceleration = (current_velocity - self.last_velocity) / dt
                    acceleration_norm = np.linalg.norm(acceleration)
                    self.accelerations.append(acceleration_norm)
                    current_acceleration = acceleration
                else:
                    current_acceleration = None

                # Jerk (三阶导数)
                if self.enable_jerk and self.last_acceleration is not None and current_acceleration is not None:
                    jerk = (current_acceleration - self.last_acceleration) / dt
                    jerk_norm = np.linalg.norm(jerk)
                    self.jerks.append(jerk_norm)

                # 更新上一次的速度和加速度
                self.last_velocity = current_velocity
                if current_acceleration is not None:
                    self.last_acceleration = current_acceleration

            self.last_position = current_pos

        # 6. 丢包检测
        if self.enable_packet_loss:
            # 假设消息有序列号（如果没有，可以用时间戳估计）
            if self.expected_seq > 0:
                # 简化版：检测时间间隔异常
                if self.last_time is not None:
                    dt = current_time - self.last_time
                    expected_dt = 1.0 / 30.0  # 假设30Hz
                    if dt > expected_dt * 2:  # 超过2倍周期认为丢包
                        self.packet_loss_count += 1
            self.expected_seq += 1

        # 7. 同步性评估（多关节）
        if self.enable_synchronization and len(msg.position) > 1:
            # 计算关节位置的标准差作为同步性指标
            sync_error = np.std(msg.position)
            self.sync_errors.append(sync_error)

        # 记录数据
        self.record_data()

        # 定期打印统计信息
        if current_time - self.last_print_time >= self.print_interval:
            self.print_statistics()
            self.last_print_time = current_time

        self.last_time = current_time

    def feedback_callback(self, msg):
        """处理反馈话题消息"""
        if len(msg.position) > 0:
            self.feedback_positions.append(np.array(msg.position))

            # 计算跟踪误差
            if self.enable_tracking_error and len(self.positions) > 0:
                # 使用最近的期望位置
                desired_pos = self.positions[-1]
                actual_pos = np.array(msg.position)

                if len(desired_pos) == len(actual_pos):
                    error = np.linalg.norm(desired_pos - actual_pos)
                    self.tracking_errors.append(error)

    def record_data(self):
        """记录数据到CSV文件"""
        row = [time.time(), self.message_count]

        if self.enable_frequency:
            freq = self.frequencies[-1] if self.frequencies else 0
            avg_freq = statistics.mean(self.frequencies) if self.frequencies else 0
            std_freq = statistics.stdev(self.frequencies) if len(self.frequencies) > 1 else 0
            row.extend([freq, avg_freq, std_freq])

        if self.enable_latency:
            lat = self.latencies[-1] if self.latencies else 0
            avg_lat = statistics.mean(self.latencies) if self.latencies else 0
            std_lat = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
            row.extend([lat, avg_lat, std_lat])

        if self.enable_velocity:
            vel = self.velocities[-1] if self.velocities else 0
            avg_vel = statistics.mean(self.velocities) if self.velocities else 0
            std_vel = statistics.stdev(self.velocities) if len(self.velocities) > 1 else 0
            row.extend([vel, avg_vel, std_vel])

        if self.enable_acceleration:
            acc = self.accelerations[-1] if self.accelerations else 0
            avg_acc = statistics.mean(self.accelerations) if self.accelerations else 0
            std_acc = statistics.stdev(self.accelerations) if len(self.accelerations) > 1 else 0
            row.extend([acc, avg_acc, std_acc])

        if self.enable_jerk:
            jrk = self.jerks[-1] if self.jerks else 0
            avg_jrk = statistics.mean(self.jerks) if self.jerks else 0
            std_jrk = statistics.stdev(self.jerks) if len(self.jerks) > 1 else 0
            row.extend([jrk, avg_jrk, std_jrk])

        if self.enable_tracking_error:
            err = self.tracking_errors[-1] if self.tracking_errors else 0
            avg_err = statistics.mean(self.tracking_errors) if self.tracking_errors else 0
            std_err = statistics.stdev(self.tracking_errors) if len(self.tracking_errors) > 1 else 0
            row.extend([err, avg_err, std_err])

        if self.enable_packet_loss:
            loss_rate = self.packet_loss_count / self.message_count if self.message_count > 0 else 0
            row.append(loss_rate)

        if self.enable_synchronization:
            sync = self.sync_errors[-1] if self.sync_errors else 0
            avg_sync = statistics.mean(self.sync_errors) if self.sync_errors else 0
            row.extend([sync, avg_sync])

        if self.enable_stability:
            # 简化版稳定性检测：检测振荡
            oscillation = self.detect_oscillation()
            stability_score = self.calculate_stability_score()
            row.extend([oscillation, stability_score])

        self.csv_writer.writerow(row)

    def detect_oscillation(self):
        """检测振荡"""
        if len(self.positions) < 10:
            return 0

        # 简单方法：检测符号变化
        recent_positions = list(self.positions)[-10:]
        if len(recent_positions) < 2:
            return 0

        # 计算差分
        diffs = [recent_positions[i+1] - recent_positions[i] for i in range(len(recent_positions)-1)]

        # 检测符号变化次数
        sign_changes = 0
        for i in range(len(diffs)-1):
            if np.any(np.sign(diffs[i]) != np.sign(diffs[i+1])):
                sign_changes += 1

        # 如果符号变化频繁，认为有振荡
        return 1 if sign_changes > 5 else 0

    def calculate_stability_score(self):
        """计算稳定性得分 (0-1, 1表示最稳定)"""
        if not self.velocities or not self.accelerations:
            return 1.0

        # 基于速度和加速度的变化率
        vel_std = statistics.stdev(self.velocities) if len(self.velocities) > 1 else 0
        acc_std = statistics.stdev(self.accelerations) if len(self.accelerations) > 1 else 0

        # 归一化并计算得分
        vel_score = 1.0 / (1.0 + vel_std)
        acc_score = 1.0 / (1.0 + acc_std)

        return (vel_score + acc_score) / 2.0

    def print_statistics(self):
        """打印统计信息"""
        elapsed_time = time.time() - self.start_time

        self.get_logger().info('=' * 60)
        self.get_logger().info(f'性能统计 (运行时间: {elapsed_time:.1f}秒)')
        self.get_logger().info(f'消息总数: {self.message_count}')

        if self.enable_frequency and self.frequencies:
            avg_freq = statistics.mean(self.frequencies)
            std_freq = statistics.stdev(self.frequencies) if len(self.frequencies) > 1 else 0
            self.get_logger().info(f'频率: {avg_freq:.2f} ± {std_freq:.2f} Hz')

        if self.enable_latency and self.latencies:
            avg_lat = statistics.mean(self.latencies)
            std_lat = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
            self.get_logger().info(f'延迟: {avg_lat:.2f} ± {std_lat:.2f} ms')

        if self.enable_velocity and self.velocities:
            avg_vel = statistics.mean(self.velocities)
            max_vel = max(self.velocities)
            self.get_logger().info(f'速度: 平均 {avg_vel:.3f}, 最大 {max_vel:.3f}')

        if self.enable_acceleration and self.accelerations:
            avg_acc = statistics.mean(self.accelerations)
            max_acc = max(self.accelerations)
            self.get_logger().info(f'加速度: 平均 {avg_acc:.3f}, 最大 {max_acc:.3f}')

        if self.enable_jerk and self.jerks:
            avg_jrk = statistics.mean(self.jerks)
            max_jrk = max(self.jerks)
            self.get_logger().info(f'Jerk: 平均 {avg_jrk:.3f}, 最大 {max_jrk:.3f}')

        if self.enable_tracking_error and self.tracking_errors:
            avg_err = statistics.mean(self.tracking_errors)
            max_err = max(self.tracking_errors)
            self.get_logger().info(f'跟踪误差: 平均 {avg_err:.4f}, 最大 {max_err:.4f}')

        if self.enable_packet_loss:
            loss_rate = self.packet_loss_count / self.message_count if self.message_count > 0 else 0
            self.get_logger().info(f'丢包率: {loss_rate*100:.2f}%')

        if self.enable_synchronization and self.sync_errors:
            avg_sync = statistics.mean(self.sync_errors)
            self.get_logger().info(f'同步误差: {avg_sync:.4f}')

        if self.enable_stability:
            stability = self.calculate_stability_score()
            self.get_logger().info(f'稳定性得分: {stability:.3f}')

        self.get_logger().info('=' * 60)

    def destroy_node(self):
        """清理资源"""
        self.print_statistics()
        self.csv_file.close()
        self.get_logger().info(f'性能数据已保存到: {self.output_file}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    monitor = PerformanceMonitorAdvanced()

    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
