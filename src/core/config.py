#!/usr/bin/env python3
"""
============================================================================
LinkerHand L10 配置文件
============================================================================
功能：集中管理所有系统参数
包括：摄像头、视觉控制、硬件驱动、状态机、抓取预设等
============================================================================
"""

from typing import List, Dict
from enum import Enum


class CameraType(Enum):
    """摄像头类型枚举"""
    OPENCV = "opencv"           # 标准OpenCV摄像头
    REALSENSE = "realsense"     # Intel RealSense D435i


class GraspPreset(Enum):
    """抓取预设枚举"""
    SMALL = "small"      # 小物体（如硬币、螺丝）
    MEDIUM = "medium"    # 中等物体（如杯子、瓶子）
    LARGE = "large"      # 大物体（如球、盒子）


# ============================================================================
# 摄像头配置
# ============================================================================

class CameraConfig:
    """摄像头配置"""

    # 摄像头类型选择
    # 可选值: CameraType.OPENCV (标准USB摄像头) 或 CameraType.REALSENSE (Intel RealSense D435i)
    CAMERA_TYPE: CameraType = CameraType.REALSENSE

    # OpenCV摄像头配置
    OPENCV_CAMERA_ID: int = 0              # 摄像头设备ID (默认: 0)
    OPENCV_FRAME_WIDTH: int = 640          # 图像宽度
    OPENCV_FRAME_HEIGHT: int = 480         # 图像高度
    OPENCV_FPS: int = 30                   # 帧率

    # RealSense摄像头配置
    REALSENSE_WIDTH: int = 640             # 图像宽度
    REALSENSE_HEIGHT: int = 480            # 图像高度
    REALSENSE_FPS: int = 30                # 帧率
    REALSENSE_ENABLE_DEPTH: bool = True    # 是否启用深度流
    REALSENSE_ALIGN_TO_COLOR: bool = True  # 将深度对齐到彩色图像


# ============================================================================
# 视觉控制器配置
# ============================================================================

class VisionConfig:
    """视觉控制器配置"""

    # MediaPipe配置
    MIN_DETECTION_CONFIDENCE: float = 0.5
    MIN_TRACKING_CONFIDENCE: float = 0.5

    # 状态机阈值
    RATIO_THRESHOLD_IDLE: float = 0.8      # ratio > 0.8 → IDLE（空闲）
    RATIO_THRESHOLD_GRASP: float = 0.2     # ratio <= 0.2 → GRASP（抓取）
    # 0.2 < ratio <= 0.8 → PRE_GRASP（预抓取）

    # 防抖参数
    DEBOUNCE_FRAMES: int = 5  # 状态切换前需要连续5帧

    # 强制IDLE冷却时间
    FORCE_IDLE_DURATION: int = 30  # 强制IDLE持续30帧


# ============================================================================
# 硬件驱动配置
# ============================================================================

class HardwareConfig:
    """硬件驱动配置"""

    # CAN总线配置
    CAN_ID: int = 0x27                     # CAN设备ID (默认: 0x27)
    CAN_CHANNEL: str = "can0"              # CAN接口名称 (默认: can0)

    # 模拟模式
    MOCK_MODE: bool = False                # 是否在模拟模式下运行（无硬件）

    # 过滤配置
    ENABLE_FILTERING: bool = True          # 启用基于变化的过滤


# ============================================================================
# 控制系统配置
# ============================================================================

class ControlConfig:
    """控制系统配置"""

    # 控制循环频率
    CONTROL_FREQ: int = 30                 # Hz (默认: 30)

    # 显示窗口配置
    WINDOW_NAME: str = 'LinkerHand L10 - 视觉控制'
    WINDOW_WIDTH: int = 640
    WINDOW_HEIGHT: int = 480


# ============================================================================
# 日志配置
# ============================================================================

class LogConfig:
    """日志配置"""

    LOG_LEVEL: str = 'INFO'                # 日志级别: DEBUG, INFO, WARNING, ERROR (默认: INFO)
    LOG_FORMAT: str = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    LOG_DATE_FORMAT: str = '%H:%M:%S'


# ============================================================================
# 关节角度预设配置
# ============================================================================

