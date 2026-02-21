#!/usr/bin/env python3
"""
============================================================================
摄像头包装器 - 支持OpenCV和Intel RealSense D435i
============================================================================
功能：统一的摄像头接口，支持多种摄像头类型
支持：
- OpenCV标准摄像头（USB摄像头、笔记本摄像头等）
- Intel RealSense D435i（RGB + 深度）
============================================================================
"""

import numpy as np
import cv2
import logging
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from .config import CameraType, CameraConfig


class CameraInterface(ABC):
    """摄像头接口基类"""

    @abstractmethod
    def open(self) -> bool:
        """
        打开摄像头

        返回：
            成功返回True，失败返回False
        """
        pass

    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        读取图像帧

        返回：
            元组包含：
            - success: 是否成功读取
            - color_frame: 彩色图像（BGR格式）
            - depth_frame: 深度图像（如果支持，否则为None）
        """
        pass

    @abstractmethod
    def release(self):
        """释放摄像头资源"""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """
        检查摄像头是否已打开

        返回：
            已打开返回True，否则返回False
        """
        pass


class OpenCVCamera(CameraInterface):
    """OpenCV标准摄像头"""

    def __init__(self, camera_id: int = 0):
        """
        初始化OpenCV摄像头

        参数：
            camera_id: 摄像头设备ID
        """
        self.logger = logging.getLogger(__name__)
        self.camera_id = camera_id
        self.cap = None

    def open(self) -> bool:
        """打开OpenCV摄像头"""
        self.logger.info(f"正在打开OpenCV摄像头 (ID: {self.camera_id})...")

        self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            self.logger.error(f"无法打开摄像头 {self.camera_id}")
            return False

        # 设置摄像头属性
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CameraConfig.OPENCV_FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CameraConfig.OPENCV_FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, CameraConfig.OPENCV_FPS)

        self.logger.info("✅ OpenCV摄像头打开成功")
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """读取OpenCV摄像头图像"""
        if self.cap is None or not self.cap.isOpened():
            return False, None, None

        ret, frame = self.cap.read()
        return ret, frame, None  # OpenCV摄像头不提供深度信息

    def release(self):
        """释放OpenCV摄像头"""
        if self.cap is not None:
            self.cap.release()
            self.logger.info("✅ OpenCV摄像头已释放")

    def is_opened(self) -> bool:
        """检查OpenCV摄像头是否已打开"""
        return self.cap is not None and self.cap.isOpened()


class RealSenseCamera(CameraInterface):
    """Intel RealSense D435i摄像头"""

    def __init__(self):
        """初始化RealSense摄像头"""
        self.logger = logging.getLogger(__name__)
        self.pipeline = None
        self.align = None
        self.config = None

    def open(self) -> bool:
        """打开RealSense摄像头"""
        try:
            import pyrealsense2 as rs

            self.logger.info("正在打开Intel RealSense D435i摄像头...")

            # 创建pipeline
            self.pipeline = rs.pipeline()
            self.config = rs.config()

            # 配置彩色流
            self.config.enable_stream(
                rs.stream.color,
                CameraConfig.REALSENSE_WIDTH,
                CameraConfig.REALSENSE_HEIGHT,
                rs.format.bgr8,
                CameraConfig.REALSENSE_FPS
            )

            # 配置深度流（如果启用）
            if CameraConfig.REALSENSE_ENABLE_DEPTH:
                self.config.enable_stream(
                    rs.stream.depth,
                    CameraConfig.REALSENSE_WIDTH,
                    CameraConfig.REALSENSE_HEIGHT,
                    rs.format.z16,
                    CameraConfig.REALSENSE_FPS
                )

                # 创建对齐对象（将深度对齐到彩色）
                if CameraConfig.REALSENSE_ALIGN_TO_COLOR:
                    self.align = rs.align(rs.stream.color)

            # 启动pipeline
            self.pipeline.start(self.config)

            self.logger.info("✅ RealSense摄像头打开成功")
            self.logger.info(f"  分辨率: {CameraConfig.REALSENSE_WIDTH}x{CameraConfig.REALSENSE_HEIGHT}")
            self.logger.info(f"  帧率: {CameraConfig.REALSENSE_FPS} FPS")
            self.logger.info(f"  深度流: {'启用' if CameraConfig.REALSENSE_ENABLE_DEPTH else '禁用'}")

            return True

        except ImportError:
            self.logger.error("❌ pyrealsense2未安装")
            self.logger.error("安装命令: pip install pyrealsense2")
            return False

        except Exception as e:
            self.logger.error(f"❌ 打开RealSense摄像头失败: {e}")
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """读取RealSense摄像头图像"""
        if self.pipeline is None:
            return False, None, None

        try:
            import pyrealsense2 as rs

            # 等待帧
            frames = self.pipeline.wait_for_frames()

            # 对齐深度到彩色（如果启用）
            if self.align is not None:
                frames = self.align.process(frames)

            # 获取彩色帧
            color_frame = frames.get_color_frame()
            if not color_frame:
                return False, None, None

            # 转换为numpy数组
            color_image = np.asanyarray(color_frame.get_data())

            # 获取深度帧（如果启用）
            depth_image = None
            if CameraConfig.REALSENSE_ENABLE_DEPTH:
                depth_frame = frames.get_depth_frame()
                if depth_frame:
                    depth_image = np.asanyarray(depth_frame.get_data())

            return True, color_image, depth_image

        except Exception as e:
            self.logger.error(f"读取RealSense图像失败: {e}")
            return False, None, None

    def release(self):
        """释放RealSense摄像头"""
        if self.pipeline is not None:
            self.pipeline.stop()
            self.logger.info("✅ RealSense摄像头已释放")

    def is_opened(self) -> bool:
        """检查RealSense摄像头是否已打开"""
        return self.pipeline is not None


class CameraFactory:
    """摄像头工厂类"""

    @staticmethod
    def create_camera(camera_type: CameraType, camera_id: int = 0) -> CameraInterface:
        """
        创建摄像头实例

        参数：
            camera_type: 摄像头类型
            camera_id: OpenCV摄像头ID（仅用于OpenCV类型）

        返回：
            摄像头实例

        异常：
            ValueError: 不支持的摄像头类型
        """
        if camera_type == CameraType.OPENCV:
            return OpenCVCamera(camera_id)
        elif camera_type == CameraType.REALSENSE:
            return RealSenseCamera()
        else:
            raise ValueError(f"不支持的摄像头类型: {camera_type}")
