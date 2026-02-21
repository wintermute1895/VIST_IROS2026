"""
手眼标定系统 - 主程序
====================
统一入口，支持三种运行模式：
1. collect: 真实数据采集（相机 + 机器人）
2. simulate: 纯软件仿真验证（无需硬件）
3. calibrate: 标定解算

使用方法:
    python main.py --mode simulate    # 仿真验证
    python main.py --mode collect     # 数据采集
    python main.py --mode calibrate   # 标定解算
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入配置和接口
import config
from robot_interface import (
    RobotInterface,
    SimulatedRobot,
    process_raw_pose,
    matrix_to_rvec_tvec,
    rvec_tvec_to_matrix
)

# =============================================================================
# 模式 1: 真实数据采集
# =============================================================================

class DataCollector:
    """真实数据采集器（相机 + 机器人）"""

    def __init__(self, robot: RobotInterface):
        """
        初始化数据采集器

        Args:
            robot: 机器人接口实例
        """
        self.robot = robot
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
        """
        捕获一帧图像

        Returns:
            np.ndarray: BGR 图像，如果失败返回 None
        """
        try:
            import pyrealsense2 as rs
            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                return None

            # 转换为 numpy 数组
            image = np.asanyarray(color_frame.get_data())
            return image
        except Exception as e:
            print(f"✗ 捕获图像失败: {e}")
            return None

    def collect(self):
        """
        交互式数据采集
        按 's' 保存当前位姿和图像
        按 'q' 退出
        """
        print("\n" + "="*70)
        print("数据采集模式")
        print("="*70)
        print("操作说明:")
        print("  - 移动机器人到不同位姿")
        print("  - 按 's' 键保存当前数据")
        print("  - 按 'q' 键退出")
        print(f"  - 最少需要 {config.CALIBRATION_PARAMS['min_samples']} 组数据")
        print("="*70 + "\n")

        while True:
            # 捕获图像
            image = self.capture_frame()
            if image is None:
                continue

            # 显示图像
            display_image = image.copy()
            cv2.putText(
                display_image,
                f"Collected: {len(self.collected_poses)} | Press 's' to save, 'q' to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            cv2.imshow("Data Collection", display_image)

            # 等待按键
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                # 保存数据
                try:
                    # 获取机器人位姿
                    robot_pose = self.robot.get_pose()

                    # 保存
                    self.collected_poses.append(robot_pose)
                    self.collected_images.append(image.copy())

                    print(f"✓ 已保存第 {len(self.collected_poses)} 组数据")

                except Exception as e:
                    print(f"✗ 保存失败: {e}")

            elif key == ord('q'):
                break

        cv2.destroyAllWindows()

        # 保存到文件
        if len(self.collected_poses) >= config.CALIBRATION_PARAMS['min_samples']:
            self._save_data()
            print(f"\n✓ 数据采集完成，共 {len(self.collected_poses)} 组")
        else:
            print(f"\n⚠️ 数据不足，需要至少 {config.CALIBRATION_PARAMS['min_samples']} 组")

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
# 模式 2: 仿真数据生成与验证
# =============================================================================

def simulate_and_verify():
    """
    纯软件仿真模式
    生成合成数据，运行标定，对比结果与 Ground Truth
    """
    print("\n" + "="*70)
    print("仿真验证模式")
    print("="*70)
    print(f"标定模式: {config.CALIBRATION_MODE}")
    print(f"生成位姿数: {config.SIMULATION_CONFIG['num_poses']}")
    print("="*70 + "\n")

    # 选择 Ground Truth
    if config.CALIBRATION_MODE == 'eye_in_hand':
        ground_truth = config.SIMULATION_CONFIG['ground_truth_eye_in_hand']
        print("Ground Truth (T_flange_to_camera):")
    else:
        ground_truth = config.SIMULATION_CONFIG['ground_truth_eye_to_hand']
        print("Ground Truth (T_base_to_camera):")

    print(ground_truth)
    print()

    # 获取相机内参（使用手动配置）
    camera_matrix = config.CAMERA_CONFIG['manual_intrinsics']['camera_matrix']
    dist_coeffs = config.CAMERA_CONFIG['manual_intrinsics']['dist_coeffs']

    # 创建仿真机器人
    sim_robot = SimulatedRobot(
        mode=config.CALIBRATION_MODE,
        ground_truth=ground_truth,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        board_config=config.CHARUCO_CONFIG,
        num_poses=config.SIMULATION_CONFIG['num_poses'],
        noise_config=config.SIMULATION_CONFIG
    )

    # 获取仿真数据
    robot_poses, board_poses_in_camera = sim_robot.get_synthetic_data()

    print(f"✓ 生成了 {len(robot_poses)} 组仿真数据\n")

    # 调试：检查数据的变化范围
    print("调试信息 - 数据统计:")
    positions = np.array([pose[:3, 3] for pose in robot_poses])
    print(f"机器人位置范围:")
    print(f"  X: [{positions[:, 0].min():.3f}, {positions[:, 0].max():.3f}]")
    print(f"  Y: [{positions[:, 1].min():.3f}, {positions[:, 1].max():.3f}]")
    print(f"  Z: [{positions[:, 2].min():.3f}, {positions[:, 2].max():.3f}]")

    board_positions = np.array([pose[:3, 3] for pose in board_poses_in_camera])
    print(f"标定板在相机中的位置范围:")
    print(f"  X: [{board_positions[:, 0].min():.3f}, {board_positions[:, 0].max():.3f}]")
    print(f"  Y: [{board_positions[:, 1].min():.3f}, {board_positions[:, 1].max():.3f}]")
    print(f"  Z: [{board_positions[:, 2].min():.3f}, {board_positions[:, 2].max():.3f}]")
    print()

    # 运行标定
    result_matrix = calibrate_from_poses(
        robot_poses,
        board_poses_in_camera,
        camera_matrix,
        dist_coeffs
    )

    if result_matrix is not None:
        # 对比结果
        print("\n" + "="*70)
        print("验证结果")
        print("="*70)
        print("\nGround Truth:")
        print(ground_truth)
        print("\n计算结果:")
        print(result_matrix)

        # 计算误差
        translation_error = np.linalg.norm(
            result_matrix[:3, 3] - ground_truth[:3, 3]
        )

        # 旋转误差（使用旋转矩阵的差异）
        R_error = result_matrix[:3, :3] @ ground_truth[:3, :3].T
        rotation_error = np.arccos((np.trace(R_error) - 1) / 2) * 180 / np.pi

        print(f"\n误差分析:")
        print(f"  平移误差: {translation_error*1000:.4f} mm")
        print(f"  旋转误差: {rotation_error:.4f} 度")

        if translation_error < 0.001 and rotation_error < 1.0:
            print("\n✓ 验证通过！数学逻辑正确。")
        else:
            print("\n⚠️ 误差较大，请检查配置或算法。")

        print("="*70 + "\n")

# =============================================================================
# 模式 3: 标定解算
# =============================================================================

def detect_charuco_corners(
    image: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    检测 ChArUco 角点

    Args:
        image: 输入图像
        camera_matrix: 相机内参矩阵
        dist_coeffs: 畸变系数

    Returns:
        Tuple of (charuco_corners, charuco_ids, rvec, tvec)
        如果检测失败返回 (None, None, None)
    """
    # 获取 ChArUco 板
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 检测 ArUco 标记
    detector_params = cv2.aruco.DetectorParameters()
    corners, ids, rejected = cv2.aruco.detectMarkers(
        image,
        aruco_dict,
        parameters=detector_params
    )

    if ids is None or len(ids) < 4:
        return None, None, None

    # 插值 ChArUco 角点
    retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        corners,
        ids,
        image,
        board
    )

    if retval < 4:  # 至少需要 4 个角点
        return None, None, None

    # 亚像素优化
    if config.CALIBRATION_PARAMS['corner_refinement']:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        charuco_corners = cv2.cornerSubPix(
            gray,
            charuco_corners,
            config.CALIBRATION_PARAMS['corner_win_size'],
            (-1, -1),
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        )

    # 估计标定板位姿
    success, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
        charuco_corners,
        charuco_ids,
        board,
        camera_matrix,
        dist_coeffs,
        None,
        None
    )

    if not success:
        return None, None, None

    return charuco_corners, charuco_ids, (rvec, tvec)

