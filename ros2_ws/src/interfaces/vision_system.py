#!/usr/bin/env python3
"""
视觉系统抽象接口 (IVisionSystem)

定义视觉模块的标准接口，确保不同视觉算法可以无缝替换。

设计模式：
- 策略模式 (Strategy Pattern): 不同视觉算法作为可替换策略
- 观察者模式 (Observer Pattern): 支持异步数据回调
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable
from src.interfaces.vision_packet import VisionPacket


class IVisionSystem(ABC):
    """
    视觉系统抽象基类

    所有视觉模块（MediaPipe, YOLO, DepthAI等）必须实现此接口。

    生命周期：
    1. initialize() - 初始化硬件和算法
    2. start() - 开始采集数据
    3. get_latest_frame() - 获取最新数据（同步）
    4. stop() - 停止采集
    5. cleanup() - 清理资源
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化视觉系统

        包括：
        - 相机硬件初始化
        - 算法模型加载
        - 参数配置

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    def start(self) -> bool:
        """
        开始数据采集

        启动相机流和处理线程。

        Returns:
            bool: 启动是否成功
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """
        停止数据采集

        停止相机流和处理线程，但不释放资源。

        Returns:
            bool: 停止是否成功
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        清理资源

        释放相机、模型等资源。
        """
        pass

    @abstractmethod
    def get_latest_frame(self, timeout: float = 0.1) -> Optional[VisionPacket]:
        """
        获取最新的视觉数据包（同步接口）

        这是控制模块的主要调用接口。

        Args:
            timeout: 超时时间（秒），如果在此时间内没有新数据，返回 None

        Returns:
            Optional[VisionPacket]: 最新的数据包，如果超时或无数据则返回 None

        注意：
        - 此方法应该是线程安全的
        - 如果视觉系统未启动，返回 None
        - 如果追踪丢失，返回带有 LOST 状态的数据包（而不是 None）
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        检查视觉系统是否正在运行

        Returns:
            bool: 是否正在运行
        """
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """
        获取当前帧率

        Returns:
            float: 帧率（FPS）
        """
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """
        获取视觉算法名称

        Returns:
            str: 算法名称（如 "MediaPipe", "YOLO+DepthAI"）
        """
        pass

    # ==========================================
    # 可选接口：异步回调（高级功能）
    # ==========================================

    def register_callback(self, callback: Callable[[VisionPacket], None]) -> None:
        """
        注册数据回调函数（可选，用于异步架构）

        Args:
            callback: 回调函数，接收 VisionPacket 作为参数

        注意：
        - 默认实现为空（不支持回调）
        - 子类可以选择实现此功能
        """
        pass

    def unregister_callback(self) -> None:
        """
        取消注册回调函数（可选）

        注意：
        - 默认实现为空
        """
        pass


# ==========================================
# 示例：模拟视觉系统（用于测试）
# ==========================================

class MockVisionSystem(IVisionSystem):
    """
    模拟视觉系统（用于测试和开发）

    生成合成的关键点数据，用于在没有真实相机时测试控制模块。
    """

    def __init__(self):
        self._running = False
        self._frame_count = 0

    def initialize(self) -> bool:
        print("🎥 [MockVision] 初始化模拟视觉系统")
        return True

    def start(self) -> bool:
        print("🎥 [MockVision] 启动数据采集")
        self._running = True
        return True

    def stop(self) -> bool:
        print("🎥 [MockVision] 停止数据采集")
        self._running = False
        return True

    def cleanup(self) -> None:
        print("🎥 [MockVision] 清理资源")
        self._running = False

    def get_latest_frame(self, timeout: float = 0.1) -> Optional[VisionPacket]:
        """生成模拟数据"""
        if not self._running:
            return None

        import numpy as np
        import time
        from src.interfaces.vision_packet import (
            VisionPacket, Keypoint3D, TrackingStatus
        )

        # 生成模拟关键点（简单的正弦波运动）
        t = self._frame_count * 0.01
        self._frame_count += 1

        # 肩部坐标系：X=up, Y=right, Z=forward
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([0.0, 0.2 + 0.05 * np.sin(t), 0.3])
        wrist_pos = np.array([0.0, 0.2 + 0.05 * np.sin(t), 0.6])
        index_pos = wrist_pos + np.array([0.0, 0.05, 0.05])
        pinky_pos = wrist_pos + np.array([0.0, -0.05, 0.05])

        packet = VisionPacket(
            shoulder=Keypoint3D(shoulder_pos, confidence=1.0),
            elbow=Keypoint3D(elbow_pos, confidence=0.95),
            wrist=Keypoint3D(wrist_pos, confidence=0.98),
            index_mcp=Keypoint3D(index_pos, confidence=0.90),
            pinky_mcp=Keypoint3D(pinky_pos, confidence=0.90),
            timestamp=time.time(),
            frame_id=self._frame_count,
            tracking_status=TrackingStatus.TRACKING,
            source_algorithm="MockVision",
            processing_time=0.001
        )

        return packet

    def is_running(self) -> bool:
        return self._running

    def get_fps(self) -> float:
        return 30.0  # 模拟30fps

    def get_algorithm_name(self) -> str:
        return "MockVision"
