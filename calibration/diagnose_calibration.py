"""
标定系统诊断脚本
检查标定数据和配置是否正确
"""

import numpy as np
import cv2
import json
from pathlib import Path
from config import CalibrationConfig


def check_robot_poses():
    """检查机械臂位姿数据"""
    print("=" * 60)
    print("1. 检查机械臂位姿数据")
    print("=" * 60)

    config = CalibrationConfig()

    if not config.poses_file.exists():
        print(f"❌ 位姿文件不存在: {config.poses_file}")
        return False

    poses = np.load(str(config.poses_file))
    print(f"✓ 加载了 {len(poses)} 组位姿数据")
    print(f"  数据形状: {poses.shape}")

    # 检查位姿是否都相同
    all_same = True
    for i in range(1, len(poses)):
        if not np.allclose(poses[0], poses[i]):
            all_same = False
            break

    if all_same:
        print(f"❌ 严重问题：所有位姿完全相同！")
        print(f"   第一个位姿:")
        print(poses[0])
        print(f"\n   这会导致手眼标定失败")
        print(f"   原因：标定需要机械臂在不同位置和姿态下采集数据")
        return False
    else:
        print(f"✓ 位姿数据有变化")

        # 计算位姿变化范围
        positions = poses[:, :3, 3]
        print(f"\n  位置变化范围:")
        print(f"    X: [{positions[:, 0].min():.3f}, {positions[:, 0].max():.3f}] 米")
        print(f"    Y: [{positions[:, 1].min():.3f}, {positions[:, 1].max():.3f}] 米")
        print(f"    Z: [{positions[:, 2].min():.3f}, {positions[:, 2].max():.3f}] 米")

        # 计算位姿之间的距离
        distances = []
        for i in range(len(poses) - 1):
            dist = np.linalg.norm(poses[i, :3, 3] - poses[i+1, :3, 3])
            distances.append(dist)

        print(f"\n  相邻位姿间距:")
        print(f"    平均: {np.mean(distances):.3f} 米")
        print(f"    最小: {np.min(distances):.3f} 米")
        print(f"    最大: {np.max(distances):.3f} 米")

        if np.mean(distances) < 0.01:
            print(f"  ⚠️  位姿变化较小，可能影响标定精度")

        return True


def check_images():
    """检查图像数据"""
    print("\n" + "=" * 60)
    print("2. 检查图像数据")
    print("=" * 60)

    config = CalibrationConfig()

    if not config.images_dir.exists():
        print(f"❌ 图像目录不存在: {config.images_dir}")
        return False

    image_files = list(config.images_dir.glob("*.png"))
    print(f"✓ 找到 {len(image_files)} 张图像")

    if len(image_files) == 0:
        print(f"❌ 没有图像文件")
        return False

    # 检查第一张图像
    first_image = cv2.imread(str(image_files[0]))
    if first_image is None:
        print(f"❌ 无法读取图像: {image_files[0]}")
        return False

    print(f"  图像尺寸: {first_image.shape[1]} x {first_image.shape[0]}")
    print(f"  图像格式: {first_image.dtype}")

    return True


def check_charuco_detection():
    """检查 ChArUco 板检测"""
    print("\n" + "=" * 60)
    print("3. 检查 ChArUco 板检测")
    print("=" * 60)

    config = CalibrationConfig()
    board = config.get_charuco_board()

    image_files = list(config.images_dir.glob("*.png"))
    if len(image_files) == 0:
        print(f"❌ 没有图像文件可供检测")
        return False

    # 检测第一张图像
    image = cv2.imread(str(image_files[0]))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 使用新的 API
    charuco_params = cv2.aruco.CharucoParameters()
    detector_params = cv2.aruco.DetectorParameters()
    charuco_detector = cv2.aruco.CharucoDetector(board, charuco_params, detector_params)

    charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(gray)

    if charuco_corners is not None and len(charuco_corners) >= 4:
        print(f"✓ 成功检测到 {len(charuco_corners)} 个角点")
        return True
    else:
        print(f"❌ 未检测到足够的角点")
        print(f"   可能原因:")
        print(f"   - 标定板不在视野内")
        print(f"   - 标定板尺寸配置不正确")
        print(f"   - 图像质量问题")
        return False


