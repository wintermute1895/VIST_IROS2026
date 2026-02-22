"""
标定数据综合分析
===============
分析所有采集图像的质量、检测情况和误差来源

使用方法:
    python analyze_calibration_data.py
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

import config
from robot_interface import rvec_tvec_to_matrix

def analyze_image_quality(image: np.ndarray) -> Dict[str, Any]:
    """分析图像质量"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 亮度统计
    brightness_mean = np.mean(gray)
    brightness_std = np.std(gray)

    # 清晰度（Laplacian方差）
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 对比度
    contrast = gray.max() - gray.min()

    return {
        'brightness_mean': brightness_mean,
        'brightness_std': brightness_std,
        'sharpness': laplacian_var,
        'contrast': contrast,
        'is_blurry': laplacian_var < 100,
        'is_dark': brightness_mean < 80,
        'is_bright': brightness_mean > 180
    }

def detect_and_analyze(image: np.ndarray, camera_matrix: np.ndarray,
                      dist_coeffs: np.ndarray) -> Dict[str, Any]:
    """检测并分析单张图像"""

    result = {
        'aruco_detected': 0,
        'aruco_ids': [],
        'charuco_detected': 0,
        'charuco_ids': [],
        'detection_success': False,
        'reprojection_error_mean': None,
        'reprojection_error_max': None,
        'reprojection_error_std': None,
        'distance': None,
        'angle_x': None,
        'angle_y': None,
        'failure_reason': []
    }

    # 获取 ChArUco 板
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 检测 ArUco 标记
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    if ids is not None:
        result['aruco_detected'] = len(ids)
        result['aruco_ids'] = ids.flatten().tolist()
    else:
        result['failure_reason'].append('未检测到ArUco标记')
        return result

    if len(ids) < 4:
        result['failure_reason'].append(f'ArUco标记数量不足（{len(ids)}<4）')
        return result

    # 检测 ChArUco 角点
    charuco_detector = cv2.aruco.CharucoDetector(board)
    charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image)

    if charuco_corners is None or len(charuco_corners) < 4:
        result['failure_reason'].append(f'ChArUco角点数量不足')
        return result

    result['charuco_detected'] = len(charuco_corners)
    result['charuco_ids'] = charuco_ids.flatten().tolist()
    result['detection_success'] = True

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
        result['failure_reason'].append('位姿估计失败')
        return result

    # 计算距离
    result['distance'] = float(np.linalg.norm(tvec))

    # 计算角度（从旋转向量）
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    # 提取欧拉角（简化版）
    sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
    result['angle_x'] = float(np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180 / np.pi)
    result['angle_y'] = float(np.arctan2(-rotation_matrix[2,0], sy) * 180 / np.pi)

    # 计算重投影误差
    reprojected, _ = cv2.projectPoints(
        obj_points, rvec, tvec, camera_matrix, dist_coeffs
    )

    detected_pts = charuco_corners.reshape(-1, 2)
    reprojected_pts = reprojected.reshape(-1, 2)
    errors = np.linalg.norm(detected_pts - reprojected_pts, axis=1)

    result['reprojection_error_mean'] = float(np.mean(errors))
    result['reprojection_error_max'] = float(np.max(errors))
    result['reprojection_error_std'] = float(np.std(errors))
    result['reprojection_errors'] = errors.tolist()

    return result

