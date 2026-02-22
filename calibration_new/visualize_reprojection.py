#!/usr/bin/env python3
"""
可视化标定结果和重投影误差
"""
import cv2
import numpy as np
import config
from pathlib import Path

# 加载数据
data_dir = Path("calibration_data")
poses = np.load(data_dir / "robot_poses.npy")
intrinsics = np.load(data_dir / "camera_intrinsics.npz")
camera_matrix = intrinsics['camera_matrix']
dist_coeffs = intrinsics['dist_coeffs']
T_cam2gripper = np.load(data_dir / "hand_eye_matrix.npy")

# 获取ChArUco板
board = config.get_charuco_board()
charuco_detector = cv2.aruco.CharucoDetector(board)

print("可视化前3张图像的重投影误差...")
print()

for i in range(min(3, len(poses))):
    # 加载图像
    image_path = data_dir / "images" / f"image_{i:03d}.png"
    image = cv2.imread(str(image_path))

    # 检测ChArUco角点
    charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image)

    if charuco_corners is None or len(charuco_corners) < 4:
        print(f"图像 {i}: 角点不足")
        continue

    # 获取机器人位姿
    T_gripper2base = poses[i]

    # 计算标定板在相机坐标系中的位姿
    # T_target2cam = T_cam2gripper^-1 * T_gripper2base^-1
    T_cam2base = T_gripper2base @ T_cam2gripper
    T_target2cam_pred = np.linalg.inv(T_cam2base)  # 假设标定板在base坐标系原点

    # 实际上我们需要从图像中估计T_target2cam
    obj_points = board.getChessboardCorners()[charuco_ids.flatten()]
    success, rvec_actual, tvec_actual = cv2.solvePnP(
        obj_points, charuco_corners, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        print(f"图像 {i}: PnP求解失败")
        continue

    # 重投影
    projected_points, _ = cv2.projectPoints(
        obj_points, rvec_actual, tvec_actual, camera_matrix, dist_coeffs
    )

    # 计算误差
    errors = np.linalg.norm(charuco_corners - projected_points.reshape(-1, 2), axis=1)

    print(f"图像 {i}:")
    print(f"  检测到 {len(charuco_corners)} 个角点")
    print(f"  平均重投影误差: {errors.mean():.2f} 像素")
    print(f"  最大重投影误差: {errors.max():.2f} 像素")

    # 在图像上绘制
    vis_image = image.copy()

    # 绘制检测到的角点（绿色）
    for corner in charuco_corners:
        cv2.circle(vis_image, tuple(corner[0].astype(int)), 5, (0, 255, 0), -1)

    # 绘制重投影点（红色）
    for point in projected_points:
        cv2.circle(vis_image, tuple(point[0].astype(int)), 3, (0, 0, 255), -1)

    # 绘制连线
    for j in range(len(charuco_corners)):
        pt1 = tuple(charuco_corners[j][0].astype(int))
        pt2 = tuple(projected_points[j][0].astype(int))
        cv2.line(vis_image, pt1, pt2, (255, 0, 0), 1)

    # 保存可视化结果
    output_path = data_dir / f"reprojection_vis_{i:03d}.png"
    cv2.imwrite(str(output_path), vis_image)
    print(f"  可视化已保存到: {output_path}")
    print()

print("✓ 可视化完成")