def calibrate_from_poses(
    robot_poses: List[np.ndarray],
    board_poses_in_camera: List[np.ndarray],
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray
) -> Optional[np.ndarray]:
    """
    从位姿数据执行手眼标定

    这是标定的核心函数，需要正确处理 Eye-in-Hand 和 Eye-to-Hand 两种模式。

    数学原理:
    --------
    Eye-in-Hand 模式:
        AX = XB
        其中:
        - A = T_base_to_flange (机器人运动)
        - B = T_camera_to_board (标定板在相机中的位姿)
        - X = T_flange_to_camera (要求解的手眼矩阵)

    Eye-to-Hand 模式:
        AX = ZB
        其中:
        - A = T_base_to_flange (机器人运动)
        - B = T_flange_to_board (标定板相对法兰的位姿，通常固定)
        - X = T_base_to_camera (要求解的眼到手矩阵)
        - Z = T_camera_to_board (标定板在相机中的位姿)

    OpenCV 的 calibrateHandEye 函数:
        输入: R_gripper2base[], t_gripper2base[], R_target2cam[], t_target2cam[]
        输出: R_cam2gripper, t_cam2gripper (Eye-in-Hand)
              或 R_cam2base, t_cam2base (Eye-to-Hand)

    Args:
        robot_poses: 机器人位姿列表 (T_base_to_flange)
        board_poses_in_camera: 标定板在相机中的位姿列表 (T_camera_to_board)
        camera_matrix: 相机内参
        dist_coeffs: 畸变系数

    Returns:
        np.ndarray: 标定结果矩阵 (4x4)
    """
    print(f"\n开始标定解算...")
    print(f"  模式: {config.CALIBRATION_MODE}")
    print(f"  数据组数: {len(robot_poses)}")

    # 准备 OpenCV 输入数据
    R_gripper2base = []
    t_gripper2base = []
    R_target2cam = []
    t_target2cam = []

    for i, (T_base_to_flange, T_camera_to_board) in enumerate(
        zip(robot_poses, board_poses_in_camera)
    ):
        # =====================================================================
        # 关键数学转换：根据标定模式准备数据
        # =====================================================================

        # 重要发现：OpenCV 的命名约定可能与直觉相反！
        # 根据实际测试，R_gripper2base 实际上是 T_base_to_gripper（机器人位姿）
        # 而不是 T_gripper_to_base（其逆）

        if config.CALIBRATION_MODE == 'eye_in_hand':
            # Eye-in-Hand 模式
            # 直接使用机器人位姿，不求逆
            T_gripper2base = T_base_to_flange  # 注意：这里不求逆！

            # 标定板在相机中的位姿也不求逆
            T_target2cam = T_camera_to_board  # 注意：这里也不求逆！

        else:  # eye_to_hand
            # Eye-to-Hand 模式
            T_gripper2base = T_base_to_flange
            T_target2cam = T_camera_to_board

        # 提取旋转和平移
        R_gripper2base.append(T_gripper2base[:3, :3])
        t_gripper2base.append(T_gripper2base[:3, 3].reshape(3, 1))
        R_target2cam.append(T_target2cam[:3, :3])
        t_target2cam.append(T_target2cam[:3, 3].reshape(3, 1))

    # 调用 OpenCV 手眼标定
    try:
        # 调试：打印第一组输入数据
        print(f"\n调试 - OpenCV 输入数据（第一组）:")
        print(f"R_gripper2base[0]:\n{R_gripper2base[0]}")
        print(f"t_gripper2base[0]: {t_gripper2base[0].T}")
        print(f"R_target2cam[0]:\n{R_target2cam[0]}")
        print(f"t_target2cam[0]: {t_target2cam[0].T}\n")

        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            R_gripper2base,
            t_gripper2base,
            R_target2cam,
            t_target2cam,
            method=config.CALIBRATION_PARAMS['method']
        )

        # 调试：打印 OpenCV 的原始输出
        T_cam2gripper_raw = np.eye(4)
        T_cam2gripper_raw[:3, :3] = R_cam2gripper
        T_cam2gripper_raw[:3, 3] = t_cam2gripper.flatten()
        print(f"OpenCV 原始输出 (T_cam2gripper):\n{T_cam2gripper_raw}\n")

        # 构建结果矩阵
        # 注意：OpenCV 返回的就是我们需要的矩阵，不需要求逆！
        result_matrix = np.eye(4)
        result_matrix[:3, :3] = R_cam2gripper
        result_matrix[:3, 3] = t_cam2gripper.flatten()

        print(f"✓ 标定完成")

        return result_matrix

    except Exception as e:
        print(f"✗ 标定失败: {e}")
        return None

