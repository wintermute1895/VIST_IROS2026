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
    def ik_strategy(self):
        """IK 策略类型 ('differential' 或 'pink')"""
        return self._config['control'].get('ik_strategy', 'differential')

    @property
    def ik_gain(self):
        """IK 增益系数"""
        return self._config['control']['ik_gain']

    @property
    def ik_damping(self):
        """IK 阻尼系数"""
        return float(self._config['control'].get('ik_damping', 1e-3))

    @property
    def ik_max_iter(self):
        """IK 最大迭代次数"""
        return int(self._config['control'].get('ik_max_iter', 50))

    @property
    def ik_tolerance(self):
        """IK 收敛阈值（米）"""
        return float(self._config['control'].get('ik_tolerance', 1e-3))

    @property
    def pink_dt(self):
        """Pink 求解器时间步长"""
        return self._config['control'].get('pink_dt', 0.02)

    @property
    def pink_wrist_priority(self):
        """Pink 手腕任务优先级"""
        return self._config['control'].get('pink_wrist_priority', 1.0)

    @property
    def pink_elbow_priority(self):
        """Pink 肘部任务优先级"""
        return self._config['control'].get('pink_elbow_priority', 0.5)

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
    # VIST Kalman Filter 参数
    # ==========================================
    @property
    def vist_enabled(self):
        """VIST 卡尔曼滤波是否启用"""
        return self._config.get('vist_kalman', {}).get('enabled', False)

    @property
    def vist_n_joints(self):
        """VIST 关节数量"""
        return self._config.get('vist_kalman', {}).get('n_joints', 7)

    @property
    def vist_state_dim(self):
        """VIST 状态维度"""
        return self._config.get('vist_kalman', {}).get('state_dim', 14)

    @property
    def vist_process_dt(self):
        """VIST 过程模型时间步长"""
        return float(self._config.get('vist_kalman', {}).get('process_model', {}).get('dt', 0.02))

    @property
    def vist_position_variance(self):
        """VIST 位置方差"""
        return float(self._config.get('vist_kalman', {}).get('process_model', {}).get('position_variance', 1e-4))

    @property
    def vist_velocity_variance(self):
        """VIST 速度方差"""
        return float(self._config.get('vist_kalman', {}).get('process_model', {}).get('velocity_variance', 1e-3))

    @property
    def vist_elbow_joint_indices(self):
        """VIST 肘部关节索引"""
        return self._config.get('vist_kalman', {}).get('process_model', {}).get('elbow_joint_indices', [3])

    @property
    def vist_elbow_damping_factor(self):
        """VIST 肘部阻尼因子"""
        return float(self._config.get('vist_kalman', {}).get('process_model', {}).get('elbow_damping_factor', 0.1))

    @property
    def vist_human_base_variance(self):
        """VIST 人类指令基础方差"""
        return float(self._config.get('vist_kalman', {}).get('observation_model', {}).get('human_base_variance', 1e-2))

    @property
    def vist_human_max_variance(self):
        """VIST 人类指令最大方差"""
        return float(self._config.get('vist_kalman', {}).get('observation_model', {}).get('human_max_variance', 1e-1))

    @property
    def vist_virtual_base_variance(self):
        """VIST 虚拟引导基础方差"""
        return float(self._config.get('vist_kalman', {}).get('observation_model', {}).get('virtual_base_variance', 1e-4))

    @property
    def vist_virtual_min_variance(self):
        """VIST 虚拟引导最小方差"""
        return float(self._config.get('vist_kalman', {}).get('observation_model', {}).get('virtual_min_variance', 1e-5))

    @property
    def vist_differential_ik_damping(self):
        """VIST 微分 IK 阻尼"""
        return float(self._config.get('vist_kalman', {}).get('observation_model', {}).get('differential_ik_damping', 5e-3))

    @property
    def vist_distance_threshold(self):
        """VIST 意图检测距离阈值"""
        return float(self._config.get('vist_kalman', {}).get('intent_detection', {}).get('distance_threshold', 0.1))

    @property
    def vist_velocity_threshold(self):
        """VIST 意图检测速度阈值"""
        return float(self._config.get('vist_kalman', {}).get('intent_detection', {}).get('velocity_threshold', 0.05))

    @property
    def vist_sigmoid_k(self):
        """VIST 意图检测 Sigmoid 陡峭度"""
        return float(self._config.get('vist_kalman', {}).get('intent_detection', {}).get('sigmoid_k', 10.0))

    @property
    def vist_intent_smoothing(self):
        """VIST 意图平滑系数"""
        return float(self._config.get('vist_kalman', {}).get('intent_detection', {}).get('intent_smoothing', 0.9))

    @property
    def vist_initial_state_variance(self):
        """VIST 初始状态方差"""
        return float(self._config.get('vist_kalman', {}).get('initialization', {}).get('initial_state_variance', 1e-2))

    @property
    def vist_initial_velocity_variance(self):
        """VIST 初始速度方差"""
        return float(self._config.get('vist_kalman', {}).get('initialization', {}).get('initial_velocity_variance', 1e-3))

    # ==========================================
    # 滤波参数
    # ==========================================
    @property
    def enable_mapper_filter(self):
        """是否在 Mapper 层启用滤波"""
        return self._config.get('filtering', {}).get('enable_mapper_filter', True)

    @property
    def mapper_filter_type(self):
        """Mapper 滤波器类型 ('ema' 或 'oneeuro')"""
        return self._config.get('filtering', {}).get('mapper_filter_type', 'oneeuro')

    @property
    def ema_alpha(self):
        """EMA 滤波系数"""
        return self._config.get('filtering', {}).get('ema_alpha', 0.5)

    @property
    def oneeuro_min_cutoff(self):
        """One Euro Filter 最小截止频率"""
        return self._config.get('filtering', {}).get('oneeuro_min_cutoff', 0.3)

    @property
    def oneeuro_beta(self):
        """One Euro Filter 速度系数"""
        return self._config.get('filtering', {}).get('oneeuro_beta', 0.005)

    @property
    def oneeuro_d_cutoff(self):
        """One Euro Filter 导数截止频率"""
        return self._config.get('filtering', {}).get('oneeuro_d_cutoff', 1.0)

    @property
    def enable_control_filter(self):
        """是否在控制节点启用滤波"""
        return self._config.get('filtering', {}).get('enable_control_filter', True)

    @property
    def control_filter_type(self):
        """控制节点滤波器类型"""
        return self._config.get('filtering', {}).get('control_filter_type', 'oneeuro')

    # 兼容旧配置（向后兼容）
    @property
    def filter_alpha(self):
        """滤波系数（兼容旧配置）"""
        # 优先使用新配置，如果不存在则使用旧配置
        if 'filtering' in self._config:
            return self.ema_alpha
        return self._config['control'].get('filter_alpha', 0.5)

    @property
    def filter_min_cutoff(self):
        """One Euro Filter 最小截止频率（兼容旧配置）"""
        if 'filtering' in self._config:
            return self.oneeuro_min_cutoff
        return self._config['control'].get('filter_min_cutoff', 0.3)

    @property
    def filter_beta(self):
        """One Euro Filter 速度系数（兼容旧配置）"""
        if 'filtering' in self._config:
            return self.oneeuro_beta
        return self._config['control'].get('filter_beta', 0.005)

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