def main():
    """主函数"""
    print("\n" + "="*70)
    print("标定数据综合分析")
    print("="*70)

    # 加载相机内参
    intrinsics_file = config.PATHS['data_dir'] / "camera_intrinsics.npz"
    if intrinsics_file.exists():
        data = np.load(intrinsics_file)
        camera_matrix = data['camera_matrix']
        dist_coeffs = data['dist_coeffs']
        print(f"\n相机内参:")
        print(f"  fx={camera_matrix[0,0]:.2f}, fy={camera_matrix[1,1]:.2f}")
        print(f"  cx={camera_matrix[0,2]:.2f}, cy={camera_matrix[1,2]:.2f}")
        print(f"  畸变系数: {dist_coeffs.flatten()}")
    else:
        camera_matrix = config.CAMERA_CONFIG['manual_intrinsics']['camera_matrix']
        dist_coeffs = config.CAMERA_CONFIG['manual_intrinsics']['dist_coeffs']
        print(f"\n⚠️ 使用配置文件中的默认内参")

    print(f"\n标定板配置:")
    print(f"  方格尺寸: {config.CHARUCO_CONFIG['square_size']*1000:.1f} mm")
    print(f"  标记尺寸: {config.CHARUCO_CONFIG['marker_size']*1000:.1f} mm")

    # 加载图像
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))

    if len(image_files) == 0:
        print(f"\n✗ 未找到图像文件")
        return

    print(f"\n找到 {len(image_files)} 张图像")
    print("\n" + "="*70)
    print("逐张分析:")
    print("="*70)

    all_results = []

    for i, image_file in enumerate(image_files):
        image = cv2.imread(str(image_file))

        print(f"\n图像 {i+1}: {image_file.name}")
        print("-" * 70)

        # 图像质量分析
        quality = analyze_image_quality(image)
        print(f"图像质量:")
        print(f"  亮度: {quality['brightness_mean']:.1f} ± {quality['brightness_std']:.1f}")
        print(f"  清晰度: {quality['sharpness']:.2f}", end="")
        if quality['is_blurry']:
            print(" ⚠️ 模糊")
        else:
            print(" ✓")
        print(f"  对比度: {quality['contrast']:.1f}")

        if quality['is_dark']:
            print(f"  ⚠️ 图像偏暗")
        elif quality['is_bright']:
            print(f"  ⚠️ 图像过亮")

        # 检测分析
        detection = detect_and_analyze(image, camera_matrix, dist_coeffs)

        print(f"\n检测结果:")
        print(f"  ArUco标记: {detection['aruco_detected']} 个")
        if detection['aruco_detected'] > 0:
            print(f"  标记ID: {detection['aruco_ids']}")

        if detection['detection_success']:
            print(f"  ChArUco角点: {detection['charuco_detected']} 个 ✓")
            print(f"  角点ID: {detection['charuco_ids']}")

            print(f"\n位姿信息:")
            print(f"  距离: {detection['distance']*100:.1f} cm")
            print(f"  角度: X={detection['angle_x']:.1f}°, Y={detection['angle_y']:.1f}°")

            print(f"\n重投影误差:")
            print(f"  平均: {detection['reprojection_error_mean']:.2f} px", end="")
            if detection['reprojection_error_mean'] > 5:
                print(" ⚠️ 误差较大")
            elif detection['reprojection_error_mean'] > 2:
                print(" ⚠️ 误差偏大")
            else:
                print(" ✓")
            print(f"  最大: {detection['reprojection_error_max']:.2f} px")
            print(f"  标准差: {detection['reprojection_error_std']:.2f} px")

            # 分析误差原因
            print(f"\n可能的误差来源:")
            if detection['distance'] < 0.15:
                print(f"  ⚠️ 距离太近（{detection['distance']*100:.1f}cm < 15cm）")
            elif detection['distance'] > 0.50:
                print(f"  ⚠️ 距离太远（{detection['distance']*100:.1f}cm > 50cm）")

            if abs(detection['angle_x']) > 45 or abs(detection['angle_y']) > 45:
                print(f"  ⚠️ 角度太倾斜（X={detection['angle_x']:.1f}°, Y={detection['angle_y']:.1f}°）")

            if quality['is_blurry']:
                print(f"  ⚠️ 图像模糊")

            if detection['charuco_detected'] < 10:
                print(f"  ⚠️ 角点数量较少（{detection['charuco_detected']} < 10）")

            if detection['reprojection_error_mean'] > 5:
                print(f"  ⚠️ 可能的原因：")
                print(f"     - 标定板尺寸配置不准确")
                print(f"     - 相机内参不准确")
                print(f"     - 标定板不平整")
        else:
            print(f"  ✗ 检测失败")
            print(f"  失败原因: {', '.join(detection['failure_reason'])}")

            # 分析失败原因
            print(f"\n可能的失败原因:")
            if quality['is_blurry']:
                print(f"  ⚠️ 图像模糊（清晰度={quality['sharpness']:.2f}）")
            if quality['is_dark']:
                print(f"  ⚠️ 光照不足（亮度={quality['brightness_mean']:.1f}）")
            if detection['aruco_detected'] == 0:
                print(f"  ⚠️ 标定板可能不在视野内或距离太远")
            elif detection['aruco_detected'] < 4:
                print(f"  ⚠️ 标定板部分遮挡或角度太倾斜")

        all_results.append({
            'image_id': i,
            'quality': quality,
            'detection': detection
        })

    # 统计分析
    print("\n" + "="*70)
    print("统计分析")
    print("="*70)

    successful = [r for r in all_results if r['detection']['detection_success']]
    failed = [r for r in all_results if not r['detection']['detection_success']]

    print(f"\n成功: {len(successful)}/{len(all_results)} ({len(successful)/len(all_results)*100:.1f}%)")
    print(f"失败: {len(failed)}/{len(all_results)} ({len(failed)/len(all_results)*100:.1f}%)")

    if len(successful) > 0:
        errors = [r['detection']['reprojection_error_mean'] for r in successful]
        distances = [r['detection']['distance'] for r in successful]
        sharpness = [r['quality']['sharpness'] for r in successful]

        print(f"\n成功图像的统计:")
        print(f"  重投影误差: {np.mean(errors):.2f} ± {np.std(errors):.2f} px")
        print(f"  距离范围: {np.min(distances)*100:.1f} - {np.max(distances)*100:.1f} cm")
        print(f"  平均清晰度: {np.mean(sharpness):.2f}")

    if len(failed) > 0:
        print(f"\n失败图像的统计:")
        failed_sharpness = [r['quality']['sharpness'] for r in failed]
        failed_brightness = [r['quality']['brightness_mean'] for r in failed]
        print(f"  平均清晰度: {np.mean(failed_sharpness):.2f} (成功: {np.mean(sharpness):.2f})")
        print(f"  平均亮度: {np.mean(failed_brightness):.1f}")

        # 统计失败原因
        print(f"\n失败原因分布:")
        reasons = {}
        for r in failed:
            for reason in r['detection']['failure_reason']:
                reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count} 次")

    # 建议
    print(f"\n" + "="*70)
    print("改进建议")
    print("="*70)

    if len(failed) > len(successful):
        print(f"\n失败率过高（{len(failed)/len(all_results)*100:.1f}%），建议:")

        avg_failed_sharpness = np.mean([r['quality']['sharpness'] for r in failed])
        if avg_failed_sharpness < 150:
            print(f"  1. 增加自动采集间隔（当前10秒），等待机器人完全停稳")
            print(f"     建议: 15-20秒")

        avg_failed_brightness = np.mean([r['quality']['brightness_mean'] for r in failed])
        if avg_failed_brightness < 100:
            print(f"  2. 增加光照强度")

        if len([r for r in failed if r['detection']['aruco_detected'] == 0]) > len(failed) * 0.5:
            print(f"  3. 控制拍摄距离，保持在20-40cm范围内")
            print(f"  4. 避免标定板角度太倾斜")

    if len(successful) > 0:
        avg_error = np.mean([r['detection']['reprojection_error_mean'] for r in successful])
        if avg_error > 5:
            print(f"\n重投影误差过大（{avg_error:.2f}px），建议:")
            print(f"  1. 用卡尺精确测量标定板尺寸")
            print(f"     运行: python measure_board_size.py")
            print(f"  2. 检查相机内参是否准确")
            print(f"  3. 检查标定板是否平整")
            print(f"  4. 避免距离太近（< 15cm）")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
