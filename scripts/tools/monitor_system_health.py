#!/usr/bin/env python3
"""
VIST系统健康监控工具
实时监控核心话题的发布频率，面板化显示
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, Image
from lbot_arm_interfaces.msg import FollowJoint
from std_msgs.msg import String
import time
import sys
import os
from collections import deque
from datetime import datetime


class SystemHealthMonitor(Node):
    def __init__(self):
        super().__init__('system_health_monitor')

        # 监控的话题配置
        self.topics = {
            # 话题名称: (消息类型, 显示名称, 预期频率范围)
            '/right_arm_joint_control': (JointState, '遥操源指令', (70, 90)),
            '/robot1/right_arm/joint_follow': (FollowJoint, 'VIST下发指令', (70, 90)),
            '/robot1/right_arm/joint_states': (JointState, '机械臂状态反馈', (40, 60)),
            '/cb_right_hand_control_cmd': (String, '灵巧手控制', (10, 100)),
            '/cb_right_hand_state': (String, '灵巧手状态', (10, 100)),
            '/camera_top/camera/color/image_raw': (Image, '顶部相机RGB', (25, 35)),
        }

        # 时间戳记录（每个话题保存最近100个时间戳）
        self.timestamps = {topic: deque(maxlen=100) for topic in self.topics.keys()}

        # 创建订阅者
        self.subscribers = {}
        for topic, (msg_type, _, _) in self.topics.items():
            # 对于图像话题，使用最小QoS避免反序列化开销
            self.subscribers[topic] = self.create_subscription(
                msg_type,
                topic,
                lambda msg, t=topic: self.callback(t),
                1  # 最小队列深度
            )

        # 显示刷新定时器（每2秒刷新一次）
        self.display_timer = self.create_timer(2.0, self.display_status)

        # 启动时间
        self.start_time = time.time()

        self.get_logger().info('系统健康监控已启动')

    def callback(self, topic_name):
        """记录消息接收时间戳（不反序列化消息内容）"""
        self.timestamps[topic_name].append(time.time())

    def calculate_frequency(self, topic_name):
        """计算话题的实时频率"""
        timestamps = self.timestamps[topic_name]

        if len(timestamps) < 2:
            return 0.0

        # 只使用最近2秒内的数据
        current_time = time.time()
        recent_timestamps = [t for t in timestamps if current_time - t <= 2.0]

        if len(recent_timestamps) < 2:
            return 0.0

        # 计算频率：消息数量 / 时间跨度
        time_span = recent_timestamps[-1] - recent_timestamps[0]
        if time_span > 0:
            return (len(recent_timestamps) - 1) / time_span
        return 0.0

    def get_status_symbol(self, freq, expected_range):
        """根据频率返回状态符号"""
        if freq == 0:
            return '❌'
        elif expected_range[0] <= freq <= expected_range[1]:
            return '✅'
        else:
            return '⚠️'

    def display_status(self):
        """面板化显示系统状态"""
        # 清屏
        os.system('clear' if os.name == 'posix' else 'cls')

        # 运行时长
        uptime = int(time.time() - self.start_time)
        uptime_str = f"{uptime // 60}分{uptime % 60}秒"

        # 打印标题
        print("=" * 100)
        print(f"VIST系统健康监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 运行时长: {uptime_str}")
        print("=" * 100)
        print()

        # 打印表头
        print(f"{'状态':<4} {'话题名称':<45} {'显示名称':<20} {'实时频率':<12} {'预期范围':<15}")
        print("-" * 100)

        # 打印每个话题的状态
        for topic, (_, display_name, expected_range) in self.topics.items():
            freq = self.calculate_frequency(topic)
            status = self.get_status_symbol(freq, expected_range)

            # 格式化频率显示
            if freq == 0:
                freq_str = "0.0 Hz [WARNING: NO DATA]"
                freq_color = "\033[91m"  # 红色
            elif expected_range[0] <= freq <= expected_range[1]:
                freq_str = f"{freq:.1f} Hz"
                freq_color = "\033[92m"  # 绿色
            else:
                freq_str = f"{freq:.1f} Hz [异常]"
                freq_color = "\033[93m"  # 黄色

            reset_color = "\033[0m"

            expected_str = f"{expected_range[0]}-{expected_range[1]} Hz"

            print(f"{status:<4} {topic:<45} {display_name:<20} {freq_color}{freq_str:<12}{reset_color} {expected_str:<15}")

        print("-" * 100)
        print()

        # 打印统计信息
        total_topics = len(self.topics)
        active_topics = sum(1 for topic in self.topics.keys() if self.calculate_frequency(topic) > 0)
        normal_topics = sum(
            1 for topic, (_, _, expected_range) in self.topics.items()
            if expected_range[0] <= self.calculate_frequency(topic) <= expected_range[1]
        )

        print(f"📊 统计: 总话题数 {total_topics} | 活跃话题 {active_topics} | 正常话题 {normal_topics}")
        print()

        # 打印图例
        print("图例: ✅ 正常 | ⚠️ 频率异常 | ❌ 无数据")
        print()
        print("按 Ctrl+C 停止监控")
        print("=" * 100)


def main():
    # 检查ROS2环境
    if 'ROS_DISTRO' not in os.environ:
        print("错误: 未检测到ROS2环境，请先source ROS2工作空间")
        print("例如: source /opt/ros/humble/setup.bash")
        sys.exit(1)

    rclpy.init()

    try:
        monitor = SystemHealthMonitor()

        # 初始提示
        print("正在启动系统健康监控...")
        print("等待2秒后开始显示数据...")
        time.sleep(2)

        rclpy.spin(monitor)
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()