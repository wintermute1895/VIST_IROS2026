#!/usr/bin/env python3
"""
UDP 通信测试脚本
用于验证视觉节点和控制节点之间的 UDP 通信

测试内容：
1. UDP 端口连接测试
2. 数据包格式验证
3. 数据完整性检查
4. 接收延迟测试
5. 数据频率测试

Author: VIST Project
Date: 2026-02-07
"""

import os
import sys
import time
import socket
import json
import numpy as np
from collections import deque

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config


class UDPConnectionTester:
    """UDP 通信测试器"""

    def __init__(self, host="0.0.0.0", port=6001):
        """
        初始化测试器

        Args:
            host: 绑定地址
            port: 绑定端口
        """
        self.host = host
        self.port = port
        self.sock = None

        # 统计数据
        self.packet_count = 0
        self.error_count = 0
        self.latency_samples = deque(maxlen=100)
        self.interval_samples = deque(maxlen=100)
        self.last_receive_time = None

    def connect(self):
        """建立 UDP 连接"""
        print("=" * 80)
        print("📡 UDP 通信测试")
        print("=" * 80)

        print(f"\n🔌 绑定 UDP 端口...")
        print(f"   地址: {self.host}")
        print(f"   端口: {self.port}")

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((self.host, self.port))
            self.sock.setblocking(False)
            print("✅ UDP 端口绑定成功")
            return True
        except Exception as e:
            print(f"❌ UDP 端口绑定失败: {e}")
            return False

    def validate_packet(self, packet):
        """
        验证数据包格式

        Args:
            packet: 解析后的 JSON 数据

        Returns:
            (is_valid, error_msg)
        """
        # 检查是否包含 keypoints
        if 'keypoints' in packet:
            keypoints = packet['keypoints']
        else:
            keypoints = packet

        # 必需的关键点
        required_keys = ['shoulder', 'elbow', 'wrist']

        # 检查关键点是否存在
        for key in required_keys:
            if key not in keypoints:
                return False, f"缺少关键点: {key}"

        # 检查关键点格式（应该是 3D 坐标）
        for key in required_keys:
            kp = keypoints[key]
            if not isinstance(kp, (list, tuple)) or len(kp) != 3:
                return False, f"关键点 {key} 格式错误: {kp}"

            # 检查是否包含 NaN 或 Inf
            if any(np.isnan(v) or np.isinf(v) for v in kp):
                return False, f"关键点 {key} 包含 NaN 或 Inf: {kp}"

        return True, "OK"

    def test_receive(self, duration=10.0, print_interval=1.0):
        """
        测试接收数据

        Args:
            duration: 测试时长（秒）
            print_interval: 打印间隔（秒）
        """
        print(f"\n🧪 开始接收测试（{duration}秒）...")
        print("   提示：确保视觉节点正在运行并发送数据\n")

        start_time = time.time()
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                try:
                    # 接收数据
                    data, addr = self.sock.recvfrom(65536)
                    receive_time = time.time()

                    # 解析 JSON
                    try:
                        packet = json.loads(data.decode('utf-8'))
                    except json.JSONDecodeError as e:
                        self.error_count += 1
                        print(f"❌ JSON 解析错误: {e}")
                        continue

                    # 验证数据包
                    is_valid, error_msg = self.validate_packet(packet)
                    if not is_valid:
                        self.error_count += 1
                        print(f"❌ 数据包验证失败: {error_msg}")
                        continue

                    # 统计
                    self.packet_count += 1

                    # 计算延迟（如果数据包包含时间戳）
                    if 'timestamp' in packet:
                        latency = receive_time - packet['timestamp']
                        self.latency_samples.append(latency * 1000)  # 转换为毫秒

                    # 计算接收间隔
                    if self.last_receive_time is not None:
                        interval = receive_time - self.last_receive_time
                        self.interval_samples.append(interval * 1000)  # 转换为毫秒
                    self.last_receive_time = receive_time

                    # 定期打印统计信息
                    if time.time() - last_print_time >= print_interval:
                        self._print_statistics()
                        last_print_time = time.time()

                except BlockingIOError:
                    # 没有数据，继续等待
                    time.sleep(0.001)
                except Exception as e:
                    self.error_count += 1
                    print(f"❌ 接收错误: {e}")

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")

        # 最终统计
        print("\n" + "=" * 80)
        print("📊 测试结果")
        print("=" * 80)
        self._print_final_statistics()

    def _print_statistics(self):
        """打印实时统计信息"""
        print(f"\r✅ 接收: {self.packet_count} 包 | 错误: {self.error_count} 包", end='')

        if len(self.latency_samples) > 0:
            avg_latency = np.mean(self.latency_samples)
            print(f" | 延迟: {avg_latency:.1f}ms", end='')

        if len(self.interval_samples) > 0:
            avg_interval = np.mean(self.interval_samples)
            frequency = 1000.0 / avg_interval if avg_interval > 0 else 0
            print(f" | 频率: {frequency:.1f}Hz", end='')

    def _print_final_statistics(self):
        """打印最终统计信息"""
        print(f"\n📦 数据包统计:")
        print(f"   总接收: {self.packet_count} 包")
        print(f"   错误: {self.error_count} 包")
        if self.packet_count > 0:
            success_rate = (self.packet_count - self.error_count) / self.packet_count * 100
            print(f"   成功率: {success_rate:.1f}%")

        if len(self.latency_samples) > 0:
            print(f"\n⏱️  延迟统计:")
            print(f"   平均: {np.mean(self.latency_samples):.2f}ms")
            print(f"   最小: {np.min(self.latency_samples):.2f}ms")
            print(f"   最大: {np.max(self.latency_samples):.2f}ms")
            print(f"   标准差: {np.std(self.latency_samples):.2f}ms")

        if len(self.interval_samples) > 0:
            print(f"\n📊 频率统计:")
            avg_interval = np.mean(self.interval_samples)
            frequency = 1000.0 / avg_interval if avg_interval > 0 else 0
            print(f"   平均间隔: {avg_interval:.2f}ms")
            print(f"   平均频率: {frequency:.1f}Hz")
            print(f"   间隔标准差: {np.std(self.interval_samples):.2f}ms")

        # 评估
        print(f"\n✅ 评估:")
        if self.packet_count == 0:
            print("   ❌ 未接收到任何数据包")
            print("   建议：检查视觉节点是否正在运行")
        elif self.error_count > self.packet_count * 0.1:
            print(f"   ⚠️ 错误率较高 ({self.error_count / self.packet_count * 100:.1f}%)")
            print("   建议：检查数据包格式和网络连接")
        else:
            print("   ✅ 通信正常")

        if len(self.latency_samples) > 0:
            avg_latency = np.mean(self.latency_samples)
            if avg_latency > 100:
                print(f"   ⚠️ 延迟较高 ({avg_latency:.1f}ms)")
                print("   建议：检查网络负载和视觉节点性能")
            else:
                print(f"   ✅ 延迟正常 ({avg_latency:.1f}ms)")

        if len(self.interval_samples) > 0:
            frequency = 1000.0 / np.mean(self.interval_samples)
            if frequency < 20:
                print(f"   ⚠️ 频率较低 ({frequency:.1f}Hz)")
                print("   建议：检查视觉节点帧率")
            else:
                print(f"   ✅ 频率正常 ({frequency:.1f}Hz)")

    def close(self):
        """关闭连接"""
        if self.sock is not None:
            self.sock.close()
            print("\n✅ UDP 连接已关闭")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="UDP 通信测试")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="绑定地址")
    parser.add_argument("--port", type=int, default=6001,
                        help="绑定端口")
    parser.add_argument("--duration", type=float, default=10.0,
                        help="测试时长（秒）")

    args = parser.parse_args()

    # 创建测试器
    tester = UDPConnectionTester(host=args.host, port=args.port)

    # 连接
    if not tester.connect():
        return

    # 测试接收
    try:
        tester.test_receive(duration=args.duration)
    finally:
        tester.close()


if __name__ == "__main__":
    main()
