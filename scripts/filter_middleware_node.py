#!/usr/bin/env python3
"""
低通滤波中间节点
在遥操臂和机械臂之间添加滤波层

数据流：
linkerta → /right_arm_joint_control → [此节点] → /right_arm_joint_control_filtered

使用方法：
# Baseline（无滤波）：直接使用原始launch
ros2 launch lbot_teleop teleop.launch.py

# Ours（带滤波）：先启动此节点，再启动teleop
python3 filter_middleware_node.py --alpha 0.2
ros2 launch lbot_teleop teleop.launch.py input_topic:=/right_arm_joint_control_filtered
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
import sys
import os
import time
import json
from pathlib import Path

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from src.control.filters import LowPassFilter

class FilterMiddlewareNode(Node):
    def __init__(self, filter_alpha=0.2, enable_logging=True):
        super().__init__('filter_middleware')

        self.filter_alpha = filter_alpha
        self.enable_logging = enable_logging

        # 创建低通滤波器
        self.lpf = LowPassFilter(alpha=filter_alpha, n_dims=7)
        self.initialized = False

        # 订阅原始topic
        self.subscription = self.create_subscription(
            JointState,
            '/right_arm_joint_control',
            self.joint_state_callback,
            10
        )

        # 发布滤波后的topic
        self.publisher = self.create_publisher(
            JointState,
            '/right_arm_joint_control_filtered',
            10
        )

        # 数据记录
        if self.enable_logging:
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.log_file = log_dir / f"filter_middleware_{timestamp}.jsonl"
            self.get_logger().info(f"📝 数据记录: {self.log_file}")

        self.frame_count = 0
        self.start_time = time.time()

        self.get_logger().info("="*60)
        self.get_logger().info("低通滤波中间节点已启动")
        self.get_logger().info(f"滤波参数: alpha={filter_alpha}")
        self.get_logger().info(f"订阅: /right_arm_joint_control")
        self.get_logger().info(f"发布: /right_arm_joint_control_filtered")
        self.get_logger().info("="*60)

    def joint_state_callback(self, msg):
        """处理关节状态消息"""
        try:
            # 提取关节位置
            if len(msg.position) < 7:
                return

            q_raw = np.array(msg.position[:7])

            # 初始化滤波器
            if not self.initialized:
                self.lpf.reset(q_raw)
                self.initialized = True
                self.get_logger().info("✅ 滤波器已初始化")

            # 应用滤波
            q_filtered = self.lpf.update(q_raw)

            # 创建新消息
            filtered_msg = JointState()
            filtered_msg.header = msg.header
            filtered_msg.name = msg.name
            filtered_msg.position = q_filtered.tolist()

            # 发布
            self.publisher.publish(filtered_msg)

            # 记录数据
            if self.enable_logging:
                self._log_data(q_raw, q_filtered)

            self.frame_count += 1
            if self.frame_count % 100 == 0:
                elapsed = time.time() - self.start_time
                freq = self.frame_count / elapsed
                self.get_logger().info(f"帧数: {self.frame_count}, 频率: {freq:.1f} Hz")

        except Exception as e:
            self.get_logger().error(f"Error: {e}")

    def _log_data(self, q_raw, q_filtered):
        """记录数据"""
        diff = np.abs(q_raw - q_filtered)

        log_entry = {
            'timestamp': time.time(),
            'frame': self.frame_count,
            'q_raw': q_raw.tolist(),
            'q_filtered': q_filtered.tolist(),
            'diff_rad': diff.tolist(),
            'diff_deg': np.degrees(diff).tolist(),
            'filter_alpha': self.filter_alpha
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

def main(args=None):
    import argparse

    parser = argparse.ArgumentParser(description='低通滤波中间节点')
    parser.add_argument('--alpha', type=float, default=0.2, help='滤波器参数（0-1）')
    parser.add_argument('--no-log', action='store_true', help='禁用数据记录')

    parsed_args = parser.parse_args()

    rclpy.init(args=args)

    node = FilterMiddlewareNode(
        filter_alpha=parsed_args.alpha,
        enable_logging=not parsed_args.no_log
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("\n用户中断")
        node.get_logger().info(f"共处理 {node.frame_count} 帧数据")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
