"""
Eye-in-Hand Calibration Configuration
配置文件：包含所有标定相关的参数
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional


class CalibrationConfig:
    """
    手眼标定配置类
    包含标定板参数、相机内参、数据存储路径等
    """

    def __init__(self):
        # ==================== ChArUco 标定板参数 ====================
        # ArUco 字典类型（可选：DICT_4X4_50, DICT_5X5_50, DICT_6X6_50 等）
        self.aruco_dict_type = cv2.aruco.DICT_4X4_50

        # 标定板尺寸（棋盘格的行数和列数）
        self.charuco_board_rows = 5  # 棋盘格行数（黑白方格）
        self.charuco_board_cols = 7  # 棋盘格列数（黑白方格）

        # ⚠️ 重要：以下两个参数必须填写真实测量值（单位：米）
        # 使用卡尺或精确测量工具测量标定板上的实际尺寸
        self.square_size = 0.040  # 棋盘格方格边长（米），例如 40mm = 0.040m
        self.marker_size = 0.030  # ArUco 二维码边长（米），例如 30mm = 0.030m
        # ⚠️ 注意：marker_size 必须小于 square_size，通常为 square_size 的 0.75 倍

        # ==================== 相机内参 ====================
        # Intel RealSense D405 相机内参
        # 方式1：手动填写（从 RealSense Viewer 或标定结果获取）
        self.camera_matrix = np.array([
            [615.0, 0.0, 320.0],  # fx, 0, cx
            [0.0, 615.0, 240.0],  # 0, fy, cy
            [0.0, 0.0, 1.0]       # 0, 0, 1
        ], dtype=np.float64)

        self.dist_coeffs = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)  # 畸变系数

        # 方式2：从 RealSense SDK 动态读取（推荐）
        self.use_realsense_intrinsics = True  # 设为 True 时自动从相机读取内参

        # ==================== 数据存储路径 ====================
        self.data_dir = Path("calibration_data")  # 数据存储根目录
        self.images_dir = self.data_dir / "images"  # 图像存储目录
        self.poses_file = self.data_dir / "robot_poses.npy"  # 机械臂位姿文件
        self.result_file = self.data_dir / "hand_eye_result.json"  # 标定结果文件
        self.result_matrix_file = self.data_dir / "T_end_to_cam.npy"  # 变换矩阵文件

        # 创建目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # ==================== 标定算法参数 ====================
        # 手眼标定方法（可选：TSAI, PARK, HORAUD, ANDREFF, DANIILIDIS）
        self.calibration_method = cv2.CALIB_HAND_EYE_TSAI  # 推荐 TSAI 或 PARK

        # 最小采集数据组数
        self.min_samples = 15

        # ==================== 可视化参数 ====================
        self.reprojection_point_color = (0, 0, 255)  # 重投影点颜色（BGR：红色）
        self.reprojection_point_radius = 8  # 重投影点半径（像素）
        self.detected_corner_color = (0, 255, 0)  # 检测到的角点颜色（BGR：绿色）

    def get_charuco_board(self):
        """
        创建 ChArUco 标定板对象
        Returns:
            cv2.aruco.CharucoBoard: ChArUco 标定板对象
        """
        aruco_dict = cv2.aruco.getPredefinedDictionary(self.aruco_dict_type)
        board = cv2.aruco.CharucoBoard(
            (self.charuco_board_cols, self.charuco_board_rows),
            self.square_size,
            self.marker_size,
            aruco_dict
        )
        return board

    def get_camera_intrinsics_from_realsense(self):
        """
        从 RealSense 相机读取内参
        需要安装 pyrealsense2: pip install pyrealsense2
        Returns:
            tuple: (camera_matrix, dist_coeffs)
        """
        try:
            import pyrealsense2 as rs

            # 创建 pipeline
            pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

            # 启动 pipeline
            profile = pipeline.start(config)

            # 获取内参
            color_stream = profile.get_stream(rs.stream.color)
            intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

            # 转换为 OpenCV 格式
            camera_matrix = np.array([
                [intrinsics.fx, 0, intrinsics.ppx],
                [0, intrinsics.fy, intrinsics.ppy],
                [0, 0, 1]
            ], dtype=np.float64)

            dist_coeffs = np.array(intrinsics.coeffs, dtype=np.float64)

            # 停止 pipeline
            pipeline.stop()

            print(f"✓ 从 RealSense 相机读取内参成功")
            print(f"  Camera Matrix:\n{camera_matrix}")
            print(f"  Distortion Coeffs: {dist_coeffs}")

            return camera_matrix, dist_coeffs

        except ImportError:
            print("⚠️ 未安装 pyrealsense2，使用配置文件中的默认内参")
            print("   安装命令: pip install pyrealsense2")
            return self.camera_matrix, self.dist_coeffs
        except Exception as e:
            print(f"⚠️ 从 RealSense 读取内参失败: {e}")
            print("   使用配置文件中的默认内参")
            return self.camera_matrix, self.dist_coeffs

    def get_camera_intrinsics(self):
        """
        获取相机内参（自动选择从 RealSense 读取或使用配置值）
        Returns:
            tuple: (camera_matrix, dist_coeffs)
        """
        if self.use_realsense_intrinsics:
            return self.get_camera_intrinsics_from_realsense()
        else:
            return self.camera_matrix, self.dist_coeffs

    def print_config(self):
        """打印当前配置"""
        print("\n" + "="*60)
        print("Eye-in-Hand Calibration Configuration")
        print("="*60)
        print(f"ChArUco Board:")
        print(f"  - Dictionary: {self.aruco_dict_type}")
        print(f"  - Size: {self.charuco_board_rows} x {self.charuco_board_cols}")
        print(f"  - Square Size: {self.square_size*1000:.1f} mm")
        print(f"  - Marker Size: {self.marker_size*1000:.1f} mm")
        print(f"\nData Storage:")
        print(f"  - Data Dir: {self.data_dir}")
        print(f"  - Images Dir: {self.images_dir}")
        print(f"\nCalibration:")
        print(f"  - Method: {self.calibration_method}")
        print(f"  - Min Samples: {self.min_samples}")
        print("="*60 + "\n")


if __name__ == "__main__":
    # 测试配置
    config = CalibrationConfig()
    config.print_config()

    # 测试 ChArUco 板创建
    board = config.get_charuco_board()
    print(f"✓ ChArUco Board 创建成功")

    # 测试相机内参读取
    camera_matrix, dist_coeffs = config.get_camera_intrinsics()
    print(f"✓ 相机内参读取成功")