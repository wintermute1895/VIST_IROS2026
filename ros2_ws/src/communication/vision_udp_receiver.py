#!/usr/bin/env python3
"""
视觉数据UDP接收器
接收vision_node_depth.py发送的UDP数据包
"""

import socket
import json
import time
import threading
from typing import Optional, Dict
import numpy as np


class VisionUDPReceiver:
    """UDP接收器，接收视觉节点发送的关键点数据"""

    def __init__(self, udp_ip: str = "127.0.0.1", udp_port: int = 5005, timeout: float = 0.1):
        """
        初始化UDP接收器

        Args:
            udp_ip: 监听IP地址
            udp_port: 监听端口
            timeout: 数据超时时间（秒）
        """
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.timeout = timeout

        # 创建UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((udp_ip, udp_port))
        self.sock.settimeout(0.01)  # 非阻塞接收

        # 数据缓存
        self.latest_data = None
        self.latest_timestamp = 0
        self.receive_count = 0

        # 接收线程
        self.running = False
        self.receive_thread = None

        print(f"✅ [UDPReceiver] 监听 {udp_ip}:{udp_port}")

    def start(self):
        """启动接收线程"""
        if self.running:
            return

        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        print(f"🚀 [UDPReceiver] 接收线程已启动")

    def stop(self):
        """停止接收线程"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.sock.close()
        print(f"🛑 [UDPReceiver] 接收线程已停止")

    def _receive_loop(self):
        """接收循环（在独立线程中运行）"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)  # 4KB缓冲区
                packet = json.loads(data.decode('utf-8'))

                # 更新最新数据
                self.latest_data = packet
                self.latest_timestamp = time.time()
                self.receive_count += 1

                # 每100帧打印一次统计
                if self.receive_count % 100 == 0:
                    print(f"📡 [UDPReceiver] 已接收 {self.receive_count} 帧")

            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except json.JSONDecodeError as e:
                print(f"⚠️ [UDPReceiver] JSON解析错误: {e}")
            except Exception as e:
                if self.running:  # 只在运行时报错
                    print(f"⚠️ [UDPReceiver] 接收错误: {e}")

    def get_latest_data(self, max_age: float = None) -> Optional[Dict]:
        """
        获取最新的视觉数据

        Args:
            max_age: 最大数据年龄（秒），超过此时间的数据视为过期

        Returns:
            视觉数据字典，如果无数据或数据过期则返回None
        """
        if self.latest_data is None:
            return None

        # 检查数据是否过期
        if max_age is not None:
            age = time.time() - self.latest_timestamp
            if age > max_age:
                return None

        return self.latest_data

    def is_receiving(self) -> bool:
        """检查是否正在接收数据"""
        if self.latest_data is None:
            return False

        # 如果最近1秒内有数据，认为正在接收
        age = time.time() - self.latest_timestamp
        return age < 1.0

    def get_stats(self) -> Dict:
        """获取接收统计信息"""
        return {
            'receive_count': self.receive_count,
            'is_receiving': self.is_receiving(),
            'latest_timestamp': self.latest_timestamp,
            'data_age': time.time() - self.latest_timestamp if self.latest_data else None
        }


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("UDP接收器测试")
    print("=" * 60)

    receiver = VisionUDPReceiver(udp_ip="127.0.0.1", udp_port=5005)
    receiver.start()

    print("\n等待接收数据...")
    print("请启动 vision_node_depth.py 发送数据")
    print("按 Ctrl+C 停止\n")

    try:
        while True:
            data = receiver.get_latest_data(max_age=0.5)
            if data:
                keypoints = data.get('keypoints', {})
                timestamp = data.get('timestamp', 0)
                print(f"收到数据: timestamp={timestamp:.3f}, 关键点数={len(keypoints)}")

                # 打印手腕坐标
                if 'wrist' in keypoints:
                    wrist = keypoints['wrist']
                    print(f"  手腕: X={wrist[0]:.3f}, Y={wrist[1]:.3f}, Z={wrist[2]:.3f}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n停止接收...")
        receiver.stop()
        print("✅ 测试完成")
