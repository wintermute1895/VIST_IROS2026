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
from rcl_interfaces.msg import ParameterDescriptor
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, Imu
from std_msgs.msg import Header, Float32MultiArray
from cv_bridge import CvBridge
import pyrealsense2 as rs
import numpy as np
import time
import yaml
import os
import cv2


class RealSenseCameraNode(Node):
    def __init__(self):
        super().__init__('realsense_camera_node')

        # 声明参数（serial_number 支持动态类型，允许整数或字符串）
        self.declare_parameter(
            'serial_number',
            '',
            ParameterDescriptor(dynamic_typing=True)
        )
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
        serial_number_param = self.get_parameter('serial_number').value
        # 将序列号转换为字符串（支持整数或字符串类型）
        self.serial_number = str(serial_number_param) if serial_number_param else ''
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

        # 加载系统配置
        self.system_config = self.load_system_config()

        # 意图计算相关
        self.intent_enabled = self.system_config.get('startup', {}).get('intent_calculation', {}).get('enabled', False)
        self.intent_detector = None
        self.aruco_dict = None
        self.aruco_params = None
        self.hand_offset = np.array([0.0, 0.0, 0.1])
        self.target_position = np.array([0.5, 0.0, 0.3])
        self.prev_hand_pos = None
        self.prev_time = None

        if self.intent_enabled:
            self.get_logger().info('意图计算功能已启用')
            self.initialize_intent_calculation()
        else:
            self.get_logger().info('意图计算功能未启用')

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

        # 意图计算发布器
        self.intent_factors_pub = None
        self.intent_debug_image_pub = None
        if self.intent_enabled:
            self.intent_factors_pub = self.create_publisher(
                Float32MultiArray, '/intent_factors', 10)
            self.intent_debug_image_pub = self.create_publisher(
                Image, '/intent_debug_image', 10)

        # 初始化RealSense
        self.pipeline = None
        self.align = None
        self.pc = None

        self.initialize_camera()

        self.get_logger().info(f'RealSense相机节点已启动: {self.camera_name}')
        if self.serial_number:
            self.get_logger().info(f'  序列号: {self.serial_number}')
        self.get_logger().info(f'  彩色: {self.color_width}x{self.color_height}@{self.color_fps}fps')
        self.get_logger().info(f'  深度: {self.depth_width}x{self.depth_height}@{self.depth_fps}fps')

        # 启动采集循环（在单独的线程中）
        import threading
        self.running = True
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

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

    def capture_loop(self):
        """采集循环 - 持续读取和发布帧"""
        self.get_logger().info('开始采集循环')

        while self.running and rclpy.ok():
            try:
                # 等待帧（使用200ms超时）
                frames = self.pipeline.wait_for_frames(timeout_ms=200)

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

            except RuntimeError as e:
                # 超时是正常的，继续循环
                if 'Timeout' not in str(e):
                    self.get_logger().warn(f'采集帧失败: {e}')
            except Exception as e:
                self.get_logger().error(f'采集循环错误: {e}')
                break

        self.get_logger().info('采集循环结束')

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

        # 意图计算（如果启用）
        if self.intent_enabled:
            self.process_intent_calculation(color_image, timestamp)

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

    def load_system_config(self):
        """加载系统配置文件"""
        try:
            # 尝试多个可能的配置文件路径
            possible_paths = [
                # 开发环境路径
                os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../config/system_config.yaml'),
                # 工作空间根目录
                os.path.expanduser('~/Dev/VIST/config/system_config.yaml'),
                # 相对于当前工作目录
                'config/system_config.yaml',
            ]

            for config_path in possible_paths:
                config_path = os.path.normpath(config_path)
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return yaml.safe_load(f)

            # 如果都找不到，返回空配置
            self.get_logger().warn('未找到配置文件，使用默认配置')
            return {}
        except Exception as e:
            self.get_logger().warn(f'加载配置文件失败: {e}')
            return {}

    def initialize_intent_calculation(self):
        """初始化意图计算"""
        try:
            # 导入意图检测器
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
            from src.core.intent_detector import ContinuousIntentDetector

            # 加载配置
            intent_config = self.system_config.get('startup', {}).get('intent_calculation', {})

            # 初始化ArUco检测器
            aruco_config = intent_config.get('aruco', {})
            dict_type = aruco_config.get('dict_type', 'DICT_4X4_50')
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_type))
            self.aruco_params = cv2.aruco.DetectorParameters()

            # 加载偏移和目标位置
            hand_offset_cfg = intent_config.get('hand_offset', {})
            self.hand_offset = np.array([
                hand_offset_cfg.get('x', 0.0),
                hand_offset_cfg.get('y', 0.0),
                hand_offset_cfg.get('z', 0.1)
            ])

            target_pos_cfg = intent_config.get('target_position', {})
            self.target_position = np.array([
                target_pos_cfg.get('x', 0.5),
                target_pos_cfg.get('y', 0.0),
                target_pos_cfg.get('z', 0.3)
            ])

            # 初始化意图检测器
            self.intent_detector = ContinuousIntentDetector()

            self.get_logger().info('意图计算初始化成功')
            self.get_logger().info(f'  手部偏移: {self.hand_offset}')
            self.get_logger().info(f'  目标位置: {self.target_position}')

        except Exception as e:
            self.get_logger().error(f'意图计算初始化失败: {e}')
            self.intent_enabled = False

    def process_intent_calculation(self, color_image, timestamp):
        """处理意图计算"""
        if not self.intent_enabled or self.intent_detector is None:
            return

        try:
            intent_config = self.system_config.get('startup', {}).get('intent_calculation', {})
            aruco_enabled = intent_config.get('aruco', {}).get('enabled', True)

            hand_pos = None
            velocity = np.zeros(3)
            corners = None
            ids = None

            # 1. 检测ArUco标记（如果启用）
            if aruco_enabled:
                # OpenCV 4.7+ 使用新的API
                try:
                    detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
                    corners, ids, _ = detector.detectMarkers(color_image)
                except AttributeError:
                    # 旧版本OpenCV使用旧API
                    corners, ids, _ = cv2.aruco.detectMarkers(
                        color_image, self.aruco_dict, parameters=self.aruco_params
                    )

                if ids is not None and len(ids) > 0:
                    # 使用第一个检测到的标记
                    marker_corners = corners[0][0]
                    marker_center = marker_corners.mean(axis=0)

                    # 简化：假设标记在图像平面上，使用像素坐标估计3D位置
                    img_h, img_w = color_image.shape[:2]
                    norm_x = (marker_center[0] - img_w/2) / img_w
                    norm_y = (marker_center[1] - img_h/2) / img_h

                    # 估计手部位置（相机坐标系）
                    hand_pos = np.array([norm_x, norm_y, 1.0]) + self.hand_offset

                    # 计算速度
                    current_time = time.time()
                    if self.prev_hand_pos is not None and self.prev_time is not None:
                        dt = current_time - self.prev_time
                        if dt > 0:
                            velocity = (hand_pos - self.prev_hand_pos) / dt

                    self.prev_hand_pos = hand_pos
                    self.prev_time = current_time

            # 2. 计算意图因子（即使没有检测到ArUco也计算）
            if hand_pos is not None:
                # 有手部位置，正常计算
                try:
                    intent_result = self.intent_detector.detect_intent(
                        current_pos=hand_pos,
                        target_pos=self.target_position,
                        velocity=velocity,
                        smooth=True
                    )

                    alpha = intent_result.alpha
                    alpha_geo = intent_result.alpha_geo
                    alpha_vel = intent_result.alpha_vel
                    alpha_dir = intent_result.alpha_dir

                except Exception as e:
                    self.get_logger().warn(f'意图因子计算失败: {e}，使用默认值')
                    alpha = 0.0
                    alpha_geo = 0.0
                    alpha_vel = 1.0
                    alpha_dir = 0.5
            else:
                # 没有手部位置，使用默认值
                alpha = 0.0
                alpha_geo = 0.0
                alpha_vel = 1.0
                alpha_dir = 0.5

            # 3. 发布意图因子（总是发布）
            if self.intent_factors_pub is not None:
                msg = Float32MultiArray()
                msg.data = [alpha, alpha_geo, alpha_vel, alpha_dir]
                self.intent_factors_pub.publish(msg)

            # 4. 绘制调试图像（总是绘制）
            debug_image = color_image.copy()

            # 绘制ArUco标记（如果检测到）
            if aruco_enabled and ids is not None and len(ids) > 0:
                cv2.aruco.drawDetectedMarkers(debug_image, corners, ids)

            # 绘制意图因子
            y_offset = 30
            cv2.putText(debug_image, f"alpha: {alpha:.3f}",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y_offset += 25
            cv2.putText(debug_image, f"alpha_geo: {alpha_geo:.3f}",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            y_offset += 25
            cv2.putText(debug_image, f"alpha_vel: {alpha_vel:.3f}",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            y_offset += 25
            cv2.putText(debug_image, f"alpha_dir: {alpha_dir:.3f}",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # 如果没有检测到ArUco，显示提示
            if aruco_enabled and (ids is None or len(ids) == 0):
                cv2.putText(debug_image, "No ArUco marker detected",
                           (10, debug_image.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (0, 0, 255), 1)

            # 发布调试图像
            if self.intent_debug_image_pub is not None:
                debug_msg = self.bridge.cv2_to_imgmsg(debug_image, encoding='bgr8')
                debug_msg.header.stamp = timestamp
                debug_msg.header.frame_id = f'{self.camera_name}_color_optical_frame'
                self.intent_debug_image_pub.publish(debug_msg)

        except Exception as e:
            self.get_logger().warn(f'意图计算处理失败: {e}')

    def destroy_node(self):
        """清理资源"""
        # 停止采集循环
        self.running = False
        if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)

        # 停止pipeline
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
