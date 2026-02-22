"""
标定板尺寸测量辅助工具
====================
帮助用户通过图像测量标定板的实际尺寸

使用方法:
    python measure_board_size.py
"""

import sys
from pathlib import Path
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent))
import config

def measure_board():
    """交互式测量标定板尺寸"""

    # 加载第一张图像
    image_files = sorted(config.PATHS['images_dir'].glob("image_*.png"))
    if len(image_files) == 0:
        print("✗ 未找到图像文件")
        return

    image = cv2.imread(str(image_files[0]))
    if image is None:
        print("✗ 无法读取图像")
        return

    print("\n" + "="*70)
    print("标定板尺寸测量")
    print("="*70)
    print("\n当前配置:")
    print(f"  方格尺寸: {config.CHARUCO_CONFIG['square_size']*1000:.1f} mm")
    print(f"  标记尺寸: {config.CHARUCO_CONFIG['marker_size']*1000:.1f} mm")

    print("\n请用卡尺测量你的标定板:")
    print("  1. 方格边长 = 一个完整方格的边长（黑+白）")
    print("  2. 标记边长 = 黑色ArUco标记的外边长")
    print("\n测量示意:")
    print("  ┌─────────┬─────────┐")
    print("  │ ░░░░░░░ │         │  ← 方格边长")
    print("  │ ░░░░░░░ │         │")
    print("  │ ░░░░░░░ │         │")
    print("  ├─────────┼─────────┤")
    print("  │         │ ▓▓▓▓▓▓▓ │")
    print("  │         │ ▓▓▓▓▓▓▓ │  ← 标记边长")
    print("  │         │ ▓▓▓▓▓▓▓ │")
    print("  └─────────┴─────────┘")

    print("\n" + "="*70)

    # 检测标定板
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    corners, ids, rejected = detector.detectMarkers(image)

    vis_image = image.copy()

    if ids is not None and len(ids) >= 2:
        # 绘制检测到的标记
        cv2.aruco.drawDetectedMarkers(vis_image, corners, ids)

        # 计算相邻标记的像素距离
        print("\n检测到的标记:")
        for i, marker_id in enumerate(ids):
            center = corners[i][0].mean(axis=0)
            print(f"  标记 {marker_id[0]}: 中心位置 ({center[0]:.1f}, {center[1]:.1f})")

        # 如果有相邻的标记，计算像素距离
        if len(ids) >= 2:
            center1 = corners[0][0].mean(axis=0)
            center2 = corners[1][0].mean(axis=0)
            pixel_dist = np.linalg.norm(center1 - center2)

            print(f"\n标记0和标记1的中心距离: {pixel_dist:.2f} 像素")
            print(f"如果你知道这两个标记的实际距离（mm），可以估算像素比例")

    # 显示图像
    cv2.imshow("Board Measurement", vis_image)
    print("\n按任意键关闭...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # 让用户输入测量值
    print("\n" + "="*70)
    print("请输入你用卡尺测量的实际尺寸:")
    print("="*70)

    try:
        square_mm = float(input("方格边长 (mm): "))
        marker_mm = float(input("标记边长 (mm): "))

        print(f"\n测量结果:")
        print(f"  方格边长: {square_mm:.1f} mm")
        print(f"  标记边长: {marker_mm:.1f} mm")

        # 与配置对比
        config_square = config.CHARUCO_CONFIG['square_size'] * 1000
        config_marker = config.CHARUCO_CONFIG['marker_size'] * 1000

        square_diff = abs(square_mm - config_square)
        marker_diff = abs(marker_mm - config_marker)

        print(f"\n与配置对比:")
        print(f"  方格: 配置={config_square:.1f}mm, 测量={square_mm:.1f}mm, 差异={square_diff:.1f}mm")
        print(f"  标记: 配置={config_marker:.1f}mm, 测量={marker_mm:.1f}mm, 差异={marker_diff:.1f}mm")

        if square_diff > 1.0 or marker_diff > 1.0:
            print(f"\n⚠️ 警告：测量值与配置差异较大！")
            print(f"   这可能是导致重投影误差大的主要原因。")
            print(f"\n建议修改 config.py:")
            print(f"  'square_size': {square_mm/1000:.6f},  # {square_mm:.1f} mm")
            print(f"  'marker_size': {marker_mm/1000:.6f},  # {marker_mm:.1f} mm")
        else:
            print(f"\n✓ 测量值与配置基本一致")

    except ValueError:
        print("✗ 输入无效")
    except KeyboardInterrupt:
        print("\n用户取消")

if __name__ == "__main__":
    measure_board()