#!/usr/bin/env python3
"""
意图计算节点 - 从相机图像计算意图因子

订阅:
  - /camera/color/image_raw (RGB图像)
  - /camera/color/camera_info (相机标定信息)
  - /right_arm/joint_states (机械臂状态，用于正运动学)

发布:
  - /intent_factors (意图因子: α_geo, α_vel, α_dir)
  - /intent_debug_image (可视化调试图像)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, JointState
from std_msgs.msg import Float32MultiArray
from cv_bridge import CvBridge
import numpy as np
import cv2
import sys
import os
import yaml

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.intent_detector import ContinuousIntentDetector


class IntentCalculationNode(Node):
    def __init__(self):
        super().__init__('intent_calculation_node')

        # CV Bridge for image conversion
        self.bridge = CvBridge()

        # 加载配置文件
        config = self.load_config()

        # 意图检测器（使用core中的实现）
        self.intent_detector = ContinuousIntentDetector()

        # 相机标定参数
        self.camera_info = None
        self.camera_matrix = None
        self.dist_coeffs = None

        # 机械臂状态
        self.current_joint_positions = None

        # 从配置文件读取参数
        intent_config = config.get('startup', {}).get('intent_calculation', {})
        aruco_config = intent_config.get('aruco', {})
        hand_offset_config = intent_config.get('hand_offset', {})
        target_config = intent_config.get('target_position', {})

        # ArUco参数
        self.aruco_dict_type = aruco_config.get('dict_type', 'DICT_4X4_50')
        self.marker_size = aruco_config.get('marker_size', 0.05)

        # 手部偏移
        self.hand_offset = np.array([
            hand_offset_config.get('x', 0.0),
            hand_offset_config.get('y', 0.0),
            hand_offset_config.get('z', 0.1)
        ])

        # 目标位置
        self.target_position = np.array([
            target_config.get('x', 0.5),
            target_config.get('y', 0.0),
            target_config.get('z', 0.3)
        ])

        # 初始化ArUco检测器
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, self.aruco_dict_type)
        )
        self.aruco_params = cv2.aruco.DetectorParameters()

        # 历史数据（用于计算速度）
        self.prev_hand_position = None
        self.prev_timestamp = None

        # 订阅相机话题
        self.image_sub = self.create_subscription(
            Image,
            '/camera/color/image_raw',
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera/color/camera_info',
            self.camera_info_callback,
            10
        )

        # 订阅机械臂状态
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/right_arm/joint_states',
            self.joint_states_callback,
            10
        )

        # 发布意图因子
        self.intent_pub = self.create_publisher(
            Float32MultiArray,
            '/intent_factors',
            10
        )

        # 发布可视化图像
        self.debug_image_pub = self.create_publisher(
            Image,
            '/intent_debug_image',
            10
        )

        self.get_logger().info('意图计算节点已启动')
        self.get_logger().info(f'ArUco字典: {self.aruco_dict_type}')
        self.get_logger().info(f'标定码尺寸: {self.marker_size} m')
        self.get_logger().info(f'手部偏移: {self.hand_offset}')
        self.get_logger().info(f'目标位置: {self.target_position}')

    def load_config(self):
        """加载配置文件"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            '../../config/system_config.yaml'
        )
        config_path = os.path.abspath(config_path)

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.get_logger().info(f'已加载配置文件: {config_path}')
            return config
        except Exception as e:
            self.get_logger().error(f'加载配置文件失败: {str(e)}')
            return {}

        # 初始化ArUco检测器
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, self.aruco_dict_type)
        )
        self.aruco_params = cv2.aruco.DetectorParameters()

        # 历史数据（用于计算速度）
        self.prev_hand_position = None
        self.prev_timestamp = None

        # 订阅相机话题
        self.image_sub = self.create_subscription(
            Image,
            '/camera/color/image_raw',
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera/color/camera_info',
            self.camera_info_callback,
            10
        )

        # 订阅机械臂状态
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/right_arm/joint_states',
            self.joint_states_callback,
            10
        )

        # 发布意图因子
        self.intent_pub = self.create_publisher(
            Float32MultiArray,
            '/intent_factors',
            10
        )

        # 发布可视化图像
        self.debug_image_pub = self.create_publisher(
            Image,
            '/intent_debug_image',
            10
        )

        self.get_logger().info('意图计算节点已启动')
        self.get_logger().info(f'ArUco字典: {self.aruco_dict_type}')
        self.get_logger().info(f'标定码尺寸: {self.marker_size} m')
        self.get_logger().info(f'手部偏移: {self.hand_offset}')
        self.get_logger().info(f'目标位置: {self.target_position}')

    def camera_info_callback(self, msg):
        """接收相机标定信息"""
        if self.camera_info is None:
            self.camera_info = msg
            self.camera_matrix = np.array(msg.k).reshape(3, 3)
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info('已接收相机标定信息')

    def joint_states_callback(self, msg):
        """接收机械臂关节状态"""
        if len(msg.position) >= 7:
            self.current_joint_positions = np.array(msg.position[:7])

    def image_callback(self, msg):
        """处理图像并计算意图因子"""
        if self.camera_matrix is None:
            self.get_logger().warn('等待相机标定信息...', throttle_duration_sec=5.0)
            return

        try:
            # 转换ROS图像到OpenCV格式
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # 检测手部位置和速度
            hand_position, hand_velocity = self.detect_hand_position(cv_image, msg.header.stamp)

            if hand_position is not None:
                # 使用core中的意图检测器计算意图因子
                intent_result = self.intent_detector.detect_intent(
                    current_pos=hand_position,
                    target_pos=self.target_position,
                    velocity=hand_velocity if hand_velocity is not None else np.zeros(3),
                    smooth=True
                )

                # 发布意图因子
                self.publish_intent_factors(intent_result)

                # 可视化
                debug_image = self.visualize_detection(cv_image, hand_position, intent_result)
                self.publish_debug_image(debug_image)

        except Exception as e:
            self.get_logger().error(f'图像处理错误: {str(e)}')

    def detect_hand_position(self, image, timestamp):
        """检测手部位置（使用ArUco标定码 + 手动偏移）"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 检测ArUco标定码
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray,
            self.aruco_dict,
            parameters=self.aruco_params
        )

        if ids is None or len(ids) == 0:
            self.get_logger().warn('未检测到ArUco标定码', throttle_duration_sec=2.0)
            return None, None

        # 估计标定码姿态
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            self.marker_size,
            self.camera_matrix,
            self.dist_coeffs
        )

        # 使用第一个检测到的标定码
        marker_position = tvecs[0][0]
        marker_rotation = rvecs[0][0]

        # 转换旋转向量为旋转矩阵
        rotation_matrix, _ = cv2.Rodrigues(marker_rotation)

        # 应用手部偏移
        hand_position = marker_position + rotation_matrix @ self.hand_offset

        # 计算速度
        hand_velocity = None
        current_time = timestamp.sec + timestamp.nanosec * 1e-9

        if self.prev_hand_position is not None and self.prev_timestamp is not None:
            dt = current_time - self.prev_timestamp
            if dt > 0:
                hand_velocity = (hand_position - self.prev_hand_position) / dt

        # 更新历史数据
        self.prev_hand_position = hand_position.copy()
        self.prev_timestamp = current_time

        return hand_position, hand_velocity

    def publish_intent_factors(self, intent_result):
        """发布意图因子"""
        msg = Float32MultiArray()
        msg.data = [
            intent_result.alpha,
            intent_result.alpha_geo,
            intent_result.alpha_vel,
            intent_result.alpha_dir
        ]
        self.intent_pub.publish(msg)

        # 打印日志
        self.get_logger().info(
            f'意图因子: α={intent_result.alpha:.3f} '
            f'(geo={intent_result.alpha_geo:.3f}, '
            f'vel={intent_result.alpha_vel:.3f}, '
            f'dir={intent_result.alpha_dir:.3f})',
            throttle_duration_sec=1.0
        )

    def visualize_detection(self, image, hand_position, intent_result):
        """可视化检测结果"""
        debug_image = image.copy()

        # 绘制手部位置信息
        y_offset = 30
        cv2.putText(debug_image, f'Hand: ({hand_position[0]:.2f}, {hand_position[1]:.2f}, {hand_position[2]:.2f})',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 30

        # 绘制意图因子
        cv2.putText(debug_image, f'Alpha: {intent_result.alpha:.3f}',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        y_offset += 25

        cv2.putText(debug_image, f'  geo: {intent_result.alpha_geo:.3f}',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20

        cv2.putText(debug_image, f'  vel: {intent_result.alpha_vel:.3f}',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20

        cv2.putText(debug_image, f'  dir: {intent_result.alpha_dir:.3f}',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 25

        # 绘制距离和速度
        cv2.putText(debug_image, f'Distance: {intent_result.distance:.3f} m',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20

        cv2.putText(debug_image, f'Velocity: {intent_result.velocity_norm:.3f} m/s',
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return debug_image

    def publish_debug_image(self, image):
        """发布调试图像"""
        try:
            debug_msg = self.bridge.cv2_to_imgmsg(image, encoding='bgr8')
            self.debug_image_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().error(f'发布调试图像失败: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    node = IntentCalculationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('节点被用户中断')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

    def __init__(self):
        super().__init__('intent_calculation_node')

        # CV Bridge for image conversion
        self.bridge = CvBridge()

        # 相机标定参数
        self.camera_info = None
        self.camera_matrix = None
        self.dist_coeffs = None

        # 标定码参数（用户需要配置）
        self.declare_parameter('aruco_dict_type', 'DICT_4X4_50')
        self.declare_parameter('marker_size', 0.05)  # 标定码尺寸（米）
        self.declare_parameter('hand_offset_x', 0.0)  # 手部相对标定码的偏移
        self.declare_parameter('hand_offset_y', 0.0)
        self.declare_parameter('hand_offset_z', 0.0)

        # 获取参数
        self.aruco_dict_type = self.get_parameter('aruco_dict_type').value
        self.marker_size = self.get_parameter('marker_size').value
        self.hand_offset = np.array([
            self.get_parameter('hand_offset_x').value,
            self.get_parameter('hand_offset_y').value,
            self.get_parameter('hand_offset_z').value
        ])

        # 初始化ArUco检测器
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, self.aruco_dict_type)
        )
        self.aruco_params = cv2.aruco.DetectorParameters()

        # 历史数据（用于计算速度）
        self.prev_hand_position = None
        self.prev_timestamp = None

        # 订阅相机话题
        self.image_sub = self.create_subscription(
            Image,
            '/camera/color/image_raw',
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera/color/camera_info',
            self.camera_info_callback,
            10
        )

        # 发布意图因子
        self.intent_pub = self.create_publisher(
            Float32MultiArray,
            '/intent_factors',
            10
        )

        # 可选：发布可视化图像
        self.debug_image_pub = self.create_publisher(
            Image,
            '/intent_debug_image',
            10
        )

        self.get_logger().info('意图计算节点已启动')
        self.get_logger().info(f'ArUco字典: {self.aruco_dict_type}')
        self.get_logger().info(f'标定码尺寸: {self.marker_size} m')
        self.get_logger().info(f'手部偏移: {self.hand_offset}')

    def camera_info_callback(self, msg):
        """接收相机标定信息"""
        if self.camera_info is None:
            self.camera_info = msg
            # 提取相机内参矩阵
            self.camera_matrix = np.array(msg.k).reshape(3, 3)
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info('已接收相机标定信息')

    def image_callback(self, msg):
        """处理图像并计算意图因子"""
        if self.camera_matrix is None:
            self.get_logger().warn('等待相机标定信息...', throttle_duration_sec=5.0)
            return

        try:
            # 转换ROS图像到OpenCV格式
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # 检测ArUco标定码
            hand_position, hand_velocity = self.detect_hand_position(cv_image, msg.header.stamp)

            if hand_position is not None:
                # 计算意图因子
                intent_factors = self.calculate_intent_factors(
                    hand_position,
                    hand_velocity
                )

                # 发布意图因子
                self.publish_intent_factors(intent_factors)

                # 可视化（可选）
                debug_image = self.visualize_detection(cv_image, hand_position)
                self.publish_debug_image(debug_image)

        except Exception as e:
            self.get_logger().error(f'图像处理错误: {str(e)}')

    def detect_hand_position(self, image, timestamp):
        """
        检测手部位置

        使用ArUco标定码 + 手动测量偏移

        Returns:
            hand_position: 手部3D位置 (x, y, z) in meters
            hand_velocity: 手部速度 (vx, vy, vz) in m/s
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 检测ArUco标定码
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray,
            self.aruco_dict,
            parameters=self.aruco_params
        )

        if ids is None or len(ids) == 0:
            self.get_logger().warn('未检测到ArUco标定码', throttle_duration_sec=2.0)
            return None, None

        # 估计标定码姿态
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            self.marker_size,
            self.camera_matrix,
            self.dist_coeffs
        )

        # 使用第一个检测到的标定码
        marker_position = tvecs[0][0]  # (x, y, z) in camera frame
        marker_rotation = rvecs[0][0]  # rotation vector

        # 转换旋转向量为旋转矩阵
        rotation_matrix, _ = cv2.Rodrigues(marker_rotation)

        # 应用手部偏移（在标定码坐标系中）
        hand_position = marker_position + rotation_matrix @ self.hand_offset

        # 计算速度
        hand_velocity = None
        current_time = timestamp.sec + timestamp.nanosec * 1e-9

        if self.prev_hand_position is not None and self.prev_timestamp is not None:
            dt = current_time - self.prev_timestamp
            if dt > 0:
                hand_velocity = (hand_position - self.prev_hand_position) / dt

        # 更新历史数据
        self.prev_hand_position = hand_position.copy()
        self.prev_timestamp = current_time

        return hand_position, hand_velocity

    def calculate_intent_factors(self, hand_position, hand_velocity):
        """
        计算意图因子 (α_geo, α_vel, α_dir)

        TODO: 用户需要在这里填充具体的计算逻辑

        Args:
            hand_position: 手部3D位置 (x, y, z) in meters
            hand_velocity: 手部速度 (vx, vy, vz) in m/s

        Returns:
            dict: {'alpha_geo': float, 'alpha_vel': float, 'alpha_dir': float}
        """
        # ============================================================
        # TODO: 用户在这里填充意图计算代码
        # ============================================================

        # 示例：简单的启发式规则
        # 实际计算逻辑应该根据论文中的公式实现

        # α_geo: 几何意图因子（基于距离）
        distance = np.linalg.norm(hand_position)
        alpha_geo = 1.0 / (1.0 + distance)  # 距离越近，意图越强

        # α_vel: 速度意图因子
        if hand_velocity is not None:
            speed = np.linalg.norm(hand_velocity)
            alpha_vel = np.exp(-speed)  # 速度越快，意图越弱（需要更多平滑）
        else:
            alpha_vel = 1.0

        # α_dir: 方向意图因子
        alpha_dir = 1.0  # 简化版本，实际需要根据运动方向计算

        return {
            'alpha_geo': float(alpha_geo),
            'alpha_vel': float(alpha_vel),
            'alpha_dir': float(alpha_dir)
        }

    def publish_intent_factors(self, intent_factors):
        """发布意图因子"""
        msg = Float32MultiArray()
        msg.data = [
            intent_factors['alpha_geo'],
            intent_factors['alpha_vel'],
            intent_factors['alpha_dir']
        ]
        self.intent_pub.publish(msg)

        # 打印日志
        self.get_logger().info(
            f'意图因子: α_geo={intent_factors["alpha_geo"]:.3f}, '
            f'α_vel={intent_factors["alpha_vel"]:.3f}, '
            f'α_dir={intent_factors["alpha_dir"]:.3f}',
            throttle_duration_sec=1.0
        )

    def visualize_detection(self, image, hand_position):
        """可视化检测结果"""
        debug_image = image.copy()

        # 在图像上绘制手部位置信息
        text = f'Hand: ({hand_position[0]:.2f}, {hand_position[1]:.2f}, {hand_position[2]:.2f})'
        cv2.putText(
            debug_image,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        return debug_image

    def publish_debug_image(self, image):
        """发布调试图像"""
        try:
            debug_msg = self.bridge.cv2_to_imgmsg(image, encoding='bgr8')
            self.debug_image_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().error(f'发布调试图像失败: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    node = IntentCalculationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('节点被用户中断')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()