#!/usr/bin/env python3
"""
遥操臂ROS2桥接节点
从sensor_reader读取数据并发布到ROS2

使用方法：
1. 终端1：启动nexus-master
   sudo ./nexus-master --broadcast-ip 192.168.10.255

2. 终端2：启动sensor_reader（管道输出）
   sudo ./sensor_reader -f dynamixel_config.txt | python3 exo_ros2_bridge.py

或者直接运行此脚本，它会自动启动sensor_reader
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import sys
import subprocess
import re
import time

class ExoskeletonBridge(Node):
    def __init__(self):
        super().__init__('exoskeleton_bridge')

        # 创建发布者
        self.publisher = self.create_publisher(
            JointState,
            '/right_arm_joint_control',
            10
        )

        self.get_logger().info("遥操臂ROS2桥接节点已启动")
        self.get_logger().info("发布到: /right_arm_joint_control")

        # 关节名称
        self.joint_names = [f'joint_{i}' for i in range(7)]

    def parse_sensor_line(self, line):
        """
        解析sensor_reader的输出行

        根据手册，输出格式类似：
        Seq: xxx
        14个数据（原始值）
        14个数据（校准后的值）

        我们需要提取校准后的前7个数据（右臂）
        """
        # 尝试提取数字
        numbers = re.findall(r'-?\d+\.?\d*', line)

        if len(numbers) >= 7:
            try:
                # 转换为浮点数（假设是度）
                joint_positions = [float(n) for n in numbers[:7]]
                return joint_positions
            except ValueError:
                return None

        return None

    def publish_joint_state(self, positions):
        """发布关节状态"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        msg.position = positions

        self.publisher.publish(msg)

    def run_from_stdin(self):
        """从标准输入读取数据（管道模式）"""
        self.get_logger().info("从标准输入读取数据...")

        try:
            for line in sys.stdin:
                line = line.strip()

                # 解析数据
                positions = self.parse_sensor_line(line)

                if positions:
                    self.publish_joint_state(positions)

        except KeyboardInterrupt:
            self.get_logger().info("用户中断")

    def run_with_subprocess(self, sensor_reader_path, config_path):
        """启动sensor_reader子进程并读取输出"""
        self.get_logger().info(f"启动sensor_reader: {sensor_reader_path}")

        try:
            # 启动sensor_reader
            process = subprocess.Popen(
                ['sudo', sensor_reader_path, '-f', config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            self.get_logger().info("sensor_reader已启动，开始读取数据...")

            # 读取输出
            for line in process.stdout:
                line = line.strip()

                # 解析数据
                positions = self.parse_sensor_line(line)

                if positions:
                    self.publish_joint_state(positions)

        except KeyboardInterrupt:
            self.get_logger().info("用户中断")
            process.terminate()
        except Exception as e:
            self.get_logger().error(f"错误: {e}")

def main(args=None):
    rclpy.init(args=args)

    node = ExoskeletonBridge()

    # 检查是否从管道读取
    if not sys.stdin.isatty():
        # 管道模式
        node.run_from_stdin()
    else:
        # 独立模式（需要指定sensor_reader路径）
        print("="*60)
        print("遥操臂ROS2桥接节点")
        print("="*60)
        print("\n使用方法：")
        print("1. 管道模式（推荐）：")
        print("   sudo ./sensor_reader -f dynamixel_config.txt | python3 exo_ros2_bridge.py")
        print("\n2. 独立模式：")
        print("   python3 exo_ros2_bridge.py /path/to/sensor_reader /path/to/config.txt")
        print("="*60)

        if len(sys.argv) >= 3:
            sensor_reader_path = sys.argv[1]
            config_path = sys.argv[2]
            node.run_with_subprocess(sensor_reader_path, config_path)
        else:
            print("\n❌ 请提供sensor_reader路径和配置文件路径")
            print("或使用管道模式")

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()