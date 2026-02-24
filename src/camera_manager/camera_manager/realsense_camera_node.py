#!/usr/bin/env python3
"""
RealSense相机ROS2节点

功能：
1. 连接Intel RealSense相机（D435i, D405等）
2. 发布彩色图像、深度图像、点云到ROS2话题
3. 发布相机内参信息
4. 支持硬件时间戳同步
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, Imu
from std_msgs.msg import Header
from cv_bridge import CvBridge
import pyrealsense2 as rs
import numpy as np
import time


class RealSenseCameraNode(Node):
    def __init__(self):
        super().__init__('realsense_camera_node')

        # 声明参数
        self.declare_parameter('serial_number', '')
        self.declare_parameter('camera_name', 'camera')
        self.declare_parameter('camera_id', 0)

        # 流配置
        self.declare_parameter('color_width', 640)
        self.declare_parameter('color_height', 480)
        self.declare_parameter('color_fps', 30)
        self.declare_parameter('depth_width', 640)
        self.declare_parameter('depth_height', 480)
        self.declare_parameter('depth_fps', 30)

        # 功能开关
        self.declare_parameter('enable_color', True)
        self.declare_parameter('enable_depth', True)
        self.declare_parameter('enable_pointcloud', False)
        self.declare_parameter('enable_imu', False)
        self.declare_parameter('align_depth_to_color', True)

        # 获取参数
        self.serial_number = self.get_parameter('serial_number').value
        self.camera_name = self.get_parameter('camera_name').value
        self.camera_id = self.get_parameter('camera_id').value

        self.color_width = self.get_parameter('color_width').value
        self.color_height = self.get_parameter('color_height').value
        self.color_fps = self.get_parameter('color_fps').value
        self.depth_width = self.get_parameter('depth_width').value
        self.depth_height = self.get_parameter('depth_height').value
        self.depth_fps = self.get_parameter('depth_fps').value

        self.enable_color = self.get_parameter('enable_color').value
        self.enable_depth = self.get_parameter('enable_depth').value
        self.enable_pointcloud = self.get_parameter('enable_pointcloud').value
        self.enable_imu = self.get_parameter('enable_imu').value
        self.align_depth_to_color = self.get_parameter('align_depth_to_color').value

        # CV Bridge
        self.bridge = CvBridge()

        # 创建发布器
        self.color_pub = None
        self.depth_pub = None
        self.color_info_pub = None
        self.depth_info_pub = None
        self.pointcloud_pub = None
        self.imu_pub = None

        if self.enable_color:
            self.color_pub = self.create_publisher(
                Image, f'/{self.camera_name}/color/image_raw', 10)
            self.color_info_pub = self.create_publisher(
                CameraInfo, f'/{self.camera_name}/color/camera_info', 10)

        if self.enable_depth:
            self.depth_pub = self.create_publisher(
                Image, f'/{self.camera_name}/depth/image_raw', 10)
            self.depth_info_pub = self.create_publisher(
                CameraInfo, f'/{self.camera_name}/depth/camera_info', 10)

        if self.enable_pointcloud:
            self.pointcloud_pub = self.create_publisher(
                PointCloud2, f'/{self.camera_name}/depth/points', 10)

        if self.enable_imu:
            self.imu_pub = self.create_publisher(
                Imu, f'/{self.camera_name}/imu', 10)

        # 初始化RealSense
        self.pipeline = None
        self.align = None
        self.pc = None

        self.initialize_camera()

        # 创建定时器（30Hz）
        self.timer = self.create_timer(1.0 / self.color_fps, self.timer_callback)

        self.get_logger().info(f'RealSense相机节点已启动: {self.camera_name}')
        if self.serial_number:
            self.get_logger().info(f'  序列号: {self.serial_number}')
        self.get_logger().info(f'  彩色: {self.color_width}x{self.color_height}@{self.color_fps}fps')
        self.get_logger().info(f'  深度: {self.depth_width}x{self.depth_height}@{self.depth_fps}fps')

    def initialize_camera(self):
        """初始化RealSense相机"""
        try:
            # 创建pipeline
            self.pipeline = rs.pipeline()
            config = rs.config()

            # 如果指定了序列号，使用特定相机
            if self.serial_number:
                config.enable_device(self.serial_number)

            # 配置流
            if self.enable_color:
                config.enable_stream(
                    rs.stream.color,
                    self.color_width,
                    self.color_height,
                    rs.format.bgr8,
                    self.color_fps
                )

            if self.enable_depth:
                config.enable_stream(
                    rs.stream.depth,
                    self.depth_width,
                    self.depth_height,
                    rs.format.z16,
                    self.depth_fps
                )

            if self.enable_imu:
                config.enable_stream(rs.stream.accel)
                config.enable_stream(rs.stream.gyro)

            # 启动pipeline
            profile = self.pipeline.start(config)

            # 获取设备信息
            device = profile.get_device()
            self.get_logger().info(f'已连接设备: {device.get_info(rs.camera_info.name)}')
            self.get_logger().info(f'固件版本: {device.get_info(rs.camera_info.firmware_version)}')
            self.get_logger().info(f'序列号: {device.get_info(rs.camera_info.serial_number)}')

            # 创建对齐对象
            if self.align_depth_to_color and self.enable_depth and self.enable_color:
                self.align = rs.align(rs.stream.color)

            # 创建点云对象
            if self.enable_pointcloud:
                self.pc = rs.pointcloud()

            # 获取相机内参
            if self.enable_color:
                color_profile = profile.get_stream(rs.stream.color)
                self.color_intrinsics = color_profile.as_video_stream_profile().get_intrinsics()

            if self.enable_depth:
                depth_profile = profile.get_stream(rs.stream.depth)
                self.depth_intrinsics = depth_profile.as_video_stream_profile().get_intrinsics()

            self.get_logger().info('相机初始化成功')

        except Exception as e:
            self.get_logger().error(f'相机初始化失败: {e}')
            raise

    def timer_callback(self):
        """定时器回调 - 采集和发布数据"""
        try:
            # 等待帧
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)

            # 对齐深度到彩色（如果启用）
            if self.align:
                frames = self.align.process(frames)

            # 获取时间戳
            timestamp = self.get_clock().now().to_msg()

            # 发布彩色图像
            if self.enable_color and self.color_pub:
                color_frame = frames.get_color_frame()
                if color_frame:
                    self.publish_color_image(color_frame, timestamp)

            # 发布深度图像
            if self.enable_depth and self.depth_pub:
                depth_frame = frames.get_depth_frame()
                if depth_frame:
                    self.publish_depth_image(depth_frame, timestamp)

            # 发布点云
            if self.enable_pointcloud and self.pointcloud_pub:
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()
                if depth_frame and color_frame:
                    self.publish_pointcloud(depth_frame, color_frame, timestamp)

        except Exception as e:
            self.get_logger().warn(f'采集帧失败: {e}')

    def publish_color_image(self, frame, timestamp):
        """发布彩色图像"""
        # 转换为numpy数组
        color_image = np.asanyarray(frame.get_data())

        # 转换为ROS2 Image消息
        msg = self.bridge.cv2_to_imgmsg(color_image, encoding='bgr8')
        msg.header.stamp = timestamp
        msg.header.frame_id = f'{self.camera_name}_color_optical_frame'

        self.color_pub.publish(msg)

        # 发布相机信息
        if self.color_info_pub:
            info_msg = self.create_camera_info_msg(
                self.color_intrinsics, timestamp, f'{self.camera_name}_color_optical_frame'
            )
            self.color_info_pub.publish(info_msg)

    def publish_depth_image(self, frame, timestamp):
        """发布深度图像"""
        # 转换为numpy数组
        depth_image = np.asanyarray(frame.get_data())

        # 转换为ROS2 Image消息
        msg = self.bridge.cv2_to_imgmsg(depth_image, encoding='16UC1')
        msg.header.stamp = timestamp
        msg.header.frame_id = f'{self.camera_name}_depth_optical_frame'

        self.depth_pub.publish(msg)

        # 发布相机信息
        if self.depth_info_pub:
            info_msg = self.create_camera_info_msg(
                self.depth_intrinsics, timestamp, f'{self.camera_name}_depth_optical_frame'
            )
            self.depth_info_pub.publish(info_msg)

    def publish_pointcloud(self, depth_frame, color_frame, timestamp):
        """发布点云"""
        # TODO: 实现点云发布
        # 这需要将深度图像转换为PointCloud2消息
        pass

    def create_camera_info_msg(self, intrinsics, timestamp, frame_id):
        """创建CameraInfo消息"""
        msg = CameraInfo()
        msg.header.stamp = timestamp
        msg.header.frame_id = frame_id

        msg.width = intrinsics.width
        msg.height = intrinsics.height

        # 内参矩阵
        msg.k = [
            intrinsics.fx, 0.0, intrinsics.ppx,
            0.0, intrinsics.fy, intrinsics.ppy,
            0.0, 0.0, 1.0
        ]

        # 畸变系数
        msg.d = list(intrinsics.coeffs)

        # 投影矩阵
        msg.p = [
            intrinsics.fx, 0.0, intrinsics.ppx, 0.0,
            0.0, intrinsics.fy, intrinsics.ppy, 0.0,
            0.0, 0.0, 1.0, 0.0
        ]

        # 畸变模型
        if intrinsics.model == rs.distortion.brown_conrady:
            msg.distortion_model = 'plumb_bob'
        elif intrinsics.model == rs.distortion.kannala_brandt4:
            msg.distortion_model = 'equidistant'
        else:
            msg.distortion_model = 'plumb_bob'

        return msg

    def destroy_node(self):
        """清理资源"""
        if self.pipeline:
            self.pipeline.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RealSenseCameraNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
