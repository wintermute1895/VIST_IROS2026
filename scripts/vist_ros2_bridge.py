#!/usr/bin/env python3
"""
VIST ROS2 桥接节点
将Python VIST算法输出转换为ROS2消息，实现硬件无关的控制架构

架构流程：
视觉输入 → VIST算法 → 本节点(ROS2发布) → high_freq_resampler → ROS2驱动 → 机器人

功能：
1. 接收视觉输入（UDP或其他方式）
2. 运行VIST算法计算关节角度
3. 发布sensor_msgs/JointState到ROS2话题
4. 支持左右双臂独立控制

Author: VIST Project
Date: 2026-02-23
"""

import os
import sys
import time
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.control.vist_controller import VISTController
from src.communication.vision_udp_receiver import VisionUDPReceiver


class VISTRos2Bridge(Node):
    """VIST到ROS2的桥接节点"""

    def __init__(self):
        super().__init__('vist_ros2_bridge')

        print("=" * 80)
        print("🌉 VIST ROS2 桥接节点")
        print("=" * 80)

        # 1. 加载配置
        print("\n📁 加载系统配置...")
        self.config = get_config()
        print("✅ 配置加载完成")

        # 2. 初始化VIST控制器（算法层）
        print("\n🧠 初始化VIST控制器...")
        self.controller = VISTController(self.config)
        print("✅ VIST控制器初始化完成")

        # 2.5 初始化UDP接收器
        print("\n📡 初始化UDP接收器...")
        udp_ip = self.config.udp_ip if hasattr(self.config, 'udp_ip') else "127.0.0.1"
        udp_port = self.config.udp_port if hasattr(self.config, 'udp_port') else 5005
        self.udp_receiver = VisionUDPReceiver(udp_ip=udp_ip, udp_port=udp_port)
        self.udp_receiver.start()
        print(f"✅ UDP接收器初始化完成 ({udp_ip}:{udp_port})")

        # 3. 声明ROS2参数
        # 注意：使用vision专用话题，避免与外骨骼冲突
        self.declare_parameter('left_topic', '/vision_left_joint_control')
        self.declare_parameter('right_topic', '/vision_right_joint_control')
        self.declare_parameter('publish_rate', 30.0)  # 发布频率 Hz
        self.declare_parameter('output_in_degrees', True)  # 输出单位（度/弧度）

        # 4. 获取参数
        self.left_topic = self.get_parameter('left_topic').value
        self.right_topic = self.get_parameter('right_topic').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.output_in_degrees = self.get_parameter('output_in_degrees').value

        # 5. 创建发布器
        self.left_pub = self.create_publisher(JointState, self.left_topic, 10)
        self.right_pub = self.create_publisher(JointState, self.right_topic, 10)

        # 6. 创建定时器（按配置的频率发布）
        timer_period = 1.0 / self.publish_rate
        self.timer = self.create_timer(timer_period, self.timer_callback)

        # 7. 统计信息
        self.publish_count = 0
        self.start_time = time.time()

        print(f"\n✅ ROS2桥接节点初始化完成")
        print(f"   左臂话题: {self.left_topic}")
        print(f"   右臂话题: {self.right_topic}")
        print(f"   发布频率: {self.publish_rate} Hz")
        print(f"   输出单位: {'度' if self.output_in_degrees else '弧度'}")
        print("=" * 80)

    def timer_callback(self):
        """定时器回调：运行VIST算法并发布结果"""
        try:
            # 1. 获取视觉输入（这里需要根据实际情况修改）
            # TODO: 从UDP接收器或其他数据源获取视觉数据
            vision_data = self.get_vision_data()
            if vision_data is None:
                if self.publish_count % 30 == 0:  # 每秒打印一次（30Hz）
                    self.get_logger().debug("vision_data is None")
                return

            # 2. 运行VIST算法
            result = self.controller.process(vision_data)
            if result is None:
                if self.publish_count % 30 == 0:
                    self.get_logger().debug("controller.process() returned None")
                return

            # VISTController.process() 返回 (q_safe, success, debug_info)
            q_target, success, debug_info = result
            if not success:
                if self.publish_count % 30 == 0:
                    self.get_logger().warn(f"controller.process() returned success=False: {debug_info.get('error', 'unknown')}")
                return

            # 3. 转换单位（如果需要）
            if self.output_in_degrees:
                q_target = np.rad2deg(q_target)

            # 4. 发布ROS2消息
            self.publish_joint_state(q_target)

            self.publish_count += 1
            if self.publish_count % 30 == 0:  # 每秒打印一次
                self.get_logger().info(f"Published {self.publish_count} messages")

        except Exception as e:
            self.get_logger().error(f"定时器回调错误: {e}")

    def get_vision_data(self):
        """
        获取视觉输入数据

        从UDP接收器获取最新的视觉数据

        Returns:
            dict: 视觉数据字典，包含手腕、肘部等位置信息
        """
        # 从UDP接收器获取最新数据（最多0.1秒旧）
        packet = self.udp_receiver.get_latest_data(max_age=0.1)

        if packet is None:
            return None

        # 提取关键点数据
        keypoints = packet.get('keypoints', {})
        if not keypoints:
            return None

        # 转换为VIST控制器需要的格式
        # vision_node_depth.py输出的是肩膀坐标系：X=up, Y=right, Z=forward
        # 注意：motion_mapper期望的key名称是'shoulder', 'elbow', 'wrist'等（不带_pos后缀）
        vision_data = {
            'wrist': keypoints.get('wrist', [0, 0, 0]),
            'elbow': keypoints.get('elbow', [0, 0, 0]),
            'shoulder': keypoints.get('shoulder', [0, 0, 0]),
            'index_mcp': keypoints.get('index_mcp', [0, 0, 0]),
            'pinky_mcp': keypoints.get('pinky_mcp', [0, 0, 0]),
            'timestamp': packet.get('timestamp', time.time())
        }

        return vision_data

    def publish_joint_state(self, q_target):
        """
        发布关节状态到ROS2话题

        Args:
            q_target: 目标关节角度数组
        """
        # 创建JointState消息
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        # 填充关节角度
        # q_target已经是受控关节的角度数组，直接使用即可
        msg.position = [float(q) for q in q_target]

        # 关节名称（使用实际的关节名称）
        controlled_indices = self.controller.ik_solver.controlled_indices
        msg.name = [f"joint_{i}" for i in controlled_indices]

        # 发布消息
        # TODO: 区分左右臂（目前假设只有右臂）
        self.right_pub.publish(msg)

        # 日志（限流）
        if self.publish_count % 100 == 0:
            elapsed = time.time() - self.start_time
            rate = self.publish_count / elapsed if elapsed > 0 else 0
            self.get_logger().info(
                f"已发布 {self.publish_count} 条消息 "
                f"(实际频率: {rate:.1f} Hz)"
            )

    def shutdown(self):
        """关闭节点"""
        print("\n" + "=" * 80)
        print("🛑 关闭VIST ROS2桥接节点")

        # 停止UDP接收器
        if hasattr(self, 'udp_receiver'):
            self.udp_receiver.stop()

        elapsed = time.time() - self.start_time
        rate = self.publish_count / elapsed if elapsed > 0 else 0
        print(f"   总发布消息数: {self.publish_count}")
        print(f"   运行时长: {elapsed:.1f} 秒")
        print(f"   平均频率: {rate:.1f} Hz")
        print("=" * 80)


def main(args=None):
    """主函数"""
    rclpy.init(args=args)

    try:
        node = VISTRos2Bridge()
        print("\n🚀 VIST ROS2桥接节点运行中...")
        print("   按 Ctrl+C 停止\n")

        rclpy.spin(node)

    except KeyboardInterrupt:
        print("\n⚠️ 收到中断信号")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'node' in locals():
            node.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
