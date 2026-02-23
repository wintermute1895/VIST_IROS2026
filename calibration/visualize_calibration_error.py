"""
可视化标定重投影误差
===================
加载标定结果，在每张图像上绘制检测点和重投影点，显示像素误差

使用方法:
    python visualize_calibration_error.py
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from typing import List, Tuple, Optional

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import config
from robot_interface import rvec_tvec_to_matrix, matrix_to_rvec_tvec

def detect_corners(image, camera_matrix, dist_coeffs):
    """检测ChArUco角点或单个标记"""
    if config.MARKER_TYPE == 'charuco':
        return detect_charuco_corners(image, camera_matrix, dist_coeffs)
    else:
        return detect_single_marker(image, camera_matrix, dist_coeffs)

def detect_charuco_corners(image, camera_matrix, dist_coeffs):
    """检测ChArUco角点"""
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    if ids is None or len(ids) < 4:
        return None, None, None

    charuco_detector = cv2.aruco.CharucoDetector(board)
    charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image)

    if charuco_corners is None or len(charuco_corners) < 4:
        return None, None, None

    # 获取3D点
    obj_points = board.getChessboardCorners()[charuco_ids.flatten()]

    return charuco_corners, charuco_ids, obj_points

def detect_single_marker(image, camera_matrix, dist_coeffs):
    """检测单个标记"""
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.SINGLE_MARKER_CONFIG['dict_type'])

    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    if ids is None or len(ids) == 0:
        return None, None, None

    target_id = config.SINGLE_MARKER_CONFIG['marker_id']
    marker_idx = None
    for i, marker_id in enumerate(ids):
        if marker_id[0] == target_id:
            marker_idx = i
            break

    if marker_idx is None:
        return None, None, None

    marker_corners = corners[marker_idx][0]

    # 定义标记的3D坐标
    marker_size = config.SINGLE_MARKER_CONFIG['marker_size']
    half_size = marker_size / 2.0
    obj_points = np.array([
        [-half_size, half_size, 0],
        [half_size, half_size, 0],
        [half_size, -half_size, 0],
        [-half_size, -half_size, 0]
    ], dtype=np.float32)

    # 创建伪ID（用于显示）
    ids = np.array([[0], [1], [2], [3]])

    return marker_corners.reshape(-1, 1, 2), ids, obj_points

def compute_reprojection_error(
    image: np.ndarray,
    robot_pose: np.ndarray,
    hand_eye_matrix: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray
) -> Tuple[Optional[np.ndarray], Optional[float], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    计算重投影误差

    Returns:
        (visualization_image, mean_error, detected_corners, reprojected_corners)
    """
    # 检测角点
    detected_corners, corner_ids, obj_points_3d = detect_corners(image, camera_matrix, dist_coeffs)

    if detected_corners is None:
        return None, None, None, None

    # 根据标定模式计算标定板在相机中的位姿
    if config.CALIBRATION_MODE == 'eye_in_hand':
        # Eye-in-Hand: T_camera_to_board = T_flange_to_camera^-1 * T_base_to_flange^-1 * T_base_to_board
        # 但我们不知道T_base_to_board，所以使用检测到的位姿
        # 实际上，我们应该用检测到的T_camera_to_board来验证

        # 使用solvePnP获取检测到的标定板位姿
        success, rvec_detected, tvec_detected = cv2.solvePnP(
            obj_points_3d,
            detected_corners,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return None, None, None, None

        # 重投影
        reprojected_corners, _ = cv2.projectPoints(
            obj_points_3d,
            rvec_detected,
            tvec_detected,
            camera_matrix,
            dist_coeffs
        )

    else:  # eye_to_hand
        # Eye-to-Hand: T_camera_to_marker = T_base_to_camera^-1 * T_base_to_flange * T_flange_to_marker
        # 其中 T_base_to_camera 是手眼矩阵
        # T_flange_to_marker 是固定的（标记贴在手上）

        # 使用solvePnP获取检测到的标记位姿
        success, rvec_detected, tvec_detected = cv2.solvePnP(
            obj_points_3d,
            detected_corners,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return None, None, None, None

        # 重投影
        reprojected_corners, _ = cv2.projectPoints(
            obj_points_3d,
            rvec_detected,
            tvec_detected,
            camera_matrix,
            dist_coeffs
        )

    # 计算误差
    detected_corners = detected_corners.reshape(-1, 2)
    reprojected_corners = reprojected_corners.reshape(-1, 2)

    errors = np.linalg.norm(detected_corners - reprojected_corners, axis=1)
    mean_error = np.mean(errors)

    # 可视化
    vis_image = image.copy()

    for i in range(len(detected_corners)):
        detected_pt = tuple(detected_corners[i].astype(int))
        reprojected_pt = tuple(reprojected_corners[i].astype(int))
        error = errors[i]

        # 绘制检测点（绿色圆圈）
        cv2.circle(vis_image, detected_pt, 5, (0, 255, 0), 2)

        # 绘制重投影点（红色叉）
        cv2.drawMarker(vis_image, reprojected_pt, (0, 0, 255),
                      cv2.MARKER_CROSS, 10, 2)

        # 绘制连线
        cv2.line(vis_image, detected_pt, reprojected_pt, (255, 0, 0), 1)

        # 显示误差值
        text_pos = (detected_pt[0] + 10, detected_pt[1] - 10)
        cv2.putText(vis_image, f"{error:.2f}px", text_pos,
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    # 显示平均误差
    cv2.putText(vis_image, f"Mean Error: {mean_error:.2f} px",
               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    return vis_image, mean_error, detected_corners, reprojected_corners

def main():
    """主函数"""
    print("\n" + "="*70)
    print("标定重投影误差可视化")
    print("="*70)

    # 加载标定结果
    if not config.PATHS['result_matrix_file'].exists():
        print(f"✗ 未找到标定结果: {config.PATHS['result_matrix_file']}")
        print("  请先运行标定")
        return

    hand_eye_matrix = np.load(config.PATHS['result_matrix_file'])
    print(f"✓ 加载标定结果")
    print(f"  模式: {config.CALIBRATION_MODE}")

    # 加载机器人位姿
    if not config.PATHS['poses_file'].exists():
        print(f"✗ 未找到位姿文件: {config.PATHS['poses_file']}")
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

    # 加载图像
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"✗ 未找到图像文件")
        return

    print(f"✓ 找到 {len(image_files)} 张图像")

    # 创建输出目录
    output_dir = config.PATHS['data_dir'] / "reprojection_visualization"
    output_dir.mkdir(exist_ok=True)

    print(f"\n处理图像...")

    all_errors = []
    valid_count = 0

    for i, image_file in enumerate(image_files):
        if i >= len(robot_poses):
            break

        image = cv2.imread(str(image_file))
        robot_pose = robot_poses[i]

        vis_image, mean_error, detected, reprojected = compute_reprojection_error(
            image, robot_pose, hand_eye_matrix, camera_matrix, dist_coeffs
        )

        if vis_image is not None:
            # 保存可视化结果
            output_path = output_dir / f"reprojection_{i:03d}.png"
            cv2.imwrite(str(output_path), vis_image)

            all_errors.append(mean_error)
            valid_count += 1

            print(f"  图像 {i+1}: 平均误差 {mean_error:.2f} px")
        else:
            print(f"  图像 {i+1}: 检测失败")

    # 统计
    if len(all_errors) > 0:
        print(f"\n" + "="*70)
        print("误差统计")
        print("="*70)
        print(f"有效图像数: {valid_count}/{len(image_files)}")
        print(f"平均重投影误差: {np.mean(all_errors):.2f} px")
        print(f"最大重投影误差: {np.max(all_errors):.2f} px")
        print(f"最小重投影误差: {np.min(all_errors):.2f} px")
        print(f"标准差: {np.std(all_errors):.2f} px")
        print(f"\n✓ 可视化结果已保存到: {output_dir}")
        print("="*70 + "\n")
    else:
        print("\n⚠️ 没有有效的图像")

if __name__ == "__main__":
    main()