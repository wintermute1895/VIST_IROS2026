"""
机器人接口
封装硬件交互逻辑（UDP 接收 + 真机驱动）
"""

import numpy as np
from src.robot.arm_driver import RealArmDriver
from src.communication.udp_receiver import UDPReceiver


class RobotInterface:
    """机器人接口（硬件交互）"""

    def __init__(self, config):
        """
        初始化机器人接口

        Args:
            config: VISTConfig 配置对象
        """
        self.config = config

        # 1. 初始化真机驱动
        print(f"\n🦾 初始化真机驱动 ({config.hardware_arm_side.upper()} arm)...")
        self.driver = RealArmDriver(
            ip=config.hardware_robot_ip,
            dof=7,
            arm_side=config.hardware_arm_side,
            config=config  # 传递配置对象
        )
        print("✅ 真机驱动初始化完成")

        # 2. 初始化 UDP 接收器
        print("\n📡 设置 UDP 接收...")
        self.udp_receiver = UDPReceiver(
            host=config.udp_host,
            port=config.udp_port,
            buffer_size=config.udp_buffer_size
        )
        print("✅ UDP 接收器初始化完成")

        # 数据超时计数
        self.data_timeout_count = 0
        self.max_data_timeout = config.max_data_timeout

    def connect(self):
        """连接到真机和 UDP"""
        # 连接真机
        print("\n🔌 连接机器人...")
        success = self.driver.connect()
        if not success:
            raise RuntimeError("❌ 连接机器人失败！")
        print("✅ 连接成功")

        # 读取当前状态
        print("\n📊 读取当前关节状态...")
        timestamp, q_pos, q_vel = self.driver.get_state()
        print(f"当前关节角度（度）: {np.round(np.rad2deg(q_pos), 2)}")

        # 连接 UDP
        self.udp_receiver.connect()

        return q_pos

    def receive_keypoints(self):
        """
        接收人体关键点数据

        Returns:
            human_keypoints: 关键点字典，如果没有数据则返回 None
        """
        keypoints = self.udp_receiver.receive()

        if keypoints is None:
            self.data_timeout_count += 1
            if self.data_timeout_count >= self.max_data_timeout:
                print(f"\n⚠️ 超过 {self.max_data_timeout} 帧未收到数据")
                # 发送当前位置（停止运动）
                _, q_current, _ = self.driver.get_state()
                self.driver.send_command(q_current)
                self.data_timeout_count = 0
            return None
        else:
            self.data_timeout_count = 0
            return keypoints

    def send_command(self, q_cmd):
        """
        发送关节角度命令到真机

        Args:
            q_cmd: 关节角度 (7-DoF)
        """
        self.driver.send_command(q_cmd)

    def get_state(self):
        """获取机器人当前状态"""
        return self.driver.get_state()

    def disconnect(self):
        """断开连接"""
        # 停止运动（发送当前位置）
        print("\n🛑 停止运动...")
        try:
            _, q_current, _ = self.driver.get_state()
            self.driver.send_command(q_current)
            import time
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ 发送停止指令失败: {e}")

        # 断开连接
        self.udp_receiver.close()
        self.driver.disconnect()
        print("\n✅ 已断开连接")