def calibrate_from_images():
    """
    从保存的图像和位姿数据执行标定
    """
    print("\n" + "="*70)
    print("标定解算模式")
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

    # 加载图像并检测角点
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"✗ 未找到图像文件")
        return

    print(f"✓ 找到 {len(image_files)} 张图像")
    print(f"\n检测 ChArUco 角点...")

    board_poses_in_camera = []
    valid_robot_poses = []

    for i, image_file in enumerate(image_files):
        image = cv2.imread(str(image_file))

        # 检测角点
        corners, ids, pose = detect_charuco_corners(image, camera_matrix, dist_coeffs)

        if pose is not None:
            rvec, tvec = pose
            T_camera_to_board = rvec_tvec_to_matrix(rvec, tvec)
            board_poses_in_camera.append(T_camera_to_board)
            valid_robot_poses.append(robot_poses[i])
            print(f"  图像 {i+1}: ✓ 检测到 {len(corners)} 个角点")
        else:
            print(f"  图像 {i+1}: ✗ 检测失败")

    print(f"\n有效数据组数: {len(valid_robot_poses)}")

    if len(valid_robot_poses) < config.CALIBRATION_PARAMS['min_samples']:
        print(f"✗ 有效数据不足，需要至少 {config.CALIBRATION_PARAMS['min_samples']} 组")
        return

    # 执行标定
    result_matrix = calibrate_from_poses(
        valid_robot_poses,
        board_poses_in_camera,
        camera_matrix,
        dist_coeffs
    )

    if result_matrix is not None:
        # 保存结果
        np.save(config.PATHS['result_matrix_file'], result_matrix)

        # 保存为 JSON（便于查看）
        result_dict = {
            'mode': config.CALIBRATION_MODE,
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

# =============================================================================
# 主程序入口
# =============================================================================

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="手眼标定系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  simulate  - 纯软件仿真验证（无需硬件）
  collect   - 真实数据采集（需要相机和机器人）
  calibrate - 标定解算（从已采集的数据）

示例:
  python main.py --mode simulate
  python main.py --mode collect
  python main.py --mode calibrate
        """
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['simulate', 'collect', 'calibrate'],
        default='simulate',
        help='运行模式'
    )

    args = parser.parse_args()

    # 打印配置
    config.print_config()

    # 根据模式执行
    if args.mode == 'simulate':
        simulate_and_verify()

    elif args.mode == 'collect':
        print("⚠️ 数据采集模式需要实现机器人接口")
        print("请在 robot_interface.py 中实现你的机器人类，然后:")
        print("  from robot_interface import YourRobotClass")
        print("  robot = YourRobotClass()")
        print("  collector = DataCollector(robot)")
        print("  collector.collect()")

    elif args.mode == 'calibrate':
        calibrate_from_images()

if __name__ == "__main__":
    main()