class JointAnglesConfig:
    """
    关节角度预设配置

    关节顺序：[拇指俯仰, 拇指偏航, 食指俯仰, 中指俯仰,
              无名指俯仰, 小指俯仰, 食指侧摆, 无名指侧摆,
              小指侧摆, 拇指侧摆]
    单位：度（0-255）
    """

    # ========================================================================
    # IDLE状态：手完全张开
    # ========================================================================
    JOINT_ANGLES_IDLE: List[float] = [
        255.0,  # [0] 拇指俯仰 (Thumb_Pitch)
        255.0,  # [1] 拇指偏航 (Thumb_Yaw)
        255.0,  # [2] 食指俯仰 (Index_Pitch)
        255.0,  # [3] 中指俯仰 (Middle_Pitch)
        255.0,  # [4] 无名指俯仰 (Ring_Pitch)
        255.0,  # [5] 小指俯仰 (Pinky_Pitch)
        255.0,  # [6] 食指侧摆 (Index_Roll)
        255.0,  # [7] 无名指侧摆 (Ring_Roll)
        255.0,  # [8] 小指侧摆 (Pinky_Roll)
        255.0,  # [9] 拇指侧摆 (Thumb_Roll)
    ]

    # ========================================================================
    # PRE_GRASP状态：预抓取姿态（部分闭合）
    # ========================================================================
    JOINT_ANGLES_PRE_GRASP: List[float] = [
        188.0,  # [0] 拇指俯仰
        51.0,   # [1] 拇指偏航
        138.0,  # [2] 食指俯仰
        130.0,  # [3] 中指俯仰
        255.0,  # [4] 无名指俯仰
        255.0,  # [5] 小指俯仰
        34.0,   # [6] 食指侧摆
        0.0,    # [7] 无名指侧摆
        0.0,    # [8] 小指侧摆
        194.0,  # [9] 拇指侧摆
    ]

    # ========================================================================
    # GRASP状态：完全捏合/抓取（完全闭合）
    # ========================================================================
    JOINT_ANGLES_GRASP: List[float] = [
        138.0,  # [0] 拇指俯仰
        60.0,   # [1] 拇指偏航
        127.0,  # [2] 食指俯仰
        118.0,  # [3] 中指俯仰
        255.0,  # [4] 无名指俯仰
        255.0,  # [5] 小指俯仰
        0.0,    # [6] 食指侧摆
        0.0,    # [7] 无名指侧摆
        0.0,    # [8] 小指侧摆
        212.0,  # [9] 拇指侧摆
    ]

    # ========================================================================
    # 多物体抓取预设 - 小物体（如硬币、螺丝、小零件）
    # ========================================================================
    GRASP_PRESET_SMALL: Dict[str, List[float]] = {
        'idle': [
            255.0, 255.0, 255.0, 255.0, 255.0,
            255.0, 255.0, 255.0, 255.0, 255.0
        ],
        'pre_grasp': [
            200.0,  # [0] 拇指俯仰 - 稍微弯曲
            80.0,   # [1] 拇指偏航 - 靠近食指
            160.0,  # [2] 食指俯仰 - 轻微弯曲
            160.0,  # [3] 中指俯仰 - 轻微弯曲
            255.0,  # [4] 无名指俯仰 - 保持张开
            255.0,  # [5] 小指俯仰 - 保持张开
            50.0,   # [6] 食指侧摆 - 靠近拇指
            0.0,    # [7] 无名指侧摆
            0.0,    # [8] 小指侧摆
            180.0,  # [9] 拇指侧摆 - 精确定位
        ],
        'grasp': [
            150.0,  # [0] 拇指俯仰 - 完全弯曲
            90.0,   # [1] 拇指偏航 - 紧贴食指
            140.0,  # [2] 食指俯仰 - 完全弯曲
            140.0,  # [3] 中指俯仰 - 完全弯曲
            255.0,  # [4] 无名指俯仰 - 保持张开
            255.0,  # [5] 小指俯仰 - 保持张开
            20.0,   # [6] 食指侧摆 - 紧贴拇指
            0.0,    # [7] 无名指侧摆
            0.0,    # [8] 小指侧摆
            170.0,  # [9] 拇指侧摆 - 精确夹持
        ]
    }

    # ========================================================================
    # 多物体抓取预设 - 中等物体（如杯子、瓶子、手机）
    # ========================================================================
    GRASP_PRESET_MEDIUM: Dict[str, List[float]] = {
        'idle': [
            255.0, 255.0, 255.0, 255.0, 255.0,
            255.0, 255.0, 255.0, 255.0, 255.0
        ],
        'pre_grasp': [
            188.0,  # [0] 拇指俯仰
            51.0,   # [1] 拇指偏航
            138.0,  # [2] 食指俯仰
            130.0,  # [3] 中指俯仰
            255.0,  # [4] 无名指俯仰
            255.0,  # [5] 小指俯仰
            34.0,   # [6] 食指侧摆
            0.0,    # [7] 无名指侧摆
            0.0,    # [8] 小指侧摆
            194.0,  # [9] 拇指侧摆
        ],
        'grasp': [
            138.0,  # [0] 拇指俯仰
            60.0,   # [1] 拇指偏航
            127.0,  # [2] 食指俯仰
            118.0,  # [3] 中指俯仰
            255.0,  # [4] 无名指俯仰
            255.0,  # [5] 小指俯仰
            0.0,    # [6] 食指侧摆
            0.0,    # [7] 无名指侧摆
            0.0,    # [8] 小指侧摆
            212.0,  # [9] 拇指侧摆
        ]
    }

    # ========================================================================
    # 多物体抓取预设 - 大物体（如球、盒子、大瓶子）
    # ========================================================================
    GRASP_PRESET_LARGE: Dict[str, List[float]] = {
        'idle': [
            255.0, 255.0, 255.0, 255.0, 255.0,
            255.0, 255.0, 255.0, 255.0, 255.0
        ],
        'pre_grasp': [
            170.0,  # [0] 拇指俯仰 - 更大开口
            30.0,   # [1] 拇指偏航 - 更宽角度
            120.0,  # [2] 食指俯仰 - 更大弯曲
            115.0,  # [3] 中指俯仰 - 更大弯曲
            200.0,  # [4] 无名指俯仰 - 参与抓取
            200.0,  # [5] 小指俯仰 - 参与抓取
            50.0,   # [6] 食指侧摆 - 更宽展开
            30.0,   # [7] 无名指侧摆 - 参与展开
            30.0,   # [8] 小指侧摆 - 参与展开
            220.0,  # [9] 拇指侧摆 - 更宽角度
        ],
        'grasp': [
            120.0,  # [0] 拇指俯仰 - 完全包裹
            40.0,   # [1] 拇指偏航 - 宽角度夹持
            100.0,  # [2] 食指俯仰 - 完全弯曲
            95.0,   # [3] 中指俯仰 - 完全弯曲
            150.0,  # [4] 无名指俯仰 - 完全弯曲
            150.0,  # [5] 小指俯仰 - 完全弯曲
            10.0,   # [6] 食指侧摆 - 包裹物体
            10.0,   # [7] 无名指侧摆 - 包裹物体
            10.0,   # [8] 小指侧摆 - 包裹物体
            230.0,  # [9] 拇指侧摆 - 稳定夹持
        ]
    }

    # 默认使用的抓取预设
    # 可选值: GraspPreset.SMALL (小物体), GraspPreset.MEDIUM (中等物体), GraspPreset.LARGE (大物体)
    DEFAULT_GRASP_PRESET: GraspPreset = GraspPreset.MEDIUM


