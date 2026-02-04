#!/usr/bin/env python3
"""
LinkerHand 灵巧手驱动模块
整合 MediaPipe 关键点 → Dex-Retargeting → LinkerHand SDK 的完整流程
"""

import sys
import os
import time
import yaml
import numpy as np
from abc import ABC, abstractmethod

# 添加项目根目录到路径（用于导入 src 模块）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 添加 LinkerHand SDK 到路径
SDK_PATH = os.path.join(os.path.dirname(__file__), "sdk/linkerhand-python-sdk-main")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

# 导入 LinkerHand SDK
try:
    from LinkerHand.linker_hand_api import LinkerHandApi
    LINKERHAND_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  [HandDriver] LinkerHand SDK not available: {e}")
    LINKERHAND_AVAILABLE = False

# 导入 Dex-Retargeting
try:
    from src.core.linker_hand_retargeter import LinkerHandRetargeter
    DEX_RETARGETING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  [HandDriver] Dex-Retargeting not available: {e}")
    DEX_RETARGETING_AVAILABLE = False


class BaseHandDriver(ABC):
    """灵巧手驱动抽象基类"""

    @abstractmethod
    def process_keypoints(self, keypoints):
        """
        处理 MediaPipe 关键点并发送到灵巧手

        Args:
            keypoints: numpy array, shape (21, 3), MediaPipe 手部关键点
        """
        pass

    @abstractmethod
    def send_joint_angles(self, joint_angles_dict):
        """
        发送关节角度（弧度）到灵巧手

        Args:
            joint_angles_dict: dict, 关节名称到弧度值的映射
        """
        pass


class MockHandDriver(BaseHandDriver):
    """调试用的虚拟灵巧手"""

    def __init__(self):
        print("🖐️  [HandDriver] Started in MOCK mode.")

    def process_keypoints(self, keypoints):
        """模拟处理关键点"""
        pass

    def send_joint_angles(self, joint_angles_dict):
        """模拟发送关节角度"""
        # print(f"[MockHand] Joint angles: {joint_angles_dict}")
        pass


