#!/usr/bin/env python3
"""
标定误差分析脚本
================
计算手眼标定的重投影误差和其他质量指标
"""

import numpy as np
import cv2
import json
from pathlib import Path
import config


def load_calibration_data():
    """加载标定数据"""
    # 加载标定结果
    hand_eye_matrix = np.load(config.PATHS['result_matrix_file'])

    # 加载机器人位姿
    robot_poses = np.load(config.PATHS['poses_file'])

    # 加载相机内参
    intrinsics_file = config.PATHS['data_dir'] / "camera_intrinsics.npz"
    data = np.load(intrinsics_file)
    camera_matrix = data['camera_matrix']
    dist_coeffs = data['dist_coeffs']

    return hand_eye_matrix, robot_poses, camera_matrix, dist_coeffs


def detect_board_pose(image, camera_matrix, dist_coeffs):
    """检测标定板位姿"""
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 检测 ArUco 标记
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    if ids is None or len(ids) < 4:
        return None, None

    # 检测 ChArUco 角点
    charuco_detector = cv2.aruco.CharucoDetector(board)
    charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(image)

    if charuco_corners is None or len(charuco_corners) < 4:
        return None, None

    # 估计位姿
    obj_points = board.getChessboardCorners()[charuco_ids.flatten()]
    success, rvec, tvec = cv2.solvePnP(
        obj_points,
        charuco_corners,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return None, None

    return rvec, tvec, charuco_corners, charuco_ids, obj_points


def calculate_reprojection_error(hand_eye_matrix, robot_poses, camera_matrix, dist_coeffs):
    """计算重投影误差"""
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    errors = []
    valid_count = 0

    print("\n" + "="*70)
    print("重投影误差分析")
    print("="*70)

    for i, (image_file, robot_pose) in enumerate(zip(image_files, robot_poses)):
        image = cv2.imread(str(image_file))

        # 检测标定板
        result = detect_board_pose(image, camera_matrix, dist_coeffs)
        if result is None:
            print(f"图像 {i+1}: 检测失败")
            continue

        rvec, tvec, charuco_corners, charuco_ids, obj_points = result

        # 重投影
        projected_points, _ = cv2.projectPoints(
            obj_points,
            rvec,
            tvec,
            camera_matrix,
            dist_coeffs
        )

        # 计算误差
        error = np.sqrt(np.sum((charuco_corners - projected_points.reshape(-1, 2))**2, axis=1))
        mean_error = np.mean(error)
        max_error = np.max(error)

        errors.append(mean_error)
        valid_count += 1

        print(f"图像 {i+1}: 平均误差 = {mean_error:.3f} 像素, 最大误差 = {max_error:.3f} 像素")

    if errors:
        overall_mean = np.mean(errors)
        overall_std = np.std(errors)
        overall_max = np.max(errors)

        print("\n" + "-"*70)
        print(f"总体统计 ({valid_count} 张图像):")
        print(f"  平均重投影误差: {overall_mean:.3f} ± {overall_std:.3f} 像素")
        print(f"  最大重投影误差: {overall_max:.3f} 像素")
        print("="*70)

        return overall_mean, overall_std, overall_max
    else:
        print("\n⚠️ 没有有效的图像用于误差计算")
        return None, None, None


def analyze_calibration_result(hand_eye_matrix):
    """分析标定结果"""
    print("\n" + "="*70)
    print("标定结果分析")
    print("="*70)

    # 提取平移和旋转
    translation = hand_eye_matrix[:3, 3]
    rotation_matrix = hand_eye_matrix[:3, :3]

    # 转换为欧拉角
    from scipy.spatial.transform import Rotation as R
    rotation = R.from_matrix(rotation_matrix)
    euler_angles = rotation.as_euler('xyz', degrees=True)

    print(f"\n平移 (T_flange_to_camera):")
    print(f"  X: {translation[0]:.6f} 米 ({translation[0]*1000:.2f} 毫米)")
    print(f"  Y: {translation[1]:.6f} 米 ({translation[1]*1000:.2f} 毫米)")
    print(f"  Z: {translation[2]:.6f} 米 ({translation[2]*1000:.2f} 毫米)")
    print(f"  距离: {np.linalg.norm(translation):.6f} 米 ({np.linalg.norm(translation)*1000:.2f} 毫米)")

    print(f"\n旋转 (欧拉角 XYZ):")
    print(f"  Roll:  {euler_angles[0]:.2f}°")
    print(f"  Pitch: {euler_angles[1]:.2f}°")
    print(f"  Yaw:   {euler_angles[2]:.2f}°")

    # 检查旋转矩阵的正交性
    orthogonality_error = np.linalg.norm(rotation_matrix @ rotation_matrix.T - np.eye(3))
    print(f"\n旋转矩阵正交性误差: {orthogonality_error:.2e}")

    # 检查行列式（应该接近 1）
    det = np.linalg.det(rotation_matrix)
    print(f"旋转矩阵行列式: {det:.6f} (应该接近 1.0)")

    print("="*70)


def main():
    """主函数"""
    print("\n" + "="*70)
    print("手眼标定误差分析")
    print("="*70)

    try:
        # 加载数据
        hand_eye_matrix, robot_poses, camera_matrix, dist_coeffs = load_calibration_data()

        # 分析标定结果
        analyze_calibration_result(hand_eye_matrix)

        # 计算重投影误差
        mean_error, std_error, max_error = calculate_reprojection_error(
            hand_eye_matrix,
            robot_poses,
            camera_matrix,
            dist_coeffs
        )

        # 保存误差统计
        if mean_error is not None:
            error_stats = {
                'mean_reprojection_error_pixels': float(mean_error),
                'std_reprojection_error_pixels': float(std_error),
                'max_reprojection_error_pixels': float(max_error),
                'num_images': len(robot_poses)
            }

            error_file = config.PATHS['data_dir'] / "calibration_error_stats.json"
            with open(error_file, 'w') as f:
                json.dump(error_stats, f, indent=2)

            print(f"\n✓ 误差统计已保存到: {error_file}")

            # 评估标定质量
            print("\n" + "="*70)
            print("标定质量评估")
            print("="*70)
            if mean_error < 0.5:
                print("✓ 优秀：重投影误差 < 0.5 像素")
            elif mean_error < 1.0:
                print("✓ 良好：重投影误差 < 1.0 像素")
            elif mean_error < 2.0:
                print("⚠️ 可接受：重投影误差 < 2.0 像素")
            else:
                print("✗ 较差：重投影误差 >= 2.0 像素，建议重新标定")
            print("="*70)

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()