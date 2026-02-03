import time
import yaml
import numpy as np
from abc import ABC, abstractmethod

class BaseHandDriver(ABC):
    """灵巧手驱动抽象基类"""
    @abstractmethod
    def send_hand_cmd(self, joint_angles):
        """发送关节角度 (弧度)"""
        pass

class MockHandDriver(BaseHandDriver):
    """调试用的虚拟灵巧手"""
    def __init__(self):
        print("🖐️ [HandDriver] Started in MOCK mode.")

    def send_hand_cmd(self, joint_angles):
        # 仅仅打印，不发送
        # print(f"[MockHand] Cmd: {np.round(joint_angles, 2)}")
        pass

class RealHandDriver(BaseHandDriver):
    """真机驱动 (例如因时/强脑/自研)"""
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
        
        self.port = self.cfg['hardware']['serial_port']
        self.mapping = self.cfg['mapping']
        
        # TODO: 初始化串口
        # import serial
        # self.ser = serial.Serial(self.port, ...)
        print(f"🖐️ [HandDriver] Connecting to real hand at {self.port}...")

    def _rad_to_raw(self, rad, finger_name):
        """将弧度映射为电机原始值"""
        r_range = self.mapping[finger_name]['rad']
        h_range = self.mapping[finger_name]['raw']
        # 线性插值
        return np.interp(rad, r_range, h_range)

    def send_hand_cmd(self, joint_angles):
        """
        输入: joint_angles (字典或列表，对应各个手指弧度)
        """
        # TODO: 1. 遍历手指进行映射
        # raw_val = self._rad_to_raw(joint_angles['index'], 'index')
        
        # TODO: 2. 拼装协议包 (Protocol)
        # packet = bytearray([...])
        
        # TODO: 3. 发送串口指令
        # self.ser.write(packet)
        pass