def check_calibration_result():
    """检查标定结果"""
    print("\n" + "=" * 60)
    print("4. 检查标定结果")
    print("=" * 60)

    config = CalibrationConfig()

    if not config.result_file.exists():
        print(f"⚠️  标定结果文件不存在: {config.result_file}")
        print(f"   请先运行 calibration_solver.py 进行标定")
        return False

    with open(config.result_file, 'r') as f:
        result = json.load(f)

    T_end2cam = np.array(result['T_end_to_cam'])

    print(f"✓ 标定结果文件存在")
    print(f"\n  T_end_to_cam 矩阵:")
    print(T_end2cam)

    # 检查是否为单位矩阵
    if np.allclose(T_end2cam, np.eye(4)):
        print(f"\n❌ 严重问题：标定矩阵是单位矩阵！")
        print(f"   这意味着标定完全失败")
        print(f"   可能原因:")
        print(f"   - 所有机械臂位姿相同")
        print(f"   - 标定数据不足")
        print(f"   - 标定算法输入数据有误")
        return False

    # 检查平移向量
    translation = T_end2cam[:3, 3]
    translation_norm = np.linalg.norm(translation)

    print(f"\n  平移向量: {translation}")
    print(f"  平移距离: {translation_norm:.3f} 米")

    if translation_norm < 0.001:
        print(f"  ⚠️  平移距离过小，可能标定失败")
        return False

    if translation_norm > 1.0:
        print(f"  ⚠️  平移距离过大，可能标定有误")

    # 检查旋转矩阵
    R = T_end2cam[:3, :3]
    det_R = np.linalg.det(R)

    print(f"\n  旋转矩阵行列式: {det_R:.6f}")

    if not np.isclose(det_R, 1.0, atol=0.01):
        print(f"  ⚠️  旋转矩阵行列式不为1，矩阵可能无效")
        return False

    print(f"  ✓ 旋转矩阵有效")

    return True


def check_error_stats():
    """检查误差统计"""
    print("\n" + "=" * 60)
    print("5. 检查误差统计")
    print("=" * 60)

    config = CalibrationConfig()
    stats_file = config.data_dir / "calibration_error_stats.json"

    if not stats_file.exists():
        print(f"⚠️  误差统计文件不存在: {stats_file}")
        print(f"   请运行 calibration_error_analysis.py 生成误差统计")
        return False

    with open(stats_file, 'r') as f:
        stats = json.load(f)

    print(f"✓ 误差统计文件存在")
    print(f"\n  总样本数: {stats['total_samples']}")
    print(f"  有效样本数: {stats['valid_samples']}")
    print(f"  失败样本数: {stats['failed_samples']}")
    print(f"\n  重投影误差统计（像素）:")
    print(f"    平均值: {stats['mean_error']:.3f}")
    print(f"    标准差: {stats['std_error']:.3f}")
    print(f"    最小值: {stats['min_error']:.3f}")
    print(f"    最大值: {stats['max_error']:.3f}")
    print(f"    中位数: {stats['median_error']:.3f}")

    mean_error = stats['mean_error']

    if mean_error < 1.0:
        print(f"\n  ✓ 优秀：误差 < 1.0 像素")
        return True
    elif mean_error < 2.0:
        print(f"\n  ✓ 良好：误差 < 2.0 像素")
        return True
    elif mean_error < 5.0:
        print(f"\n  ⚠️  可接受：误差 < 5.0 像素")
        return True
    else:
        print(f"\n  ❌ 较差：误差 >= 5.0 像素")
        print(f"     建议重新标定")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("手眼标定系统诊断")
    print("=" * 60 + "\n")

    results = []

    # 1. 检查机械臂位姿
    results.append(("机械臂位姿数据", check_robot_poses()))

    # 2. 检查图像数据
    results.append(("图像数据", check_images()))

    # 3. 检查 ChArUco 检测
    results.append(("ChArUco 板检测", check_charuco_detection()))

    # 4. 检查标定结果
    results.append(("标定结果", check_calibration_result()))

    # 5. 检查误差统计
    results.append(("误差统计", check_error_stats()))

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)

    for name, result in results:
        status = "✓ 通过" if result else "❌ 失败"
        print(f"{name:20s}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print(f"\n✓ 所有检查通过，标定系统正常")
    else:
        print(f"\n❌ 部分检查失败，请根据上述提示修复问题")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