# ============================================================================
# 可视化配置
# ============================================================================

class VisualizationConfig:
    """可视化配置"""

    # 信息面板配置
    PANEL_WIDTH: int = 280
    PANEL_ALPHA: float = 0.6  # 半透明度

    # 底部状态栏配置
    BOTTOM_BAR_HEIGHT: int = 70
    BOTTOM_BAR_ALPHA: float = 0.75

    # 中文字体路径（按优先级）
    CHINESE_FONT_PATHS: List[str] = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "C:\\Windows\\Fonts\\msyh.ttc",  # Windows
    ]

    # 字体大小
    FONT_SIZE_TITLE: int = 24
    FONT_SIZE_JOINT: int = 16
    FONT_SIZE_STATUS: int = 32
    FONT_SIZE_STATE: int = 32
    FONT_SIZE_RATIO: int = 28
    FONT_SIZE_DEBOUNCE: int = 24
    FONT_SIZE_STATS: int = 22
    FONT_SIZE_HINT: int = 18


# ============================================================================
# 配置管理器
# ============================================================================

class Config:
    """配置管理器 - 统一访问所有配置"""

    camera = CameraConfig
    vision = VisionConfig
    hardware = HardwareConfig
    control = ControlConfig
    log = LogConfig
    joint_angles = JointAnglesConfig
    visualization = VisualizationConfig

    @classmethod
    def get_grasp_preset(cls, preset: GraspPreset) -> Dict[str, List[float]]:
        """
        获取指定的抓取预设

        参数：
            preset: 抓取预设类型

        返回：
            包含idle、pre_grasp、grasp三个状态的角度字典
        """
        if preset == GraspPreset.SMALL:
            return cls.joint_angles.GRASP_PRESET_SMALL
        elif preset == GraspPreset.MEDIUM:
            return cls.joint_angles.GRASP_PRESET_MEDIUM
        elif preset == GraspPreset.LARGE:
            return cls.joint_angles.GRASP_PRESET_LARGE
        else:
            # 默认返回中等物体预设
            return cls.joint_angles.GRASP_PRESET_MEDIUM

    @classmethod
    def print_config(cls):
        """打印当前配置"""
        print("\n" + "=" * 70)
        print("当前配置:")
        print("=" * 70)
        print(f"摄像头类型: {cls.camera.CAMERA_TYPE.value}")
        print(f"控制频率: {cls.control.CONTROL_FREQ} Hz")
        print(f"CAN ID: 0x{cls.hardware.CAN_ID:02X}")
        print(f"CAN通道: {cls.hardware.CAN_CHANNEL}")
        print(f"模拟模式: {cls.hardware.MOCK_MODE}")
        print(f"默认抓取预设: {cls.joint_angles.DEFAULT_GRASP_PRESET.value}")
        print(f"日志级别: {cls.log.LOG_LEVEL}")
        print("=" * 70 + "\n")