class LinkerHandDriver(BaseHandDriver):
    """
    LinkerHand 完整驱动类

    功能流程：
    1. 接收 MediaPipe 21 个手部关键点 (21x3)
    2. 使用 Dex-Retargeting 映射到机器人关节空间（弧度）
    3. 将弧度值映射到 LinkerHand 的 0-255 范围
    4. 通过 LinkerHand SDK 发送到真机
    """

    def __init__(self, config_path, project_root=None):
        """
        初始化 LinkerHand 驱动

        Args:
            config_path: str, 配置文件路径（hand_retargeting_config.yaml）
            project_root: str, 项目根目录路径（用于解析相对路径）
        """
        print(f"🚀 [LinkerHandDriver] Initializing...")

        # 设置项目根目录
        if project_root is None:
            # 默认为当前文件的上上级目录
            self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.project_root = project_root

        # 加载配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 1. 初始化 Dex-Retargeting
        self._init_retargeting()

        # 2. 初始化 LinkerHand SDK
        self._init_linkerhand()

        # 3. 加载关节映射配置
        self.joint_mapping = self.config['joint_mapping']

        # L10 的关节顺序（LinkerHand SDK 期望的顺序）
        self.l10_joint_order = [
            "thumb_cmc_pitch",      # 0
            "thumb_cmc_yaw",        # 1
            "index_mcp_pitch",      # 2
            "middle_mcp_pitch",     # 3
            "ring_mcp_pitch",       # 4
            "pinky_mcp_pitch",      # 5
            "index_mcp_roll",       # 6 (URDF 中使用 roll)
            "ring_mcp_roll",        # 7 (URDF 中使用 roll)
            "pinky_mcp_roll",       # 8 (URDF 中使用 roll)
            "thumb_cmc_roll"        # 9 (拇指的 roll 关节)
        ]

        print("✅ [LinkerHandDriver] Initialization complete!")

    def _init_retargeting(self):
        """初始化 Dex-Retargeting"""
        if not DEX_RETARGETING_AVAILABLE:
            raise ImportError("Dex-Retargeting is not available. Please install it first.")

        print("  📐 [LinkerHandDriver] Initializing Dex-Retargeting...")

        # 创建临时配置文件（LinkerHandRetargeter 需要的格式）
        temp_config = {
            'retargeting': self.config['retargeting']
        }

        # 保存临时配置
        temp_config_path = "/tmp/temp_retargeting_config.yaml"
        with open(temp_config_path, 'w') as f:
            yaml.dump(temp_config, f)

        # 初始化 LinkerHandRetargeter（配置14个，提取10个）
        self.retargeting_controller = LinkerHandRetargeter(
            config_path=temp_config_path,
            project_root=self.project_root
        )

        print("  ✅ [LinkerHandDriver] Dex-Retargeting initialized")

    def _init_linkerhand(self):
        """初始化 LinkerHand SDK"""
        if not LINKERHAND_AVAILABLE:
            raise ImportError("LinkerHand SDK is not available. Please check the SDK path.")

        print("  🤖 [LinkerHandDriver] Initializing LinkerHand SDK...")

        lh_config = self.config['linkerhand']

        # 初始化 LinkerHand API
        self.linkerhand = LinkerHandApi(
            hand_type=lh_config['hand_type'],
            hand_joint=lh_config['hand_joint'],
            can=lh_config['can']
        )

        # 设置速度和扭矩
        self.linkerhand.set_speed(speed=lh_config['speed'])
        self.linkerhand.set_torque(torque=lh_config['torque'])

        # 禁用碰撞检测（如果配置中指定）
        if 'collision_detection' in lh_config and not lh_config['collision_detection']:
            print("  ⚠️  [LinkerHandDriver] Disabling collision detection...")
            # 尝试禁用碰撞检测
            # 注意：LinkerHand SDK 可能没有直接的碰撞检测开关
            # 如果 SDK 有相关方法，在这里调用
            if hasattr(self.linkerhand, 'set_collision_detection'):
                self.linkerhand.set_collision_detection(False)
            elif hasattr(self.linkerhand, 'disable_collision_detection'):
                self.linkerhand.disable_collision_detection()
            else:
                print("  ℹ️  [LinkerHandDriver] SDK does not support collision detection control")

        print(f"  ✅ [LinkerHandDriver] LinkerHand SDK initialized ({lh_config['hand_type']} {lh_config['hand_joint']})")
        print(f"  ⚙️  [LinkerHandDriver] Speed: {lh_config['speed']}")
        print(f"  ⚙️  [LinkerHandDriver] Torque: {lh_config['torque']}")

    def process_keypoints(self, keypoints):
        """
        处理 MediaPipe 关键点并发送到灵巧手

        Args:
            keypoints: numpy array, shape (21, 3), MediaPipe 手部关键点
        """
        # 1. 使用 Dex-Retargeting 映射到关节空间
        # LinkerHandRetargeter.process() 返回 10 维 numpy 数组（按 SDK 顺序）
        active_qpos = self.retargeting_controller.process(keypoints)

        # 2. 转换为关节字典格式（用于映射到原始值）
        joint_angles_dict = dict(zip(self.l10_joint_order, active_qpos))

        # 3. 发送到灵巧手
        self.send_joint_angles(joint_angles_dict)

    def send_joint_angles(self, joint_angles_dict):
        """
        发送关节角度（弧度）到灵巧手

        Args:
            joint_angles_dict: dict, 关节名称到弧度值的映射
                例如: {'thumb_cmc_pitch': 0.5, 'index_mcp_pitch': 1.2, ...}
        """
        # 将弧度值映射到 0-255 范围
        raw_values = []

        for joint_name in self.l10_joint_order:
            # 获取关节角度（弧度）
            rad_value = joint_angles_dict.get(joint_name, 0.0)

            # 映射到 0-255 范围
            raw_value = self._rad_to_raw(rad_value, joint_name)
            raw_values.append(raw_value)

        # 发送到 LinkerHand
        self.linkerhand.finger_move(pose=raw_values)

    def _rad_to_raw(self, rad_value, joint_name):
        """
        将弧度值映射到 LinkerHand 的 0-255 原始值

        Args:
            rad_value: float, 关节角度（弧度）
            joint_name: str, 关节名称

        Returns:
            float, 0-255 范围的原始值
        """
        if joint_name not in self.joint_mapping:
            print(f"⚠️  [LinkerHandDriver] Unknown joint: {joint_name}, using default mapping")
            return np.clip(rad_value * 255 / 1.57, 0, 255)

        mapping = self.joint_mapping[joint_name]
        rad_range = mapping['rad_range']
        raw_range = mapping['raw_range']

        # 线性插值
        raw_value = np.interp(rad_value, rad_range, raw_range)

        # 限制在 0-255 范围内
        return float(np.clip(raw_value, 0, 255))

    def get_hand_state(self):
        """获取当前灵巧手状态"""
        return self.linkerhand.get_state()

    def close(self):
        """关闭驱动"""
        print("🛑 [LinkerHandDriver] Closing...")


# 便捷函数：创建驱动实例
def create_hand_driver(mode="mock", config_path=None, project_root=None):
    """
    创建灵巧手驱动实例

    Args:
        mode: str, "mock" 或 "real"
        config_path: str, 配置文件路径（仅 real 模式需要）
        project_root: str, 项目根目录（仅 real 模式需要）

    Returns:
        BaseHandDriver 实例
    """
    if mode == "mock":
        return MockHandDriver()
    elif mode == "real":
        if config_path is None:
            raise ValueError("config_path is required for real mode")
        return LinkerHandDriver(config_path, project_root)
    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    # 测试代码
    print("Testing LinkerHandDriver...")

    # 测试 Mock 模式
    mock_driver = create_hand_driver(mode="mock")
    print("Mock driver created successfully")

    # 测试 Real 模式（需要配置文件）
    # config_path = "config/hand_retargeting_config.yaml"
    # real_driver = create_hand_driver(mode="real", config_path=config_path)
    # print("Real driver created successfully")