#!/usr/bin/env python3
"""
使用ChArUco板标定相机内参
"""
import cv2
import numpy as np
import pyrealsense2 as rs
from pathlib import Path
import config

print("="*70)
print("相机内参标定")
print("="*70)
print("\n操作说明:")
print("  1. 将ChArUco板放在不同位置和角度")
print("  2. 按空格键采集图像（需要15-20张）")
print("  3. 按q键完成采集并开始标定")
print("="*70 + "\n")

# 初始化相机
pipeline = rs.pipeline()
rs_config = rs.config()
rs_config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
profile = pipeline.start(rs_config)

print("等待相机预热...")
import time
time.sleep(2)  # 相机预热时间
print("✓ 相机就绪\n")

# 准备ChArUco板
board = config.get_charuco_board()
charuco_detector = cv2.aruco.CharucoDetector(board)

# 存储角点
all_corners = []
all_ids = []
image_size = None

print("开始采集标定图像...")
collected = 0

try:
    while True:
        frames = pipeline.wait_for_frames(timeout_ms=5000)
        color_frame = frames.get_color_frame()
        if not color_frame:
            continue
        
        image = np.asanyarray(color_frame.get_data())
        image_size = (image.shape[1], image.shape[0])
        display = image.copy()
        
        # 检测ChArUco角点
        charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(image)
        
        if charuco_corners is not None and len(charuco_corners) > 4:
            cv2.aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids)
            cv2.putText(display, f"Detected: {len(charuco_corners)} corners", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.putText(display, f"Collected: {collected}/20 | Space: capture, Q: done",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow("Camera Calibration", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord(' '):  # 空格键采集
            if charuco_corners is not None and len(charuco_corners) > 4:
                all_corners.append(charuco_corners)
                all_ids.append(charuco_ids)
                collected += 1
                print(f"✓ 采集第 {collected} 张图像 ({len(charuco_corners)} 个角点)")
            else:
                print("✗ 未检测到足够的角点")
        
        elif key == ord('q'):  # q键退出
            break

finally:
    pipeline.stop()
    cv2.destroyAllWindows()

if collected < 10:
    print(f"\n✗ 图像不足，需要至少10张，当前只有{collected}张")
    exit(1)

print(f"\n开始标定 (使用{collected}张图像)...")

# 执行标定
ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
    all_corners, all_ids, board, image_size, None, None
)

print("\n" + "="*70)
print("标定结果")
print("="*70)
print(f"\n相机矩阵:")
print(camera_matrix)
print(f"\n畸变系数:")
print(dist_coeffs)

# 计算重投影误差
total_error = 0
for i in range(len(all_corners)):
    obj_points = board.getChessboardCorners()[all_ids[i].flatten()]
    img_points2, _ = cv2.projectPoints(obj_points, rvecs[i], tvecs[i], 
                                       camera_matrix, dist_coeffs)
    error = cv2.norm(all_corners[i], img_points2, cv2.NORM_L2) / len(all_corners[i])
    total_error += error

mean_error = total_error / len(all_corners)
print(f"\n平均重投影误差: {mean_error:.3f} 像素")

if mean_error < 1.0:
    print("✓ 标定质量: 优秀")
elif mean_error < 2.0:
    print("✓ 标定质量: 良好")
else:
    print("⚠ 标定质量: 一般，建议重新标定")

# 保存结果
output_dir = Path("calibration_data/camera_intrinsics")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "d405_calibrated.npz"

np.savez(output_file, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)
print(f"\n✓ 标定结果已保存到: {output_file}")
