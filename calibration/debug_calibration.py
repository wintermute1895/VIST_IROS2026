#!/usr/bin/env python3
"""
详细调试标定过程中的每一步数据
"""
import numpy as np
import cv2
from pathlib import Path
import config
from robot_interface import rvec_tvec_to_matrix

# 加载数据
data_dir = Path("calibration_data")
robot_poses = np.load(data_dir / "robot_poses.npy")
intrinsics = np.load(data_dir / "camera_intrinsics.npz")
camera_matrix = intrinsics['camera_matrix']
dist_coeffs = intrinsics['dist_coeffs']

print("="*70)
print("详细调试标定数据")
print("="*70)
print()

# 检查第一张图像
image_path = data_dir / "images" / "image_000.png"
image = cv2.imread(str(image_path))

print(f"图像 0:")
print(f"  路径: {image_path}")
print(f"  尺寸: {image.shape}")
print()

# 检测ChArUco角点
board = config.get_charuco_board()
charuco_detector = cv2.aruco.CharucoDetector(board)
charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image)

print(f"  检测到 {len(charuco_corners)} 个ChArUco角点")
print(f"  角点ID: {charuco_ids.flatten()[:10]}...")  # 只打印前10个
print()

# 估计标定板位姿
obj_points = board.getChessboardCorners()[charuco_ids.flatten()]
success, rvec, tvec = cv2.solvePnP(
    obj_points, charuco_corners, camera_matrix, dist_coeffs,
    flags=cv2.SOLVEPNP_ITERATIVE
)

print(f"  PnP求解: {'成功' if success else '失败'}")
print(f"  rvec: {rvec.flatten()}")
print(f"  tvec: {tvec.flatten()}")
print()

# 转换为4x4矩阵
T_camera_to_board = rvec_tvec_to_matrix(rvec, tvec)
print(f"  T_camera_to_board (标定板在相机坐标系中的位姿):")
print(T_camera_to_board)
print()

# 机器人位姿
T_base_to_flange = robot_poses[0]
print(f"  T_base_to_flange (机器人末端在基座坐标系中的位姿):")
print(T_base_to_flange)
print()

# 检查坐标系关系
print("="*70)
print("坐标系关系检查")
print("="*70)
print()

print("Eye-in-Hand 标定的数学关系:")
print("  AX = XB")
print("  其中:")
print("    A = T_base_to_flange (机器人运动)")
print("    X = T_flange_to_camera (要求解的手眼矩阵)")
print("    B = T_camera_to_board (标定板在相机中的位姿)")
print()

print("OpenCV calibrateHandEye 的输入:")
print("  R_gripper2base, t_gripper2base")
print("  R_target2cam, t_target2cam")
print()

print("我们传入的数据:")
print(f"  R_gripper2base = T_base_to_flange[:3,:3]")
print(f"  t_gripper2base = T_base_to_flange[:3,3]")
print(f"  R_target2cam = T_camera_to_board[:3,:3]")
print(f"  t_target2cam = T_camera_to_board[:3,3]")
print()

# 检查标定板尺寸
print("="*70)
print("ChArUco板配置")
print("="*70)
print(f"  方格尺寸: {config.CHARUCO_CONFIG['square_size']} 米 ({config.CHARUCO_CONFIG['square_size']*1000} 毫米)")
print(f"  标记尺寸: {config.CHARUCO_CONFIG['marker_size']} 米 ({config.CHARUCO_CONFIG['marker_size']*1000} 毫米)")
print()

# 检查标定板在相机中的距离
board_distance = np.linalg.norm(tvec)
print(f"  标定板到相机的距离: {board_distance:.3f} 米 ({board_distance*1000:.1f} 毫米)")
print()

# 检查标定板的3D点
print("="*70)
print("标定板3D点检查 (前5个)")
print("="*70)
for i in range(min(5, len(obj_points))):
    print(f"  点 {charuco_ids[i][0]}: {obj_points[i]}")
print()

# 重投影检查
projected_points, _ = cv2.projectPoints(
    obj_points, rvec, tvec, camera_matrix, dist_coeffs
)
errors = np.linalg.norm(charuco_corners - projected_points.reshape(-1, 2), axis=1)
print(f"  单张图像重投影误差: {errors.mean():.2f} ± {errors.std():.2f} 像素")
print(f"  最大误差: {errors.max():.2f} 像素")
print()

print("="*70)
print("结论")
print("="*70)
if errors.mean() < 2:
    print("✓ 单张图像的PnP估计是准确的")
    print("  问题可能在于:")
    print("  1. 机器人位姿数据不准确")
    print("  2. 标定算法的输入格式不对")
    print("  3. 坐标系定义有误")
else:
    print("✗ 单张图像的PnP估计就有问题")
    print("  可能原因:")
    print("  1. ChArUco板尺寸配置错误")
    print("  2. 相机内参不准确")
    print("  3. 标定板不平整")
print()