#!/usr/bin/env python3
"""
目标感知模块 (Target Perception Module)

功能：
1. 检测目标物体（USB插口）的3D位置
2. 提供目标位置给 VIST 卡尔曼滤波器
3. 支持多种检测方法（视觉标记、深度学习、手动标定）

设计原则：
- 可插拔：支持多种目标检测算法
- 解耦：与人体姿态检测独立
- 实时：低延迟的目标位置更新

与 VIST 的集成：
- 目标位置 → VIST.detect_intent() → 计算意图因子 α
- α → 协方差调度 → 卡尔曼滤波参数调整
- α → 虚拟夹具 → 导纳控制引导
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np
import time


class TargetDetectionResult:
    """
    目标检测结果

    Attributes:
        position: 目标3D位置 [x, y, z] (米，机器人基座坐标系)
        confidence: 检测置信度 [0.0, 1.0]
        timestamp: 检测时间戳
        detected: 是否检测到目标
        debug_info: 调试信息
    """

    def __init__(
        self,
        position: np.ndarray,
        confidence: float = 1.0,
        timestamp: Optional[float] = None,
        detected: bool = True,
        debug_info: dict = None
    ):
        self.position = np.array(position, dtype=np.float64)
        self.confidence = confidence
        self.timestamp = timestamp or time.time()
        self.detected = detected
        self.debug_info = debug_info or {}

    def is_valid(self, min_confidence: float = 0.5) -> bool:
        """检查检测结果是否有效"""
        return (
            self.detected and
            self.confidence >= min_confidence and
            np.all(np.isfinite(self.position))
        )

    def __str__(self) -> str:
        return (
            f"TargetDetection(pos=[{self.position[0]:.3f}, {self.position[1]:.3f}, {self.position[2]:.3f}], "
            f"conf={self.confidence:.2f}, detected={self.detected})"
        )


class ITargetDetector(ABC):
    """
    目标检测器抽象接口

    所有目标检测算法必须实现此接口。
    """

    @abstractmethod
    def initialize(self) -> bool:
        """初始化检测器"""
        pass

    @abstractmethod
    def detect(self) -> Optional[TargetDetectionResult]:
        """
        检测目标位置

        Returns:
            TargetDetectionResult: 检测结果，如果检测失败返回 None
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理资源"""
        pass

    @abstractmethod
    def get_detector_name(self) -> str:
        """获取检测器名称"""
        pass


class ManualTargetDetector(ITargetDetector):
    """
    手动目标检测器

    用于测试和开发，手动指定目标位置。
    """

    def __init__(self, target_position: np.ndarray):
        """
        Args:
            target_position: 目标位置 [x, y, z] (米，机器人基座坐标系)
        """
        self.target_position = np.array(target_position, dtype=np.float64)
        self._initialized = False

    def initialize(self) -> bool:
        print(f"🎯 [ManualTarget] 初始化手动目标检测器")
        print(f"   目标位置: {self.target_position}")
        self._initialized = True
        return True

    def detect(self) -> Optional[TargetDetectionResult]:
        if not self._initialized:
            return None

        return TargetDetectionResult(
            position=self.target_position,
            confidence=1.0,
            detected=True,
            debug_info={'method': 'manual'}
        )

    def cleanup(self) -> None:
        self._initialized = False

    def get_detector_name(self) -> str:
        return "ManualTarget"


class ArUcoTargetDetector(ITargetDetector):
    """
    ArUco 标记目标检测器

    使用 ArUco 标记检测目标位置（适合快速原型）。
    """

    def __init__(self, camera_source=0, marker_id=0, marker_size=0.05):
        """
        Args:
            camera_source: 相机源（0=默认相机，或RealSense）
            marker_id: ArUco 标记ID
            marker_size: 标记尺寸（米）
        """
        self.camera_source = camera_source
        self.marker_id = marker_id
        self.marker_size = marker_size
        self._initialized = False
        self.camera = None
        self.aruco_dict = None
        self.aruco_params = None

    def initialize(self) -> bool:
        print(f"🎯 [ArUcoTarget] 初始化 ArUco 目标检测器")
        try:
            import cv2

            # 初始化 ArUco
            self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            self.aruco_params = cv2.aruco.DetectorParameters_create()

            # 初始化相机
            # TODO: 支持 RealSense
            self.camera = cv2.VideoCapture(self.camera_source)

            self._initialized = True
            print(f"   ✅ ArUco 检测器初始化成功")
            return True

        except Exception as e:
            print(f"   ❌ ArUco 检测器初始化失败: {e}")
            return False

    def detect(self) -> Optional[TargetDetectionResult]:
        if not self._initialized:
            return None

        try:
            import cv2

            # 读取相机帧
            ret, frame = self.camera.read()
            if not ret:
                return None

            # 检测 ArUco 标记
            corners, ids, rejected = cv2.aruco.detectMarkers(
                frame, self.aruco_dict, parameters=self.aruco_params
            )

            if ids is None or self.marker_id not in ids:
                return TargetDetectionResult(
                    position=np.zeros(3),
                    confidence=0.0,
                    detected=False
                )

            # 找到目标标记
            idx = np.where(ids == self.marker_id)[0][0]
            marker_corners = corners[idx][0]

            # TODO: 使用相机内参计算3D位置
            # 这里简化为2D中心点
            center = marker_corners.mean(axis=0)

            # 临时：假设固定深度
            position = np.array([center[0] / 1000, center[1] / 1000, 0.5])

            return TargetDetectionResult(
                position=position,
                confidence=0.9,
                detected=True,
                debug_info={'marker_id': self.marker_id}
            )

        except Exception as e:
            print(f"⚠️ [ArUcoTarget] 检测失败: {e}")
            return None

    def cleanup(self) -> None:
        if self.camera is not None:
            self.camera.release()
        self._initialized = False

    def get_detector_name(self) -> str:
        return "ArUcoTarget"


class YOLOTargetDetector(ITargetDetector):
    """
    YOLO 目标检测器

    使用 YOLO 检测USB插口（需要训练模型）。
    """

    def __init__(self, model_path: str, camera_source=0):
        """
        Args:
            model_path: YOLO 模型路径
            camera_source: 相机源
        """
        self.model_path = model_path
        self.camera_source = camera_source
        self._initialized = False
        self.model = None
        self.camera = None

    def initialize(self) -> bool:
        print(f"🎯 [YOLOTarget] 初始化 YOLO 目标检测器")
        try:
            # TODO: 加载 YOLO 模型
            # from ultralytics import YOLO
            # self.model = YOLO(self.model_path)

            # TODO: 初始化相机
            # self.camera = ...

            self._initialized = True
            print(f"   ✅ YOLO 检测器初始化成功")
            return True

        except Exception as e:
            print(f"   ❌ YOLO 检测器初始化失败: {e}")
            return False

    def detect(self) -> Optional[TargetDetectionResult]:
        if not self._initialized:
            return None

        # TODO: 实现 YOLO 检测
        # 1. 读取相机帧
        # 2. YOLO 推理
        # 3. 提取USB插口位置
        # 4. 深度估计（RealSense）
        # 5. 转换到机器人坐标系

        return None

    def cleanup(self) -> None:
        self._initialized = False

    def get_detector_name(self) -> str:
        return "YOLOTarget"


# ==========================================
# 辅助函数：创建目标检测器
# ==========================================

def create_target_detector(detector_type: str, **kwargs) -> ITargetDetector:
    """
    工厂函数：创建目标检测器

    Args:
        detector_type: 检测器类型 ('manual', 'aruco', 'yolo')
        **kwargs: 检测器参数

    Returns:
        ITargetDetector: 目标检测器实例
    """
    if detector_type == 'manual':
        target_pos = kwargs.get('target_position', [0.3, 0.0, 0.4])
        return ManualTargetDetector(target_pos)

    elif detector_type == 'aruco':
        return ArUcoTargetDetector(
            camera_source=kwargs.get('camera_source', 0),
            marker_id=kwargs.get('marker_id', 0),
            marker_size=kwargs.get('marker_size', 0.05)
        )

    elif detector_type == 'yolo':
        return YOLOTargetDetector(
            model_path=kwargs.get('model_path', 'usb_detector.pt'),
            camera_source=kwargs.get('camera_source', 0)
        )

    else:
        raise ValueError(f"未知的检测器类型: {detector_type}")
