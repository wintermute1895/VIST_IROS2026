"""
单个 ArUco/AprilTag 标记的手眼标定
===================================
专门用于 Eye-to-Hand 标定，标记贴在机械手背上

使用方法:
    python calibrate_single_marker.py --mode collect     # 数据采集
    python calibrate_single_marker.py --mode calibrate   # 标定解算
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入配置和接口
import config
from robot_interface import (
    RobotInterface,
    process_raw_pose,
    matrix_to_rvec_tvec,
    rvec_tvec_to_matrix
)

# =============================================================================
# 单个标记检测
# =============================================================================

def detect_single_marker(
    image: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    marker_config: dict
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    检测单个 ArUco/AprilTag 标记并估计其位姿

    Args:
        image: 输入图像
        camera_matrix: 相机内参矩阵
        dist_coeffs: 畸变系数
        marker_config: 标记配置字典

    Returns:
        Tuple of (corners, rvec, tvec) 如果检测成功，否则返回 None
    """
    # 获取字典
    aruco_dict = cv2.aruco.getPredefinedDictionary(marker_config['dict_type'])

    # 检测标记
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    if ids is None or len(ids) == 0:
        return None

    # 查找目标标记
    target_id = marker_config['marker_id']
    marker_idx = None
    for i, marker_id in enumerate(ids):
        if marker_id[0] == target_id:
            marker_idx = i
            break

    if marker_idx is None:
        return None

    # 获取标记的4个角点
    marker_corners = corners[marker_idx][0]  # shape: (4, 2)

    # 定义标记的3D坐标（标记中心为原点）
    marker_size = marker_config['marker_size']
    half_size = marker_size / 2.0
    obj_points = np.array([
        [-half_size, half_size, 0],   # 左上
        [half_size, half_size, 0],    # 右上
        [half_size, -half_size, 0],   # 右下
        [-half_size, -half_size, 0]   # 左下
    ], dtype=np.float32)

    # 使用 solvePnP 估计位姿
    success, rvec, tvec = cv2.solvePnP(
        obj_points,
        marker_corners,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return None

    return marker_corners, rvec, tvec
# =============================================================================
# 数据采集
# =============================================================================

class SingleMarkerCollector:
    """单标记数据采集器"""

    def __init__(self, robot: RobotInterface, marker_config: dict):
        self.robot = robot
        self.marker_config = marker_config
        self.camera_matrix = None
        self.dist_coeffs = None
        self.pipeline = None

        # 初始化相机
        self._init_camera()

        # 数据存储
        self.collected_poses = []
        self.collected_images = []

    def _init_camera(self):
        """初始化 RealSense 相机"""
        try:
            import pyrealsense2 as rs

            self.pipeline = rs.pipeline()
            rs_config = rs.config()

            # 配置彩色流
            rs_config.enable_stream(
                rs.stream.color,
                config.CAMERA_CONFIG['realsense']['width'],
                config.CAMERA_CONFIG['realsense']['height'],
                rs.format.bgr8,
                config.CAMERA_CONFIG['realsense']['fps']
            )

            # 启动相机
            profile = self.pipeline.start(rs_config)

            # 相机预热
            time.sleep(2)

            # 获取相机内参
            if config.CAMERA_CONFIG['realsense']['use_intrinsics']:
                color_stream = profile.get_stream(rs.stream.color)
                intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

                self.camera_matrix = np.array([
                    [intrinsics.fx, 0, intrinsics.ppx],
                    [0, intrinsics.fy, intrinsics.ppy],
                    [0, 0, 1]
                ], dtype=np.float64)

                self.dist_coeffs = np.array(intrinsics.coeffs, dtype=np.float64)

                print(f"✓ 相机初始化成功")
                print(f"  分辨率: {intrinsics.width}x{intrinsics.height}")
                print(f"  焦距: fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
            else:
                self.camera_matrix = config.CAMERA_CONFIG['manual_intrinsics']['camera_matrix']
                self.dist_coeffs = config.CAMERA_CONFIG['manual_intrinsics']['dist_coeffs']

        except ImportError:
            print("⚠️ 未安装 pyrealsense2，请安装: pip install pyrealsense2")
            raise
        except Exception as e:
            print(f"✗ 相机初始化失败: {e}")
            raise

    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧图像"""
        try:
            import pyrealsense2 as rs
            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                return None

            image = np.asanyarray(color_frame.get_data())
            return image
        except Exception as e:
            print(f"✗ 捕获图像失败: {e}")
            return None

    def collect(self):
        """交互式数据采集"""
        print("\n" + "="*70)
        print("单标记数据采集模式")
        print("="*70)
        print(f"标定模式: {config.CALIBRATION_MODE}")
        print(f"标记类型: {str(self.marker_config['dict_type']).split('.')[-1]}")
        print(f"标记 ID: {self.marker_config['marker_id']}")
        print(f"标记尺寸: {self.marker_config['marker_size']*1000:.1f} mm")
        print("\n操作说明:")
        print("  - 移动机器人到不同位姿")
        print("  - 按 's' 键保存当前数据")
        print("  - 按 'q' 键退出")
        print(f"  - 最少需要 {config.CALIBRATION_PARAMS['min_samples']} 组数据")
        print("="*70 + "\n")

        try:
            while True:
                # 捕获图像
                image = self.capture_frame()
                if image is None:
                    continue

                # 检测标记
                result = detect_single_marker(
                    image, 
                    self.camera_matrix, 
                    self.dist_coeffs,
                    self.marker_config
                )

                # 显示图像
                display_image = image.copy()

                # 如果检测到标记，绘制
                if result is not None:
                    corners, rvec, tvec = result
                    # 绘制标记边框
                    cv2.aruco.drawDetectedMarkers(display_image, [corners.reshape(1, 4, 2)])
                    # 绘制坐标轴
                    axis_length = self.marker_config['marker_size'] * 0.5
                    cv2.drawFrameAxes(
                        display_image,
                        self.camera_matrix,
                        self.dist_coeffs,
                        rvec,
                        tvec,
                        axis_length
                    )
                    status_text = f"Collected: {len(self.collected_poses)} | Marker detected | Press 's' to save"
                    status_color = (0, 255, 0)
                else:
                    status_text = f"Collected: {len(self.collected_poses)} | No marker | Press 'q' to quit"
                    status_color = (0, 0, 255)

                cv2.putText(
                    display_image,
                    status_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    status_color,
                    2
                )
                cv2.imshow("Single Marker Collection", display_image)

                # 等待按键
                key = cv2.waitKey(30) & 0xFF

                # 按 's' 键保存
                if key == ord('s'):
                    if result is None:
                        print("✗ 未检测到标记，无法保存")
                        continue

                    try:
                        print(f"\n正在保存第 {len(self.collected_poses) + 1} 组数据...")
                        # 获取机器人位姿
                        robot_pose = self.robot.get_pose()

                        # 保存
                        self.collected_poses.append(robot_pose)
                        self.collected_images.append(image.copy())

                        print(f"✓ 已保存第 {len(self.collected_poses)} 组数据")

                    except Exception as e:
                        print(f"✗ 保存失败: {e}")
                        import traceback
                        traceback.print_exc()

                # 按 'q' 键退出
                if key == ord('q'):
                    print("\n检测到 'q' 键，正在退出...")
                    break

        except KeyboardInterrupt:
            print("\n\n检测到 Ctrl+C，正在保存数据并退出...")

        finally:
            cv2.destroyAllWindows()

        # 保存到文件
        if len(self.collected_poses) > 0:
            self._save_data()
            print(f"\n✓ 数据采集完成，共 {len(self.collected_poses)} 组")

            if len(self.collected_poses) < config.CALIBRATION_PARAMS['min_samples']:
                print(f"⚠️ 警告：数据量少于推荐值 {config.CALIBRATION_PARAMS['min_samples']} 组")
        else:
            print(f"\n⚠️ 未采集任何数据")

    def _save_data(self):
        """保存采集的数据到文件"""
        # 保存位姿
        np.save(config.PATHS['poses_file'], np.array(self.collected_poses))

        # 保存图像
        for i, image in enumerate(self.collected_images):
            image_path = config.PATHS['images_dir'] / f"image_{i:03d}.png"
            cv2.imwrite(str(image_path), image)

        # 保存相机内参
        intrinsics_file = config.PATHS['data_dir'] / "camera_intrinsics.npz"
        np.savez(
            intrinsics_file,
            camera_matrix=self.camera_matrix,
            dist_coeffs=self.dist_coeffs
        )

        print(f"✓ 数据已保存到 {config.PATHS['data_dir']}")

# =============================================================================
# 标定解算
# =============================================================================

def calibrate_from_images(marker_config: dict):
    """从保存的图像和位姿数据执行标定"""
    print("\n" + "="*70)
    print("单标记标定解算模式")
    print("="*70)

    # 加载机器人位姿
    if not config.PATHS['poses_file'].exists():
        print(f"✗ 未找到位姿文件: {config.PATHS['poses_file']}")
        print("  请先运行数据采集模式")
        return

    robot_poses = np.load(config.PATHS['poses_file'])
    print(f"✓ 加载了 {len(robot_poses)} 组机器人位姿")

    # 加载相机内参
    intrinsics_file = config.PATHS['data_dir'] / "camera_intrinsics.npz"
    if intrinsics_file.exists():
        data = np.load(intrinsics_file)
        camera_matrix = data['camera_matrix']
        dist_coeffs = data['dist_coeffs']
        print(f"✓ 加载了相机内参")
    else:
        camera_matrix = config.CAMERA_CONFIG['manual_intrinsics']['camera_matrix']
        dist_coeffs = config.CAMERA_CONFIG['manual_intrinsics']['dist_coeffs']
        print(f"⚠️ 使用配置文件中的默认内参")

    # 加载图像并检测标记
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"✗ 未找到图像文件")
        return

    print(f"✓ 找到 {len(image_files)} 张图像")
    print(f"\n检测标记...")
    print(f"  标记类型: {str(marker_config['dict_type']).split('.')[-1]}")
    print(f"  标记 ID: {marker_config['marker_id']}")
    print(f"  标记尺寸: {marker_config['marker_size']*1000:.1f} mm\n")

    board_poses_in_camera = []
    valid_robot_poses = []

    for i, image_file in enumerate(image_files):
        image = cv2.imread(str(image_file))

        # 检测标记
        result = detect_single_marker(image, camera_matrix, dist_coeffs, marker_config)

        if result is not None:
            corners, rvec, tvec = result
            T_camera_to_marker = rvec_tvec_to_matrix(rvec, tvec)
            board_poses_in_camera.append(T_camera_to_marker)
            valid_robot_poses.append(robot_poses[i])
            print(f"  图像 {i+1}: ✓ 检测到标记")
        else:
            print(f"  图像 {i+1}: ✗ 检测失败")

    print(f"\n有效数据组数: {len(valid_robot_poses)}")

    if len(valid_robot_poses) < config.CALIBRATION_PARAMS['min_samples']:
        print(f"✗ 有效数据不足，需要至少 {config.CALIBRATION_PARAMS['min_samples']} 组")
        return

    # 执行标定
    result_matrix = calibrate_hand_eye(
        valid_robot_poses,
        board_poses_in_camera
    )

    if result_matrix is not None:
        # 保存结果
        np.save(config.PATHS['result_matrix_file'], result_matrix)

        # 保存为 JSON
        result_dict = {
            'mode': config.CALIBRATION_MODE,
            'marker_type': 'single_marker',
            'marker_dict': str(marker_config['dict_type']).split('.')[-1],
            'marker_id': int(marker_config['marker_id']),
            'marker_size_mm': float(marker_config['marker_size'] * 1000),
            'matrix': result_matrix.tolist(),
            'translation': result_matrix[:3, 3].tolist(),
            'rotation_matrix': result_matrix[:3, :3].tolist(),
        }

        with open(config.PATHS['result_file'], 'w') as f:
            json.dump(result_dict, f, indent=2)

        print(f"\n" + "="*70)
        print("标定结果")
        print("="*70)
        print(result_matrix)
        print(f"\n✓ 结果已保存到:")
        print(f"  - {config.PATHS['result_matrix_file']}")
        print(f"  - {config.PATHS['result_file']}")
        print("="*70 + "\n")

def calibrate_hand_eye(
    robot_poses: List[np.ndarray],
    marker_poses_in_camera: List[np.ndarray]
) -> Optional[np.ndarray]:
    """执行手眼标定"""
    print(f"\n开始标定解算...")
    print(f"  模式: {config.CALIBRATION_MODE}")
    print(f"  数据组数: {len(robot_poses)}")

    # 准备 OpenCV 输入数据
    R_gripper2base = []
    t_gripper2base = []
    R_target2cam = []
    t_target2cam = []

    for T_base_to_flange, T_camera_to_marker in zip(robot_poses, marker_poses_in_camera):
        # 提取旋转和平移
        R_gripper2base.append(T_base_to_flange[:3, :3])
        t_gripper2base.append(T_base_to_flange[:3, 3].reshape(3, 1))
        R_target2cam.append(T_camera_to_marker[:3, :3])
        t_target2cam.append(T_camera_to_marker[:3, 3].reshape(3, 1))

    # 调用 OpenCV 手眼标定
    try:
        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            R_gripper2base,
            t_gripper2base,
            R_target2cam,
            t_target2cam,
            method=config.CALIBRATION_PARAMS['method']
        )

        # 构建结果矩阵
        result_matrix = np.eye(4)
        result_matrix[:3, :3] = R_cam2gripper
        result_matrix[:3, 3] = t_cam2gripper.flatten()

        print(f"✓ 标定完成")

        return result_matrix

    except Exception as e:
        print(f"✗ 标定失败: {e}")
        return None

# =============================================================================
# 主程序
# =============================================================================

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="单标记手眼标定系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  collect   - 数据采集（需要相机和机器人）
  calibrate - 标定解算（从已采集的数据）

示例:
  python calibrate_single_marker.py --mode collect
  python calibrate_single_marker.py --mode calibrate
        """
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['collect', 'calibrate'],
        default='collect',
        help='运行模式'
    )

    args = parser.parse_args()

    # 打印配置
    print("\n" + "="*70)
    print("单标记手眼标定系统配置")
    print("="*70)
    print(f"标定模式: {config.CALIBRATION_MODE.upper()}")
    print(f"标记类型: {str(config.SINGLE_MARKER_CONFIG['dict_type']).split('.')[-1]}")
    print(f"标记 ID: {config.SINGLE_MARKER_CONFIG['marker_id']}")
    print(f"标记尺寸: {config.SINGLE_MARKER_CONFIG['marker_size']*1000:.1f} mm")
    print(f"数据目录: {config.PATHS['data_dir']}")
    print("="*70 + "\n")

    # 根据模式执行
    if args.mode == 'collect':
        # 导入 LinkerArm 接口
        try:
            from linkerarm_interface import LinkerArmInterface

            # 创建机器人接口
            print("正在连接到 LinkerArm...")
            robot = LinkerArmInterface(
                tcp_host="192.168.10.21",
                arm_side="right"
            )

            # 创建数据采集器
            collector = SingleMarkerCollector(robot, config.SINGLE_MARKER_CONFIG)

            # 开始采集
            collector.collect()

            # 断开连接
            robot.disconnect()

        except ImportError as e:
            print(f"✗ 无法导入 LinkerArm 接口: {e}")
            print("\n请确保:")
            print("  1. linkerarm_interface.py 文件存在")
            print("  2. LBot SDK 已正确安装")
        except Exception as e:
            print(f"✗ 数据采集失败: {e}")
            import traceback
            traceback.print_exc()

    elif args.mode == 'calibrate':
        calibrate_from_images(config.SINGLE_MARKER_CONFIG)

if __name__ == "__main__":
    main()
