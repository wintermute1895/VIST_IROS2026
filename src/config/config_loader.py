"""
VIST Configuration Loader
统一的配置管理模块
"""

import yaml
import numpy as np
import os
from pathlib import Path


class VISTConfig:
    """VIST 系统配置类"""

    def __init__(self, config_path=None):
        """
        加载配置文件

        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径
        """
        if config_path is None:
            # 默认路径：项目根目录/config/system_config.yaml
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "system_config.yaml"

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        print(f"✅ [Config] 配置文件加载成功: {config_path}")

    # ==========================================
    # 机器人参数
    # ==========================================
    @property
    def robot_shoulder_position(self):
        """机器人肩部位置 [x, y, z]"""
        return np.array(self._config['robot']['shoulder_position'], dtype=np.float64)

    @property
    def robot_arm_lengths(self):
        """机器人臂长 {'upper': float, 'fore': float}"""
        return self._config['robot']['arm_lengths']

    @property
    def robot_joint_limits(self):
        """关节限位 (7, 2) numpy array"""
        return np.array(self._config['robot']['joint_limits'], dtype=np.float64)

    # ==========================================
    # 坐标系转换
    # ==========================================
    @property
    def rotation_matrix(self):
        """坐标转换矩阵 (3, 3) numpy array"""
        return np.array(self._config['coordinate_transform']['rotation_matrix'], dtype=np.float64)

    # ==========================================
    # 控制参数
    # ==========================================
    @property
    def ik_gain(self):
        """IK 增益系数"""
        return self._config['control']['ik_gain']

    @property
    def max_joint_velocity(self):
        """最大关节速度 (rad/s)"""
        return self._config['control']['max_joint_velocity']

    @property
    def max_joint_acceleration(self):
        """最大关节加速度 (rad/s^2)"""
        return self._config['control']['max_joint_acceleration']

    @property
    def control_frequency(self):
        """控制频率 (Hz)"""
        return self._config['control']['frequency']

    @property
    def control_dt(self):
        """控制周期 (seconds)"""
        return self._config['control']['dt']

    @property
    def filter_alpha(self):
        """滤波系数"""
        return self._config['control']['filter_alpha']

    @property
    def filter_min_cutoff(self):
        """One Euro Filter 最小截止频率"""
        return self._config['control']['filter_min_cutoff']

    @property
    def filter_beta(self):
        """One Euro Filter 速度系数"""
        return self._config['control']['filter_beta']

    @property
    def control_duration(self):
        """遥操作时长 (seconds)"""
        return self._config['control']['duration']

    @property
    def wrist_weight(self):
        """手腕权重"""
        return self._config['control']['wrist_weight']

    @property
    def elbow_weight(self):
        """肘部权重"""
        return self._config['control']['elbow_weight']

    # ==========================================
    # 网络参数
    # ==========================================
    @property
    def udp_host(self):
        """UDP 绑定地址"""
        return self._config['network']['udp_host']

    @property
    def udp_ip(self):
        """UDP IP 地址"""
        return self._config['network']['udp_ip']

    @property
    def udp_port(self):
        """UDP 端口"""
        return self._config['network']['udp_port']

    @property
    def udp_buffer_size(self):
        """UDP 缓冲区大小"""
        return self._config['network']['buffer_size']

    # ==========================================
    # 视觉参数
    # ==========================================
    @property
    def vision_width(self):
        """相机宽度"""
        return self._config['vision']['width']

    @property
    def vision_height(self):
        """相机高度"""
        return self._config['vision']['height']

    @property
    def vision_fps(self):
        """相机帧率"""
        return self._config['vision']['fps']

    @property
    def vision_scale(self):
        """坐标缩放"""
        return self._config['vision']['scale']

    @property
    def use_realsense_depth(self):
        """是否使用 RealSense 深度"""
        return self._config['vision']['use_realsense_depth']

    # ==========================================
    # 安全参数
    # ==========================================
    @property
    def max_data_timeout(self):
        """最大数据超时帧数"""
        return self._config['safety']['max_data_timeout']

    @property
    def debug_mode(self):
        """调试模式"""
        return self._config['safety']['debug_mode']

    @property
    def debug_print_interval(self):
        """调试输出间隔（帧数）"""
        return self._config['safety']['debug_print_interval']

    # ==========================================
    # 辅助方法
    # ==========================================
    def print_summary(self):
        """打印配置摘要"""
        print("\n" + "=" * 60)
        print("VIST 系统配置摘要")
        print("=" * 60)
        print(f"\n机器人参数:")
        print(f"  肩部位置: {self.robot_shoulder_position}")
        print(f"  上臂长度: {self.robot_arm_lengths['upper']:.4f}m")
        print(f"  前臂长度: {self.robot_arm_lengths['forearm']:.4f}m")
        print(f"\n控制参数:")
        print(f"  IK 增益: {self.ik_gain}")
        print(f"  最大速度: {self.max_joint_velocity} rad/s")
        print(f"  控制频率: {self.control_frequency} Hz")
        print(f"\n网络参数:")
        print(f"  UDP: {self.udp_ip}:{self.udp_port}")
        print(f"\n坐标转换矩阵:")
        print(self.rotation_matrix)
        print("=" * 60 + "\n")


# 全局配置实例（单例模式）
_global_config = None


def get_config(config_path=None):
    """
    获取全局配置实例（单例模式）

    Args:
        config_path: 配置文件路径，仅在首次调用时有效

    Returns:
        VISTConfig 实例
    """
    global _global_config
    if _global_config is None:
        _global_config = VISTConfig(config_path)
    return _global_config


if __name__ == "__main__":
    # 测试配置加载
    config = get_config()
    config.print_summary()
