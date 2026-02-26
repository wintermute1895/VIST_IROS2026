#!/usr/bin/env python3
"""
模拟lbot_driver节点
完全不连接真机，用于测试控制流程的频率
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from lbot_arm_interfaces.msg import FollowJoint
from lbot_arm_interfaces.srv import MoveJ
import numpy as np
import time
from collections import deque


class MockLbotDriver(Node):
    def __init__(self):
        super().__init__('mock_lbot_driver')

        # 声明参数
        self.declare_parameter('robot_namespace', 'robot1')
        self.declare_parameter('monitor_frequency', True)

        namespace = self.get_parameter('robot_namespace').value
        self.monitor_freq = self.get_parameter('monitor_frequency').value

        # 订阅joint_follow命令（模拟接收控制命令）
        self.left_follow_sub = self.create_subscription(
            FollowJoint,
            f'/{namespace}/left_arm/joint_follow',
            lambda msg: self.follow_callback(msg, 'left'),
            10
        )

        self.right_follow_sub = self.create_subscription(
            FollowJoint,
            f'/{namespace}/right_arm/joint_follow',
            lambda msg: self.follow_callback(msg, 'right'),
            10
        )

        # 发布joint_states（模拟机器人状态反馈）
        self.left_state_pub = self.create_publisher(
            JointState,
            f'/{namespace}/left_arm/joint_states',
            10
        )

        self.right_state_pub = self.create_publisher(
            JointState,
            f'/{namespace}/right_arm/joint_states',
            10
        )

        # 创建MoveJ服务（模拟首次移动服务）
        self.left_movej_service = self.create_service(
            MoveJ,
            f'/{namespace}/left_arm/move_joint',
            lambda req, res: self.movej_callback(req, res, 'left')
        )

        self.right_movej_service = self.create_service(
            MoveJ,
            f'/{namespace}/right_arm/move_joint',
            lambda req, res: self.movej_callback(req, res, 'right')
        )

        # 频率监控
        self.left_timestamps = deque(maxlen=100)
        self.right_timestamps = deque(maxlen=100)

        # 当前位置（模拟）
        self.left_position = np.zeros(7)
        self.right_position = np.zeros(7)

        # 上一次采样的位置和时间（用于速度计算）
        self.left_last_position = np.zeros(7)
        self.right_last_position = np.zeros(7)
        self.left_last_sample_time = None
        self.right_last_sample_time = None

        # 速度阈值（rad/s）- 超过此值将触发警报
        self.declare_parameter('velocity_threshold', 3.0)
        self.velocity_threshold = self.get_parameter('velocity_threshold').value

        # 加速度阈值（rad/s^2）
        self.declare_parameter('acceleration_threshold', 100.0)
        self.acceleration_threshold = self.get_parameter('acceleration_threshold').value

        # 创建定时器，以50Hz采样和发布状态（模拟真机的50Hz反馈）
        # 这个频率模拟了真实机械臂底层固件的控制循环频率
        self.state_timer = self.create_timer(0.02, self.sample_and_publish_states)

        # 创建定时器，每秒打印频率统计
        if self.monitor_freq:
            self.monitor_timer = self.create_timer(1.0, self.print_frequency_stats)

        self.get_logger().info('='*80)
        self.get_logger().info('模拟lbot_driver已启动（不连接真机）')
        self.get_logger().info('='*80)
        self.get_logger().info(f'命名空间: {namespace}')
        self.get_logger().info(f'订阅: /{namespace}/left_arm/joint_follow')
        self.get_logger().info(f'订阅: /{namespace}/right_arm/joint_follow')
        self.get_logger().info(f'发布: /{namespace}/left_arm/joint_states (50Hz)')
        self.get_logger().info(f'发布: /{namespace}/right_arm/joint_states (50Hz)')
        self.get_logger().info(f'服务: /{namespace}/left_arm/move_joint (MoveJ)')
        self.get_logger().info(f'服务: /{namespace}/right_arm/move_joint (MoveJ)')
        self.get_logger().info('='*80)
        self.get_logger().info('安全监控已启用:')
        self.get_logger().info(f'  速度阈值: {self.velocity_threshold} rad/s')
        self.get_logger().info(f'  加速度阈值: {self.acceleration_threshold} rad/s²')
        self.get_logger().info(f'  采样频率: 50 Hz (模拟真机底层固件)')
        self.get_logger().info('='*80)

    def movej_callback(self, request, response, arm):
        """处理MoveJ服务请求（模拟首次移动）"""
        self.get_logger().info(f'[Mock] 收到 {arm} 臂 MoveJ 请求，模拟执行中...')

        # 模拟移动：直接设置目标位置
        if arm == 'left':
            if request.joints and len(request.joints) >= 7:
                self.left_position = np.array(request.joints[:7])
        else:
            if request.joints and len(request.joints) >= 7:
                self.right_position = np.array(request.joints[:7])

        # 返回成功（MoveJ_Response 只有 success 字段）
        response.success = True

        self.get_logger().info(f'[Mock] {arm} 臂 MoveJ 完成')
        return response

    def follow_callback(self, msg, arm):
        """接收joint_follow命令"""
        current_time = time.time()

        # 记录时间戳用于频率监控
        if arm == 'left':
            self.left_timestamps.append(current_time)
            if msg.joints and len(msg.joints) >= 7:
                self.left_position = np.array(msg.joints[:7])
        else:
            self.right_timestamps.append(current_time)
            if msg.joints and len(msg.joints) >= 7:
                self.right_position = np.array(msg.joints[:7])

    def sample_and_publish_states(self):
        """
        以50Hz采样最新的指令并发布机器人状态
        这模拟了真实机械臂底层固件的行为：
        - 每20ms醒来一次
        - 从接收缓冲区抓取最新指令
        - 计算瞬时速度和加速度
        - 检测危险的运动指令
        """
        current_time = time.time()

        # 采样左臂
        self._sample_arm(
            'left',
            self.left_position,
            self.left_last_position,
            self.left_last_sample_time,
            current_time
        )
        self.left_last_position = self.left_position.copy()
        self.left_last_sample_time = current_time

        # 采样右臂
        self._sample_arm(
            'right',
            self.right_position,
            self.right_last_position,
            self.right_last_sample_time,
            current_time
        )
        self.right_last_position = self.right_position.copy()
        self.right_last_sample_time = current_time

        # 发布状态
        self._publish_arm_state('left', self.left_position, self.left_state_pub)
        self._publish_arm_state('right', self.right_position, self.right_state_pub)

    def _sample_arm(self, arm_name, current_pos, last_pos, last_time, current_time):
        """采样单个机械臂并检测危险运动"""
        if last_time is None:
            return  # 第一次采样，没有历史数据

        dt = current_time - last_time
        if dt <= 0:
            return

        # 计算位置差（模拟从缓冲区抓取到的新指令与上次指令的差异）
        position_delta = current_pos - last_pos

        # 计算瞬时速度（rad/s）
        instantaneous_velocity = position_delta / dt

        # 计算瞬时加速度（rad/s^2）
        # 注意：这里简化处理，实际应该用速度差/时间差
        instantaneous_acceleration = instantaneous_velocity / dt

        # 检测每个关节
        for joint_idx in range(len(current_pos)):
            vel = abs(instantaneous_velocity[joint_idx])
            acc = abs(instantaneous_acceleration[joint_idx])
            pos_delta = abs(position_delta[joint_idx])

            # 速度阈值检测
            if vel > self.velocity_threshold:
                self.get_logger().error(
                    f'🚨 [{arm_name}] 关节{joint_idx} 速度异常！'
                    f'瞬时速度 = {vel:.2f} rad/s (阈值: {self.velocity_threshold} rad/s)'
                )
                self.get_logger().error(
                    f'    位置跳变: {pos_delta:.4f} rad, 时间间隔: {dt*1000:.1f} ms'
                )

            # 加速度阈值检测
            if acc > self.acceleration_threshold:
                self.get_logger().error(
                    f'🚨 [{arm_name}] 关节{joint_idx} 加速度异常！'
                    f'瞬时加速度 = {acc:.2f} rad/s² (阈值: {self.acceleration_threshold} rad/s²)'
                )

            # 极端情况：单次跳变超过0.3弧度（约17度）
            if pos_delta > 0.3:
                self.get_logger().fatal(
                    f'💀 [{arm_name}] 关节{joint_idx} 检测到极端位置跳变！'
                    f'跳变量: {pos_delta:.4f} rad ({np.degrees(pos_delta):.1f}°)'
                    f' - 这将导致电机烧毁！'
                )

    def _publish_arm_state(self, arm_name, position, publisher):
        """发布机械臂状态"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [f'joint_{i}' for i in range(7)]
        msg.position = position.tolist()
        msg.velocity = [0.0] * 7
        msg.effort = [0.0] * 7
        publisher.publish(msg)

    def calculate_frequency(self, timestamps):
        """计算频率"""
        if len(timestamps) < 2:
            return None, None, None, 0

        ts_list = list(timestamps)
        intervals = [ts_list[i] - ts_list[i-1] for i in range(1, len(ts_list))]

        if not intervals:
            return None, None, None, 0

        avg_interval = sum(intervals) / len(intervals)
        min_interval = min(intervals)
        max_interval = max(intervals)

        avg_freq = 1.0 / avg_interval if avg_interval > 0 else 0
        min_freq = 1.0 / max_interval if max_interval > 0 else 0
        max_freq = 1.0 / min_interval if min_interval > 0 else 0

        return avg_freq, min_freq, max_freq, len(timestamps)

    def print_frequency_stats(self):
        """打印频率统计"""
        left_avg, left_min, left_max, left_count = self.calculate_frequency(self.left_timestamps)
        right_avg, right_min, right_max, right_count = self.calculate_frequency(self.right_timestamps)

        print("\n" + "="*80)
        print(f"joint_follow 接收频率统计 - {time.strftime('%H:%M:%S')}")
        print("="*80)

        if left_avg is not None:
            print(f"\n左臂 joint_follow:")
            print(f"  平均频率: {left_avg:.2f} Hz")
            print(f"  频率范围: {left_min:.2f} - {left_max:.2f} Hz")
            print(f"  样本数: {left_count}")

            # 警告检查
            if left_avg > 200:
                print(f"  ⚠️  警告: 频率过高！可能导致电机过载")
            elif left_avg > 100:
                print(f"  ⚠️  注意: 频率偏高，建议降低到100Hz以下")
            else:
                print(f"  ✅ 频率正常")
        else:
            print(f"\n左臂 joint_follow: 无数据")

        if right_avg is not None:
            print(f"\n右臂 joint_follow:")
            print(f"  平均频率: {right_avg:.2f} Hz")
            print(f"  频率范围: {right_min:.2f} - {right_max:.2f} Hz")
            print(f"  样本数: {right_count}")

            # 警告检查
            if right_avg > 200:
                print(f"  ⚠️  警告: 频率过高！可能导致电机过载")
            elif right_avg > 100:
                print(f"  ⚠️  注意: 频率偏高，建议降低到100Hz以下")
            else:
                print(f"  ✅ 频率正常")
        else:
            print(f"\n右臂 joint_follow: 无数据")

        print("="*80)


def main():
    rclpy.init()

    try:
        node = MockLbotDriver()
        print("\n" + "="*80)
        print("模拟lbot_driver运行中...")
        print("现在可以启动你的控制节点进行测试")
        print("按 Ctrl+C 停止")
        print("="*80)
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n\n模拟驱动已停止")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()