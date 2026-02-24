#!/usr/bin/env python3
"""
鲁棒的多相机管理器
支持自动发现、故障恢复、硬件时间戳

改进点：
1. 自动发现RealSense相机
2. 相机故障自动重连
3. 使用硬件时间戳
4. 数据质量监控（不做滤波，只做检测）
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Header, String
import pyrealsense2 as rs
import numpy as np
from cv_bridge import CvBridge
import threading
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CameraInstance:
    """单个相机实例（带故障恢复）"""

    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger
        self.camera_id = config['id']
        self.serial = config['serial']

        # 状态
        self.is_running = False
        self.last_frame_time = 0
        self.consecutive_failures = 0

        # Pipeline
        self.pipeline = None
        self.profile = None
        self.align = None

        # 统计
        self.stats = {
            'total_frames': 0,
            'failed_frames': 0,
            'reconnect_count': 0
        }

    def start(self) -> bool:
        """启动相机"""
        try:
            # 创建pipeline和config
            self.pipeline = rs.pipeline()
            config = rs.config()

            # 如果指定了序列号，启用该设备
            if self.serial != "auto":
                config.enable_device(self.serial)

            # 配置流
            streams = self.config['streams']
            if 'color' in streams:
                c = streams['color']
                config.enable_stream(
                    rs.stream.color,
                    c['resolution'][0], c['resolution'][1],
                    rs.format.bgr8, c['fps']
                )

            if 'depth' in streams:
                d = streams['depth']
                config.enable_stream(
                    rs.stream.depth,
                    d['resolution'][0], d['resolution'][1],
                    rs.format.z16, d['fps']
                )

            # 启动pipeline
            self.profile = self.pipeline.start(config)

            # 创建对齐对象
            if 'color' in streams and 'depth' in streams:
                self.align = rs.align(rs.stream.color)

            # 获取实际的序列号（如果是auto模式）
            if self.serial == "auto":
                device = self.profile.get_device()
                self.serial = device.get_info(rs.camera_info.serial_number)
                self.logger.info(f"相机 {self.camera_id} 自动检测到序列号: {self.serial}")

            self.is_running = True
            self.consecutive_failures = 0
            self.logger.info(f"✅ 相机 {self.camera_id} 启动成功 (SN: {self.serial})")
            return True

        except Exception as e:
            self.logger.error(f"❌ 相机 {self.camera_id} 启动失败: {e}")
            return False

    def stop(self):
        """停止相机"""
        if self.pipeline and self.is_running:
            try:
                self.pipeline.stop()
                self.is_running = False
                self.logger.info(f"相机 {self.camera_id} 已停止")
            except Exception as e:
                self.logger.error(f"停止相机 {self.camera_id} 时出错: {e}")

    def get_frames(self) -> Tuple[Optional[rs.frame], Optional[rs.frame], Optional[float]]:
        """
        获取帧（带硬件时间戳）

        Returns:
            (color_frame, depth_frame, hardware_timestamp_ms)
        """
        if not self.is_running:
            return None, None, None

        try:
            # 等待帧（1秒超时）
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)

            # 获取硬件时间戳（毫秒）
            hw_timestamp = frames.get_timestamp()

            # 对齐深度到彩色
            if self.align:
                frames = self.align.process(frames)

            # 提取帧
            color_frame = frames.get_color_frame() if 'color' in self.config['streams'] else None
            depth_frame = frames.get_depth_frame() if 'depth' in self.config['streams'] else None

            # 更新统计
            self.stats['total_frames'] += 1
            self.last_frame_time = time.time()
            self.consecutive_failures = 0

            return color_frame, depth_frame, hw_timestamp

        except Exception as e:
            self.stats['failed_frames'] += 1
            self.consecutive_failures += 1

            if self.consecutive_failures % 10 == 0:
                self.logger.warn(
                    f"相机 {self.camera_id} 连续失败 {self.consecutive_failures} 次: {e}"
                )

            return None, None, None

    def check_health(self) -> dict:
        """检查相机健康状态"""
        now = time.time()
        time_since_last_frame = now - self.last_frame_time if self.last_frame_time > 0 else 0

        return {
            'camera_id': self.camera_id,
            'is_running': self.is_running,
            'serial': self.serial,
            'time_since_last_frame': time_since_last_frame,
            'consecutive_failures': self.consecutive_failures,
            'total_frames': self.stats['total_frames'],
            'failed_frames': self.stats['failed_frames'],
            'reconnect_count': self.stats['reconnect_count'],
            'status': 'ok' if self.is_running and self.consecutive_failures < 5 else 'failed'
        }


class RobustCameraManager(Node):
    """鲁棒的多相机管理器"""

    def __init__(self):
        super().__init__('robust_camera_manager')

        # 加载配置
        self.config = self._load_config()

        # 初始化
        self.bridge = CvBridge()
        self.cameras: Dict[str, CameraInstance] = {}
        self.camera_publishers: Dict[str, Dict] = {}  # 改名避免与ROS2 Node冲突
        self.lock = threading.Lock()

        # 自动发现相机
        if self.config['camera_manager']['auto_discovery']:
            self._auto_discover_cameras()

        # 设置相机
        self._setup_cameras()

        # 创建发布定时器
        publish_rate = self.config['camera_manager'].get('publish_rate', 30.0)
        self.timer = self.create_timer(1.0 / publish_rate, self.publish_callback)

        # 创建健康检查定时器
        self.health_timer = self.create_timer(1.0, self.health_check_callback)

        # 启动自动重连线程
        if self.config['camera_manager']['enable_auto_reconnect']:
            self.reconnect_thread = threading.Thread(target=self._auto_reconnect_loop, daemon=True)
            self.reconnect_thread.start()

        # 创建状态发布器
        self.status_pub = self.create_publisher(String, '/camera_manager/status', 10)

        self.get_logger().info(f"✅ 鲁棒相机管理器初始化完成，管理 {len(self.cameras)} 个相机")

    def _load_config(self) -> dict:
        """加载配置文件"""
        config_path = Path(__file__).parent.parent.parent.parent / 'config' / 'camera_config.yaml'

        if not config_path.exists():
            self.get_logger().warn(f"配置文件不存在: {config_path}，使用默认配置")
            return self._get_default_config()

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.get_logger().info(f"已加载配置: {config_path}")
        return config

    def _get_default_config(self) -> dict:
        """默认配置"""
        return {
            'camera_manager': {
                'auto_discovery': True,
                'enable_auto_reconnect': True,
                'reconnect_interval': 2.0,
                'use_hardware_timestamp': True,
                'publish_rate': 30.0
            },
            'cameras': [
                {
                    'id': 'overhead',
                    'serial': 'auto',
                    'enabled': True,
                    'streams': {
                        'color': {'resolution': [848, 480], 'fps': 30},
                        'depth': {'resolution': [848, 480], 'fps': 30}
                    }
                }
            ]
        }

    def _auto_discover_cameras(self):
        """自动发现RealSense相机"""
        ctx = rs.context()
        devices = ctx.query_devices()

        discovered = []
        for dev in devices:
            serial = dev.get_info(rs.camera_info.serial_number)
            model = dev.get_info(rs.camera_info.name)
            discovered.append({'serial': serial, 'model': model})

        self.get_logger().info(f"🔍 自动发现 {len(discovered)} 个相机: {discovered}")

    def _setup_cameras(self):
        """设置所有相机"""
        for cam_config in self.config['cameras']:
            if not cam_config.get('enabled', True):
                continue

            camera_id = cam_config['id']
            camera = CameraInstance(cam_config, self.get_logger())

            if camera.start():
                self.cameras[camera_id] = camera
                self._create_publishers(camera_id, cam_config['streams'])
            else:
                self.get_logger().error(f"无法启动相机: {camera_id}")

    def _create_publishers(self, camera_id: str, streams: dict):
        """创建ROS2发布器"""
        self.camera_publishers[camera_id] = {}

        if 'color' in streams:
            self.camera_publishers[camera_id]['color_image'] = self.create_publisher(
                Image, f'/{camera_id}/color/image_raw', 10
            )
            self.camera_publishers[camera_id]['color_info'] = self.create_publisher(
                CameraInfo, f'/{camera_id}/color/camera_info', 10
            )

        if 'depth' in streams:
            self.camera_publishers[camera_id]['depth_image'] = self.create_publisher(
                Image, f'/{camera_id}/depth/image_raw', 10
            )
            self.camera_publishers[camera_id]['depth_info'] = self.create_publisher(
                CameraInfo, f'/{camera_id}/depth/camera_info', 10
            )

    def publish_callback(self):
        """发布帧"""
        with self.lock:
            for camera_id, camera in self.cameras.items():
                color_frame, depth_frame, hw_timestamp = camera.get_frames()

                if color_frame is None and depth_frame is None:
                    continue

                # 创建header
                header = self._create_header(camera_id, hw_timestamp)

                # 发布彩色图像
                if color_frame is not None:
                    self._publish_color(camera_id, color_frame, header)

                # 发布深度图像
                if depth_frame is not None:
                    self._publish_depth(camera_id, depth_frame, header)

    def _create_header(self, camera_id: str, hw_timestamp: Optional[float]) -> Header:
        """创建消息头（支持硬件时间戳）"""
        header = Header()
        header.frame_id = camera_id

        if self.config['camera_manager']['use_hardware_timestamp'] and hw_timestamp is not None:
            # 使用硬件时间戳（毫秒转秒）
            sec = int(hw_timestamp / 1000.0)
            nanosec = int((hw_timestamp % 1000.0) * 1e6)
            header.stamp.sec = sec
            header.stamp.nanosec = nanosec
        else:
            # 使用ROS时间
            header.stamp = self.get_clock().now().to_msg()

        return header

    def _publish_color(self, camera_id: str, color_frame, header: Header):
        """发布彩色图像"""
        color_image = np.asanyarray(color_frame.get_data())
        color_msg = self.bridge.cv2_to_imgmsg(color_image, encoding='bgr8')
        color_msg.header = header
        self.camera_publishers[camera_id]['color_image'].publish(color_msg)

        # 发布相机信息
        color_info = self._create_camera_info(color_frame, header)
        self.camera_publishers[camera_id]['color_info'].publish(color_info)

    def _publish_depth(self, camera_id: str, depth_frame, header: Header):
        """发布深度图像"""
        depth_image = np.asanyarray(depth_frame.get_data())
        depth_msg = self.bridge.cv2_to_imgmsg(depth_image, encoding='16UC1')
        depth_msg.header = header
        self.camera_publishers[camera_id]['depth_image'].publish(depth_msg)

        # 发布相机信息
        depth_info = self._create_camera_info(depth_frame, header)
        self.camera_publishers[camera_id]['depth_info'].publish(depth_info)

    def _create_camera_info(self, frame, header: Header) -> CameraInfo:
        """创建相机信息消息"""
        info = CameraInfo()
        info.header = header

        intrinsics = frame.profile.as_video_stream_profile().intrinsics
        info.width = intrinsics.width
        info.height = intrinsics.height
        info.distortion_model = 'plumb_bob'

        info.k = [intrinsics.fx, 0.0, intrinsics.ppx,
                  0.0, intrinsics.fy, intrinsics.ppy,
                  0.0, 0.0, 1.0]

        info.d = list(intrinsics.coeffs)

        info.r = [1.0, 0.0, 0.0,
                  0.0, 1.0, 0.0,
                  0.0, 0.0, 1.0]

        info.p = [intrinsics.fx, 0.0, intrinsics.ppx, 0.0,
                  0.0, intrinsics.fy, intrinsics.ppy, 0.0,
                  0.0, 0.0, 1.0, 0.0]

        return info

    def health_check_callback(self):
        """健康检查回调"""
        status_lines = ["=== 相机健康状态 ==="]

        for camera_id, camera in self.cameras.items():
            health = camera.check_health()
            status_lines.append(
                f"{camera_id}: {health['status']} | "
                f"帧数: {health['total_frames']} | "
                f"失败: {health['failed_frames']} | "
                f"重连: {health['reconnect_count']}"
            )

        # 发布状态
        status_msg = String()
        status_msg.data = "\n".join(status_lines)
        self.status_pub.publish(status_msg)

    def _auto_reconnect_loop(self):
        """自动重连循环"""
        interval = self.config['camera_manager']['reconnect_interval']
        max_attempts = self.config['camera_manager'].get('max_reconnect_attempts', 10)

        while rclpy.ok():
            time.sleep(interval)

            with self.lock:
                for camera_id, camera in list(self.cameras.items()):
                    health = camera.check_health()

                    if health['status'] == 'failed':
                        if health['reconnect_count'] >= max_attempts:
                            self.get_logger().error(
                                f"相机 {camera_id} 重连次数超限 ({max_attempts})，放弃重连"
                            )
                            continue

                        self.get_logger().warn(f"尝试重连相机: {camera_id}")

                        # 停止旧连接
                        camera.stop()
                        time.sleep(0.5)

                        # 尝试重新启动
                        if camera.start():
                            camera.stats['reconnect_count'] += 1
                            self.get_logger().info(
                                f"✅ 相机 {camera_id} 重连成功 "
                                f"(第 {camera.stats['reconnect_count']} 次)"
                            )
                        else:
                            self.get_logger().error(f"❌ 相机 {camera_id} 重连失败")

    def destroy_node(self):
        """清理资源"""
        with self.lock:
            for camera in self.cameras.values():
                camera.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobustCameraManager()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        node.get_logger().error(f"运行时错误: {e}")
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass

        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass  # 忽略shutdown错误


if __name__ == '__main__':
    main()