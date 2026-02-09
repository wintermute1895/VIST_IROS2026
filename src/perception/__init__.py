"""
VIST 感知模块 (Perception Module)

提供目标检测、意图感知等功能，支持 VIST 精密装配遥操作。

主要组件：
- TargetDetector: 目标检测（USB插口位置）
- IntentDetector: 意图感知（已集成在 VISTKalmanFilter 中）
"""

from src.perception.target_detector import (
    ITargetDetector,
    TargetDetectionResult,
    ManualTargetDetector,
    ArUcoTargetDetector,
    YOLOTargetDetector,
    create_target_detector
)

__all__ = [
    'ITargetDetector',
    'TargetDetectionResult',
    'ManualTargetDetector',
    'ArUcoTargetDetector',
    'YOLOTargetDetector',
    'create_target_detector'
]
