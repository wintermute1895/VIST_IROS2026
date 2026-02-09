#!/usr/bin/env python3
"""
视觉-控制标准交互协议 (Vision-Control Interface Protocol)

设计目标：
1. 解耦 (Decoupling): 视觉算法可替换，控制模块无需修改
2. 安全性 (Safety): 异常情况可检测，触发急停
3. 可解释性 (Interpretability): 包含调试信息

架构决策：
- 意图因子 α 在控制端计算（需要机器人当前状态）
- 视觉端只提供原始数据和置信度
- 接口层负责数据验证和异常检测
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum
import numpy as np
import time


class TrackingStatus(Enum):
    """追踪状态枚举"""
    TRACKING = "tracking"              # 正常追踪
    LOST = "lost"                      # 目标丢失
    OCCLUDED = "occluded"              # 部分遮挡
    LOW_CONFIDENCE = "low_confidence"  # 低置信度
    INITIALIZING = "initializing"      # 初始化中


@dataclass
class Keypoint3D:
    """
    3D关键点数据结构

    Attributes:
        position: 3D坐标 [x, y, z] (numpy array, 单位: 米)
        confidence: 置信度 [0.0, 1.0]
        visible: 是否可见（未被遮挡）
    """
    position: np.ndarray  # shape: (3,)
    confidence: float     # [0.0, 1.0]
    visible: bool = True

    def __post_init__(self):
        """验证数据有效性"""
        if not isinstance(self.position, np.ndarray):
            self.position = np.array(self.position, dtype=np.float64)

        if self.position.shape != (3,):
            raise ValueError(f"position 必须是 (3,) 形状，当前: {self.position.shape}")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence 必须在 [0, 1]，当前: {self.confidence}")

    def is_valid(self, min_confidence: float = 0.5) -> bool:
        """
        检查关键点是否有效

        Args:
            min_confidence: 最小置信度阈值

        Returns:
            bool: 是否有效
        """
        return (
            self.visible and
            self.confidence >= min_confidence and
            np.all(np.isfinite(self.position))
        )


@dataclass
class VisionPacket:
    """
    视觉数据包 - 视觉模块输出的标准数据格式

    设计原则：
    1. 包含控制所需的所有原始数据
    2. 包含足够的元数据用于安全检查
    3. 不包含控制逻辑（如意图因子 α）

    Attributes:
        # ==================== 核心数据 ====================
        shoulder: 肩部关键点（肩部坐标系原点）
        elbow: 肘部关键点
        wrist: 腕部关键点（末端执行器目标位置）
        index_mcp: 食指掌指关节（用于姿态计算）
        pinky_mcp: 小指掌指关节（用于姿态计算）

        # ==================== 元数据 ====================
        timestamp: 数据采集时间戳（秒，time.time()）
        frame_id: 帧ID（用于调试和日志关联）
        tracking_status: 追踪状态

        # ==================== 调试信息 ====================
        source_algorithm: 视觉算法名称（如 "MediaPipe", "YOLO+DepthAI"）
        processing_time: 视觉处理耗时（秒）
        debug_info: 额外的调试信息字典
    """

    # ==================== 核心数据 ====================
    shoulder: Keypoint3D
    elbow: Keypoint3D
    wrist: Keypoint3D
    index_mcp: Keypoint3D
    pinky_mcp: Keypoint3D

    # ==================== 元数据 ====================
    timestamp: float  # 秒，time.time()
    frame_id: int
    tracking_status: TrackingStatus

    # ==================== 调试信息 ====================
    source_algorithm: str = "Unknown"
    processing_time: float = 0.0  # 秒
    debug_info: Dict = field(default_factory=dict)

    def __post_init__(self):
        """验证数据包完整性"""
        # 确保所有关键点都是 Keypoint3D 实例
        for kp_name in ['shoulder', 'elbow', 'wrist', 'index_mcp', 'pinky_mcp']:
            kp = getattr(self, kp_name)
            if not isinstance(kp, Keypoint3D):
                raise TypeError(f"{kp_name} 必须是 Keypoint3D 实例")

        # 确保 tracking_status 是枚举类型
        if not isinstance(self.tracking_status, TrackingStatus):
            raise TypeError("tracking_status 必须是 TrackingStatus 枚举")

    def get_age(self) -> float:
        """
        获取数据包年龄（当前时间 - 时间戳）

        Returns:
            float: 数据包年龄（秒）
        """
        return time.time() - self.timestamp

    def is_stale(self, max_age: float = 0.1) -> bool:
        """
        检查数据是否陈旧

        Args:
            max_age: 最大允许年龄（秒），默认100ms

        Returns:
            bool: 是否陈旧
        """
        return self.get_age() > max_age

    def is_tracking_valid(self) -> bool:
        """
        检查追踪状态是否有效

        Returns:
            bool: 追踪是否有效
        """
        return self.tracking_status == TrackingStatus.TRACKING

    def get_all_keypoints_valid(self, min_confidence: float = 0.5) -> bool:
        """
        检查所有关键点是否有效

        Args:
            min_confidence: 最小置信度阈值

        Returns:
            bool: 所有关键点是否有效
        """
        keypoints = [self.shoulder, self.elbow, self.wrist,
                    self.index_mcp, self.pinky_mcp]
        return all(kp.is_valid(min_confidence) for kp in keypoints)

    def to_motion_mapper_format(self) -> Dict[str, np.ndarray]:
        """
        转换为 ArmMotionMapper 所需的格式

        Returns:
            Dict: 包含 'shoulder', 'elbow', 'wrist', 'index_mcp', 'pinky_mcp' 的字典
        """
        return {
            'shoulder': self.shoulder.position,
            'elbow': self.elbow.position,
            'wrist': self.wrist.position,
            'index_mcp': self.index_mcp.position,
            'pinky_mcp': self.pinky_mcp.position
        }

    def get_summary(self) -> str:
        """
        获取数据包摘要（用于日志）

        Returns:
            str: 摘要字符串
        """
        return (
            f"VisionPacket(frame={self.frame_id}, "
            f"age={self.get_age()*1000:.1f}ms, "
            f"status={self.tracking_status.value}, "
            f"wrist_conf={self.wrist.confidence:.2f}, "
            f"source={self.source_algorithm})"
        )


# ==========================================
# 辅助函数：快速构建数据包
# ==========================================

def create_vision_packet_from_dict(
    keypoints_dict: Dict[str, np.ndarray],
    confidences: Optional[Dict[str, float]] = None,
    tracking_status: TrackingStatus = TrackingStatus.TRACKING,
    source_algorithm: str = "Unknown",
    frame_id: int = 0
) -> VisionPacket:
    """
    从字典快速构建 VisionPacket

    Args:
        keypoints_dict: 关键点字典，格式: {'shoulder': [x,y,z], ...}
        confidences: 置信度字典（可选），格式: {'shoulder': 0.95, ...}
        tracking_status: 追踪状态
        source_algorithm: 视觉算法名称
        frame_id: 帧ID

    Returns:
        VisionPacket: 构建的数据包
    """
    if confidences is None:
        confidences = {k: 1.0 for k in keypoints_dict.keys()}

    return VisionPacket(
        shoulder=Keypoint3D(keypoints_dict['shoulder'], confidences.get('shoulder', 1.0)),
        elbow=Keypoint3D(keypoints_dict['elbow'], confidences.get('elbow', 1.0)),
        wrist=Keypoint3D(keypoints_dict['wrist'], confidences.get('wrist', 1.0)),
        index_mcp=Keypoint3D(keypoints_dict['index_mcp'], confidences.get('index_mcp', 1.0)),
        pinky_mcp=Keypoint3D(keypoints_dict['pinky_mcp'], confidences.get('pinky_mcp', 1.0)),
        timestamp=time.time(),
        frame_id=frame_id,
        tracking_status=tracking_status,
        source_algorithm=source_algorithm
    )
