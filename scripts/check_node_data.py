#!/usr/bin/env python3
"""
检查现有节点的数据格式

用途：
1. 监听UDP端口，查看纯视觉控制节点输出的数据格式
2. 检查数据是否包含关节角度
3. 确定需要如何转换为FollowJoint消息
"""

import socket
import json
import sys


def check_udp_data(port=5005, timeout=5.0):
    """检查UDP数据格式"""
    print(f"监听UDP端口 {port}...")
    print(f"超时时间: {timeout}秒")
    print("等待数据...\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    sock.settimeout(timeout)

    try:
        data, addr = sock.recvfrom(4096)
        print(f"✓ 接收到数据 (来自 {addr})")
        print(f"  数据大小: {len(data)} 字节")
        print()

        # 尝试解析JSON
        try:
            json_data = json.loads(data.decode('utf-8'))
            print("✓ 数据格式: JSON")
            print()
            print("数据内容:")
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
            print()

            # 检查关键字段
            print("字段检查:")
            if 'joint_angles' in json_data:
                print("  ✓ 包含 joint_angles 字段")
                print(f"    关节数量: {len(json_data['joint_angles'])}")
                print(f"    数据: {json_data['joint_angles']}")
            else:
                print("  ✗ 未找到 joint_angles 字段")
                print(f"  可用字段: {list(json_data.keys())}")

            if 'timestamp' in json_data:
                print(f"  ✓ 包含 timestamp: {json_data['timestamp']}")

            return json_data

        except json.JSONDecodeError:
            print("✗ 数据不是JSON格式")
            print(f"原始数据: {data[:200]}")  # 只显示前200字节
            return None

    except socket.timeout:
        print(f"✗ 超时：{timeout}秒内未接收到数据")
        print()
        print("可能的原因：")
        print("1. 纯视觉控制节点未运行")
        print("2. UDP端口配置不正确")
        print("3. 防火墙阻止了UDP通信")
        return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None

    finally:
        sock.close()


def check_ros2_topic(topic_name, timeout=5.0):
    """检查ROS2话题数据格式"""
    print(f"检查ROS2话题: {topic_name}")
    print(f"超时时间: {timeout}秒")
    print()

    try:
        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import JointState
        from lbot_arm_interfaces.msg import FollowJoint

        rclpy.init()

        class TopicChecker(Node):
            def __init__(self):
                super().__init__('topic_checker')
                self.data_received = False

                # 尝试订阅JointState
                self.sub1 = self.create_subscription(
                    JointState,
                    topic_name,
                    self.joint_state_callback,
                    10
                )

                # 尝试订阅FollowJoint
                self.sub2 = self.create_subscription(
                    FollowJoint,
                    topic_name,
                    self.follow_joint_callback,
                    10
                )

            def joint_state_callback(self, msg):
                print("✓ 接收到 JointState 消息")
                print(f"  关节数量: {len(msg.position)}")
                print(f"  位置: {msg.position[:7] if len(msg.position) >= 7 else msg.position}")
                print(f"  速度: {msg.velocity[:7] if len(msg.velocity) >= 7 else msg.velocity}")
                self.data_received = True

            def follow_joint_callback(self, msg):
                print("✓ 接收到 FollowJoint 消息")
                print(f"  关节数量: {len(msg.joints)}")
                print(f"  关节角度: {msg.joints}")
                self.data_received = True

        node = TopicChecker()

        # 等待数据
        import time
        start_time = time.time()
        while not node.data_received and (time.time() - start_time) < timeout:
            rclpy.spin_once(node, timeout_sec=0.1)

        if not node.data_received:
            print(f"✗ 超时：{timeout}秒内未接收到数据")

        node.destroy_node()
        rclpy.shutdown()

    except ImportError as e:
        print(f"✗ 导入错误: {e}")
        print("请确保已source ROS2环境")


def main():
    print("=" * 60)
    print("VIST 节点数据格式检查工具")
    print("=" * 60)
    print()

    if len(sys.argv) < 2:
        print("用法:")
        print("  检查UDP数据: python3 check_node_data.py udp [port]")
        print("  检查ROS2话题: python3 check_node_data.py ros2 <topic_name>")
        print()
        print("示例:")
        print("  python3 scripts/check_node_data.py udp 5005")
        print("  python3 scripts/check_node_data.py ros2 /left_joint_follow")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'udp':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5005
        data = check_udp_data(port)

        if data:
            print()
            print("=" * 60)
            print("建议的适配器配置:")
            print("=" * 60)
            if 'joint_angles' in data:
                print("✓ 数据格式正确，可以直接使用 VisionToROS2Adapter")
            else:
                print("⚠ 需要修改适配器代码以匹配实际数据格式")
                print(f"  可用字段: {list(data.keys())}")

    elif mode == 'ros2':
        if len(sys.argv) < 3:
            print("错误：请指定话题名称")
            sys.exit(1)
        topic_name = sys.argv[2]
        check_ros2_topic(topic_name)

    else:
        print(f"未知模式: {mode}")
        sys.exit(1)


if __name__ == '__main__':
    main()