#!/usr/bin/env python3
"""
RealSense相机管理器
检测和管理多个RealSense相机
"""

import pyrealsense2 as rs
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RealSenseManager:
    """RealSense相机管理器"""

    def __init__(self):
        # 延迟初始化context，避免在导入时占用设备
        self._context = None
        self.devices = []
        self.pipelines = {}

    @property
    def context(self):
        """延迟初始化context"""
        if self._context is None:
            self._context = rs.context()
        return self._context

    def detect_cameras(self) -> List[Dict]:
        """
        检测所有连接的RealSense相机

        Returns:
            相机信息列表，每个相机包含：
            - serial_number: 序列号
            - name: 相机型号名称
            - firmware_version: 固件版本
            - usb_type: USB类型
            - connected: 是否连接
        """
        cameras = []

        try:
            devices = self.context.query_devices()

            for device in devices:
                try:
                    camera_info = {
                        'serial_number': device.get_info(rs.camera_info.serial_number),
                        'name': device.get_info(rs.camera_info.name),
                        'firmware_version': device.get_info(rs.camera_info.firmware_version),
                        'usb_type': device.get_info(rs.camera_info.usb_type_descriptor),
                        'connected': True
                    }
                    cameras.append(camera_info)
                    logger.info(f"检测到相机: {camera_info['name']} (SN: {camera_info['serial_number']})")
                except Exception as e:
                    logger.error(f"获取相机信息失败: {e}")

        except Exception as e:
            logger.error(f"检测相机失败: {e}")

        return cameras

    def start_camera(self, serial_number: str,
                     width: int = 640,
                     height: int = 480,
                     fps: int = 30) -> bool:
        """
        启动指定相机

        Args:
            serial_number: 相机序列号
            width: 图像宽度
            height: 图像高度
            fps: 帧率

        Returns:
            是否成功启动
        """
        try:
            pipeline = rs.pipeline()
            config = rs.config()

            # 指定相机序列号
            config.enable_device(serial_number)

            # 配置流
            config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
            config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)

            # 启动pipeline
            pipeline.start(config)

            self.pipelines[serial_number] = pipeline
            logger.info(f"相机 {serial_number} 启动成功")
            return True

        except Exception as e:
            logger.error(f"启动相机 {serial_number} 失败: {e}")
            return False

    def stop_camera(self, serial_number: str) -> bool:
        """停止指定相机"""
        try:
            if serial_number in self.pipelines:
                self.pipelines[serial_number].stop()
                del self.pipelines[serial_number]
                logger.info(f"相机 {serial_number} 已停止")
                return True
            return False
        except Exception as e:
            logger.error(f"停止相机 {serial_number} 失败: {e}")
            return False

    def get_frame(self, serial_number: str) -> Optional[tuple]:
        """
        获取指定相机的帧

        Returns:
            (color_image, depth_image) 或 None
        """
        try:
            if serial_number not in self.pipelines:
                return None

            frames = self.pipelines[serial_number].wait_for_frames(timeout_ms=1000)

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if not color_frame or not depth_frame:
                return None

            # 转换为numpy数组
            import numpy as np
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            return (color_image, depth_image)

        except Exception as e:
            logger.error(f"获取相机 {serial_number} 帧失败: {e}")
            return None

    def stop_all(self):
        """停止所有相机"""
        for serial_number in list(self.pipelines.keys()):
            self.stop_camera(serial_number)


# 全局实例
_manager = None

def get_manager() -> RealSenseManager:
    """获取全局RealSense管理器实例"""
    global _manager
    if _manager is None:
        _manager = RealSenseManager()
    return _manager
