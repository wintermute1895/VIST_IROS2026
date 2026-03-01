"""
UDP 通信模块
提供 UDP 数据接收和发送功能

更新日期：2026-02-21
"""

import socket
import time
import json
import numpy as np
from typing import Optional, Dict, Any


class UDPReceiver:
    """UDP 数据接收器（JSON 版本）

    特性：
    - JSON 序列化（兼容性好）
    - 包丢失检测（seq + timestamp）
    - 性能统计
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 6001, buffer_size: int = 65536):
        """
        初始化 UDP 接收器

        Args:
            host: 绑定地址
            port: 绑定端口
            buffer_size: 缓冲区大小
        """
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.sock = None

        # 包丢失检测
        self.last_seq = -1
        self.packets_received = 0
        self.packets_lost = 0

        # 延迟统计
        self.latency_samples = []
        self.max_latency_samples = 100

    def connect(self):
        """建立 UDP 连接"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.setblocking(False)
        print(f"✅ [UDPReceiver] 绑定成功: {self.host}:{self.port}")

    def receive(self) -> Optional[Dict[str, Any]]:
        """
        接收数据包

        Returns:
            解析后的数据字典，如果没有数据则返回 None
        """
        if self.sock is None:
            raise RuntimeError("UDP 接收器未连接，请先调用 connect()")

        try:
            data, addr = self.sock.recvfrom(self.buffer_size)

            # 解析 JSON 数据包
            packet = json.loads(data.decode('utf-8'))

            # 检测包丢失
            if 'seq' in packet:
                seq = packet['seq']
                if self.last_seq >= 0:
                    expected_seq = self.last_seq + 1
                    if seq != expected_seq:
                        lost = seq - expected_seq
                        self.packets_lost += lost
                        print(f"⚠️ [UDPReceiver] 检测到丢包: 期望 {expected_seq}, 收到 {seq}, 丢失 {lost} 包")
                self.last_seq = seq

            # 计算延迟
            if 'timestamp' in packet:
                send_time = packet['timestamp']
                recv_time = time.time()
                latency = (recv_time - send_time) * 1000  # ms
                self.latency_samples.append(latency)
                if len(self.latency_samples) > self.max_latency_samples:
                    self.latency_samples.pop(0)

            self.packets_received += 1

            # 兼容新旧格式
            if 'keypoints' in packet:
                return packet
            else:
                # 旧格式：直接返回关键点数据
                return {'keypoints': packet}

        except BlockingIOError:
            # 没有数据可读（非阻塞模式）
            return None
        except Exception as e:
            print(f"⚠️ [UDPReceiver] 接收错误: {e}")
            return None

    def close(self):
        """关闭连接"""
        if self.sock is not None:
            self.sock.close()
            self.sock = None
            print("✅ [UDPReceiver] 连接已关闭")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'packets_received': self.packets_received,
            'packets_lost': self.packets_lost,
            'loss_rate': 0.0,
            'avg_latency_ms': 0.0,
            'max_latency_ms': 0.0
        }

        if self.packets_received > 0:
            total_packets = self.packets_received + self.packets_lost
            stats['loss_rate'] = self.packets_lost / total_packets * 100

        if len(self.latency_samples) > 0:
            stats['avg_latency_ms'] = np.mean(self.latency_samples)
            stats['max_latency_ms'] = np.max(self.latency_samples)

        return stats

    def reset_statistics(self):
        """重置统计信息"""
        self.last_seq = -1
        self.packets_received = 0
        self.packets_lost = 0
        self.latency_samples = []


class UDPSender:
    """UDP 数据发送器（优化版）

    特性：
    - MessagePack 序列化
    - 自动添加 seq + timestamp
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6001):
        """
        初始化 UDP 发送器

        Args:
            host: 目标地址
            port: 目标端口
        """
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = 0

    def send(self, data: Dict[str, Any]):
        """
        发送数据包

        Args:
            data: 要发送的数据字典
        """
        try:
            # 添加序列号和时间戳
            packet = {
                'seq': self.seq,
                'timestamp': time.time(),
                **data
            }
            self.seq += 1

            # 序列化为 JSON
            message = json.dumps(packet).encode('utf-8')

            self.sock.sendto(message, (self.host, self.port))
        except Exception as e:
            print(f"⚠️ [UDPSender] 发送错误: {e}")

    def close(self):
        """关闭连接"""
        self.sock.close()
        print("✅ [UDPSender] 连接已关闭")
