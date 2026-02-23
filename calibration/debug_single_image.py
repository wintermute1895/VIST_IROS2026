"""
单张图像调试工具
===============
逐张查看图像的检测情况，分析失败原因和重投影误差

使用方法:
    python debug_single_image.py [图像编号]
    例如: python debug_single_image.py 0  # 查看第一张图像
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from typing import Optional, Tuple

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import config
from robot_interface import rvec_tvec_to_matrix, matrix_to_rvec_tvec

def detect_and_visualize(image_path: str, robot_pose: np.ndarray,
                        camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
    """检测并可视化单张图像"""

    image = cv2.imread(image_path)
    if image is None:
        print(f"✗ 无法读取图像: {image_path}")
        return

    print(f"\n{'='*70}")
    print(f"图像: {Path(image_path).name}")
    print(f"{'='*70}")

    # 获取 ChArUco 板
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 检测 ArUco 标记
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    # 可视化图像
    vis_image = image.copy()

    print(f"\nArUco 标记检测:")
    if ids is not None:
        print(f"  检测到 {len(ids)} 个 ArUco 标记")
        print(f"  标记 ID: {ids.flatten().tolist()}")
        # 绘制检测到的标记
        cv2.aruco.drawDetectedMarkers(vis_image, corners, ids)
    else:
        print(f"  ✗ 未检测到任何 ArUco 标记")
        print(f"  可能原因:")
        print(f"    - 光照不足")
        print(f"    - 标定板距离太远")
        print(f"    - 标定板角度太倾斜")
        print(f"    - 图像模糊")

    if rejected is not None and len(rejected) > 0:
        print(f"  拒绝的候选: {len(rejected)} 个")

    # 检测 ChArUco 角点
    if ids is not None and len(ids) >= 4:
        charuco_detector = cv2.aruco.CharucoDetector(board)
        charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image)

        print(f"\nChArUco 角点检测:")
        if charuco_corners is not None and len(charuco_corners) >= 4:
            print(f"  ✓ 检测到 {len(charuco_corners)} 个角点")
            print(f"  角点 ID: {charuco_ids.flatten().tolist()}")

            # 绘制角点
            cv2.aruco.drawDetectedCornersCharuco(vis_image, charuco_corners, charuco_ids)

            # 估计位姿
            obj_points = board.getChessboardCorners()[charuco_ids.flatten()]
            success, rvec, tvec = cv2.solvePnP(
                obj_points,
                charuco_corners,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

            if success:
                print(f"\n位姿估计:")
                print(f"  ✓ 成功")
                print(f"  平移 (m): [{tvec[0][0]:.4f}, {tvec[1][0]:.4f}, {tvec[2][0]:.4f}]")
                print(f"  距离: {np.linalg.norm(tvec):.4f} m")

                # 绘制坐标轴
                axis_length = config.CHARUCO_CONFIG['square_size'] * 2
                cv2.drawFrameAxes(vis_image, camera_matrix, dist_coeffs,
                                rvec, tvec, axis_length)

                # 计算重投影误差
                reprojected, _ = cv2.projectPoints(
                    obj_points, rvec, tvec, camera_matrix, dist_coeffs
                )

                detected_pts = charuco_corners.reshape(-1, 2)
                reprojected_pts = reprojected.reshape(-1, 2)
                errors = np.linalg.norm(detected_pts - reprojected_pts, axis=1)

                print(f"\n重投影误差:")
                print(f"  平均: {np.mean(errors):.2f} px")
                print(f"  最大: {np.max(errors):.2f} px")
                print(f"  最小: {np.min(errors):.2f} px")
                print(f"  标准差: {np.std(errors):.2f} px")

                # 在图像上绘制误差
                for i, (det_pt, repr_pt, error) in enumerate(zip(detected_pts, reprojected_pts, errors)):
                    det_pt = tuple(det_pt.astype(int))
                    repr_pt = tuple(repr_pt.astype(int))

                    # 绘制检测点（绿色）
                    cv2.circle(vis_image, det_pt, 5, (0, 255, 0), 2)
                    # 绘制重投影点（红色）
                    cv2.drawMarker(vis_image, repr_pt, (0, 0, 255),
                                  cv2.MARKER_CROSS, 10, 2)
                    # 连线
                    cv2.line(vis_image, det_pt, repr_pt, (255, 0, 0), 1)
                    # 显示误差
                    cv2.putText(vis_image, f"{error:.1f}",
                              (det_pt[0]+10, det_pt[1]-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

                # 显示平均误差
                cv2.putText(vis_image, f"Mean Error: {np.mean(errors):.2f} px",
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

                # 显示详细误差列表
                print(f"\n各角点误差 (px):")
                for i, error in enumerate(errors):
                    print(f"  角点 {charuco_ids[i][0]}: {error:.2f}")
            else:
                print(f"  ✗ 位姿估计失败")
        else:
            print(f"  ✗ 角点数量不足 (需要至少4个)")
            if charuco_corners is not None:
                print(f"  检测到 {len(charuco_corners)} 个角点")
    else:
        print(f"\nChArUco 角点检测:")
        print(f"  ✗ ArUco 标记数量不足 (需要至少4个)")

    # 显示图像信息
    print(f"\n图像信息:")
    print(f"  尺寸: {image.shape[1]}x{image.shape[0]}")
    print(f"  亮度: 平均={np.mean(image):.1f}, 标准差={np.std(image):.1f}")

    # 检查图像质量
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    print(f"  清晰度 (Laplacian方差): {laplacian_var:.2f}")
    if laplacian_var < 100:
        print(f"    ⚠️ 图像可能模糊")

    print(f"{'='*70}\n")

    # 显示图像
    cv2.imshow("Debug View", vis_image)
    print("按任意键继续，按 'q' 退出...")
    key = cv2.waitKey(0)
    cv2.destroyAllWindows()

    return key != ord('q')

def main():
    """主函数"""
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

    # 加载机器人位姿
    if not config.PATHS['poses_file'].exists():
        print(f"✗ 未找到位姿文件: {config.PATHS['poses_file']}")
        return

    robot_poses = np.load(config.PATHS['poses_file'])

    # 加载图像
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"✗ 未找到图像文件")
        return

    print(f"✓ 找到 {len(image_files)} 张图像")

    # 如果指定了图像编号
    if len(sys.argv) > 1:
        try:
            idx = int(sys.argv[1])
            if 0 <= idx < len(image_files):
                detect_and_visualize(
                    str(image_files[idx]),
                    robot_poses[idx],
                    camera_matrix,
                    dist_coeffs
                )
            else:
                print(f"✗ 图像编号超出范围 (0-{len(image_files)-1})")
        except ValueError:
            print(f"✗ 无效的图像编号")
    else:
        # 逐张查看所有图像
        print("\n开始逐张查看图像...")
        for i, image_file in enumerate(image_files):
            if i >= len(robot_poses):
                break

            should_continue = detect_and_visualize(
                str(image_file),
                robot_poses[i],
                camera_matrix,
                dist_coeffs
            )

            if not should_continue:
                print("用户退出")
                break

if __name__ == "__main__":
    main()
