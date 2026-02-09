"""
UDP 通信模块
提供 UDP 数据接收和发送功能
"""

import socket
import json
import numpy as np
from typing import Optional, Dict, Any


class UDPReceiver:
    """UDP 数据接收器"""

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
            packet = json.loads(data.decode('utf-8'))

            # 兼容新旧格式
            if 'keypoints' in packet:
                return packet['keypoints']
            else:
                return packet

        except BlockingIOError:
            # 没有数据可读（非阻塞模式）
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ [UDPReceiver] JSON 解析失败: {e}")
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


class UDPSender:
    """UDP 数据发送器"""

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

    def send(self, data: Dict[str, Any]):
        """
        发送数据包

        Args:
            data: 要发送的数据字典
        """
        try:
            message = json.dumps(data).encode('utf-8')
            self.sock.sendto(message, (self.host, self.port))
        except Exception as e:
            print(f"⚠️ [UDPSender] 发送错误: {e}")

    def close(self):
        """关闭连接"""
        self.sock.close()
        print("✅ [UDPSender] 连接已关闭")
