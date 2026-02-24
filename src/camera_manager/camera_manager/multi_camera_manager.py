#!/usr/bin/env python3
"""
Multi-camera manager for RealSense cameras.
Manages multiple RealSense cameras (D435i, D405) with proper identification.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Header
import pyrealsense2 as rs
import numpy as np
from cv_bridge import CvBridge
import threading
from typing import Dict, List, Optional


class CameraInstance:
    """Represents a single RealSense camera instance."""

    def __init__(self, serial_number: str, camera_name: str,
                 enable_color: bool = True, enable_depth: bool = True,
                 color_width: int = 640, color_height: int = 480, color_fps: int = 30,
                 depth_width: int = 640, depth_height: int = 480, depth_fps: int = 30):
        self.serial_number = serial_number
        self.camera_name = camera_name
        self.enable_color = enable_color
        self.enable_depth = enable_depth

        # Pipeline and config
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_device(serial_number)

        # Enable streams
        if enable_color:
            self.config.enable_stream(rs.stream.color, color_width, color_height,
                                     rs.format.bgr8, color_fps)
        if enable_depth:
            self.config.enable_stream(rs.stream.depth, depth_width, depth_height,
                                     rs.format.z16, depth_fps)

        self.is_running = False
        self.align = rs.align(rs.stream.color) if enable_depth and enable_color else None

    def start(self):
        """Start the camera pipeline."""
        try:
            self.pipeline.start(self.config)
            self.is_running = True
            return True
        except Exception as e:
            print(f"Failed to start camera {self.camera_name} ({self.serial_number}): {e}")
            return False

    def stop(self):
        """Stop the camera pipeline."""
        if self.is_running:
            self.pipeline.stop()
            self.is_running = False

    def get_frames(self):
        """Get aligned frames from the camera."""
        if not self.is_running:
            return None, None, None

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            timestamp = frames.get_timestamp()

            if self.align:
                frames = self.align.process(frames)

            color_frame = frames.get_color_frame() if self.enable_color else None
            depth_frame = frames.get_depth_frame() if self.enable_depth else None

            return color_frame, depth_frame, timestamp
        except Exception as e:
            print(f"Error getting frames from {self.camera_name}: {e}")
            return None, None, None


class MultiCameraManager(Node):
    """ROS2 node for managing multiple RealSense cameras."""

    def __init__(self):
        super().__init__('multi_camera_manager')

        # Declare parameters
        self.declare_parameter('camera_configs', [])
        self.declare_parameter('publish_rate', 30.0)

        # Get parameters
        camera_configs = self.get_parameter('camera_configs').value
        self.publish_rate = self.get_parameter('publish_rate').value

        # Initialize
        self.bridge = CvBridge()
        self.cameras: Dict[str, CameraInstance] = {}
        self.publishers: Dict[str, Dict] = {}
        self.lock = threading.Lock()

        # Setup cameras
        self._setup_cameras(camera_configs)

        # Create timer for publishing
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_callback)

        self.get_logger().info(f'Multi-camera manager initialized with {len(self.cameras)} cameras')

    def _setup_cameras(self, camera_configs: List):
        """Setup all cameras from configuration."""
        for config in camera_configs:
            serial = config.get('serial_number', '')
            name = config.get('camera_name', f'camera_{serial}')
            enable_color = config.get('enable_color', True)
            enable_depth = config.get('enable_depth', True)

            # Create camera instance
            camera = CameraInstance(
                serial_number=serial,
                camera_name=name,
                enable_color=enable_color,
                enable_depth=enable_depth,
                color_width=config.get('color_width', 640),
                color_height=config.get('color_height', 480),
                color_fps=config.get('color_fps', 30),
                depth_width=config.get('depth_width', 640),
                depth_height=config.get('depth_height', 480),
                depth_fps=config.get('depth_fps', 30)
            )

            # Start camera
            if camera.start():
                self.cameras[name] = camera
                self._create_publishers(name, enable_color, enable_depth)
                self.get_logger().info(f'Started camera: {name} (SN: {serial})')
            else:
                self.get_logger().error(f'Failed to start camera: {name} (SN: {serial})')

    def _create_publishers(self, camera_name: str, enable_color: bool, enable_depth: bool):
        """Create ROS2 publishers for a camera."""
        self.publishers[camera_name] = {}

        if enable_color:
            self.publishers[camera_name]['color_image'] = self.create_publisher(
                Image, f'/{camera_name}/color/image_raw', 10)
            self.publishers[camera_name]['color_info'] = self.create_publisher(
                CameraInfo, f'/{camera_name}/color/camera_info', 10)

        if enable_depth:
            self.publishers[camera_name]['depth_image'] = self.create_publisher(
                Image, f'/{camera_name}/depth/image_raw', 10)
            self.publishers[camera_name]['depth_info'] = self.create_publisher(
                CameraInfo, f'/{camera_name}/depth/camera_info', 10)

    def publish_callback(self):
        """Publish frames from all cameras."""
        with self.lock:
            for camera_name, camera in self.cameras.items():
                color_frame, depth_frame, timestamp = camera.get_frames()

                if color_frame is None and depth_frame is None:
                    continue

                # Create header with hardware timestamp
                header = Header()
                header.stamp = self.get_clock().now().to_msg()
                header.frame_id = camera_name

                # Publish color image
                if color_frame is not None:
                    color_image = np.asanyarray(color_frame.get_data())
                    color_msg = self.bridge.cv2_to_imgmsg(color_image, encoding='bgr8')
                    color_msg.header = header
                    self.publishers[camera_name]['color_image'].publish(color_msg)

                    # Publish color camera info
                    color_info = self._create_camera_info(color_frame, header)
                    self.publishers[camera_name]['color_info'].publish(color_info)

                # Publish depth image
                if depth_frame is not None:
                    depth_image = np.asanyarray(depth_frame.get_data())
                    depth_msg = self.bridge.cv2_to_imgmsg(depth_image, encoding='16UC1')
                    depth_msg.header = header
                    self.publishers[camera_name]['depth_image'].publish(depth_msg)

                    # Publish depth camera info
                    depth_info = self._create_camera_info(depth_frame, header)
                    self.publishers[camera_name]['depth_info'].publish(depth_info)

    def _create_camera_info(self, frame, header: Header) -> CameraInfo:
        """Create CameraInfo message from frame intrinsics."""
        info = CameraInfo()
        info.header = header

        intrinsics = frame.profile.as_video_stream_profile().intrinsics
        info.width = intrinsics.width
        info.height = intrinsics.height
        info.distortion_model = 'plumb_bob'

        # Intrinsic matrix
        info.k = [intrinsics.fx, 0.0, intrinsics.ppx,
                  0.0, intrinsics.fy, intrinsics.ppy,
                  0.0, 0.0, 1.0]

        # Distortion coefficients
        info.d = list(intrinsics.coeffs)

        # Rectification matrix (identity for unrectified)
        info.r = [1.0, 0.0, 0.0,
                  0.0, 1.0, 0.0,
                  0.0, 0.0, 1.0]

        # Projection matrix
        info.p = [intrinsics.fx, 0.0, intrinsics.ppx, 0.0,
                  0.0, intrinsics.fy, intrinsics.ppy, 0.0,
                  0.0, 0.0, 1.0, 0.0]

        return info

    def destroy_node(self):
        """Clean up resources."""
        with self.lock:
            for camera in self.cameras.values():
                camera.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MultiCameraManager()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
