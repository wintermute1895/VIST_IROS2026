import socket
import json
import numpy as np
import time
from abc import ABC, abstractmethod

class BaseArmDriver(ABC):
    """硬件驱动抽象基类"""
    @abstractmethod
    def get_state(self):
        """返回: timestamp, q_pos (np.array), q_vel (np.array)"""
        pass

    @abstractmethod
    def send_command(self, q_cmd):
        """发送关节位置指令"""
        pass

class UdpArmDriver(BaseArmDriver):
    """
    通用 UDP 驱动 (适用于 VIST 架构的仿真或透传)
    """
    def __init__(self, ip="127.0.0.1", recv_port=6000, send_port=6001, dof=7):
        self.ip = ip
        self.send_port = send_port
        self.dof = dof
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", recv_port))
        self.sock.setblocking(False)
        
        # 缓存状态，防止丢包时读取失败
        self.last_q = np.zeros(dof)
        self.last_v = np.zeros(dof)

    def get_state(self):
        try:
            # 尝试读取最新的包（清空缓冲区，只取最后一个）
            data = None
            while True:
                try:
                    chunk, _ = self.sock.recvfrom(65535)
                    data = chunk
                except BlockingIOError:
                    break
            
            if data:
                parsed = json.loads(data.decode())
                # 假设协议格式: {"joints": {"joint1": 0.1, ...}, "velocities": ...}
                # 这里为了简化，直接假设发来的是列表，实际需根据硬件协议解析
                if "q" in parsed:
                    self.last_q = np.array(parsed["q"])
                if "v" in parsed:
                    self.last_v = np.array(parsed["v"])
                    
        except Exception as e:
            print(f"[Driver] Receive Error: {e}")
            
        return time.time(), self.last_q, self.last_v

    def send_command(self, q_cmd):
        # 确保数据格式安全
        safe_cmd = np.array(q_cmd).flatten().tolist()
        msg = json.dumps({
            "ts": time.time(),
            "cmd_type": "position",
            "q_target": safe_cmd
        })
        self.sock.sendto(msg.encode(), (self.ip, self.send_port))

class MockArmDriver(BaseArmDriver):
    """
    调试用的虚假驱动 (无需真实连接)
    """
    def __init__(self, dof=7):
        self.q = np.zeros(dof)
        self.dof = dof
        print("⚠️ Running in Mock/Simulation Mode")

    def get_state(self):
        # 模拟一点噪声
        noise = np.random.normal(0, 0.0001, self.dof)
        return time.time(), self.q + noise, np.zeros(self.dof)

    def send_command(self, q_cmd):
        # 完美执行
        self.q = np.array(q_cmd)