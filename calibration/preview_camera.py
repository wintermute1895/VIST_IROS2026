#!/usr/bin/env python3
"""
相机预览工具
============
用于在标定前预览相机画面，调整相机位置和角度。
"""

import cv2
import numpy as np
import config


def preview_camera():
    """
    打开相机预览窗口

    操作说明:
    - 按 'q' 键退出
    - 按 'd' 键检测 ChArUco 标定板
    """
    print("\n" + "="*70)
    print("相机预览模式")
    print("="*70)
    print("操作说明:")
    print("  - 按 'q' 键退出")
    print("  - 按 'd' 键检测 ChArUco 标定板（测试标定板是否可见）")
    print("="*70 + "\n")

    # 初始化 RealSense 相机
    try:
        import pyrealsense2 as rs

        pipeline = rs.pipeline()
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
        profile = pipeline.start(rs_config)

        # 获取相机内参
        if config.CAMERA_CONFIG['realsense']['use_intrinsics']:
            color_stream = profile.get_stream(rs.stream.color)
            intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

            camera_matrix = np.array([
                [intrinsics.fx, 0, intrinsics.ppx],
                [0, intrinsics.fy, intrinsics.ppy],
                [0, 0, 1]
            ], dtype=np.float64)

            dist_coeffs = np.array(intrinsics.coeffs, dtype=np.float64)

            print(f"✓ 相机初始化成功")
            print(f"  分辨率: {intrinsics.width}x{intrinsics.height}")
            print(f"  焦距: fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
            print()
        else:
            camera_matrix = config.CAMERA_CONFIG['manual_intrinsics']['camera_matrix']
            dist_coeffs = config.CAMERA_CONFIG['manual_intrinsics']['dist_coeffs']

    except ImportError:
        print("✗ 未安装 pyrealsense2，请安装: pip install pyrealsense2")
        return
    except Exception as e:
        print(f"✗ 相机初始化失败: {e}")
        return

    # 获取 ChArUco 板配置
    board = config.get_charuco_board()
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

    # 主循环
    detect_mode = False

    try:
        while True:
            # 捕获图像
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            # 转换为 numpy 数组
            image = np.asanyarray(color_frame.get_data())
            display_image = image.copy()

            # 如果启用检测模式，检测 ChArUco 角点
            if detect_mode:
                # 检测 ArUco 标记（兼容 OpenCV 4.7+）
                detector_params = cv2.aruco.DetectorParameters()
                detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
                corners, ids, rejected = detector.detectMarkers(image)

                if ids is not None and len(ids) >= 4:
                    # 绘制检测到的标记
                    cv2.aruco.drawDetectedMarkers(display_image, corners, ids)

                    # 插值 ChArUco 角点
                    retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                        corners,
                        ids,
                        image,
                        board
                    )

                    if retval >= 4:
                        # 绘制 ChArUco 角点
                        cv2.aruco.drawDetectedCornersCharuco(
                            display_image,
                            charuco_corners,
                            charuco_ids
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

                        if success:
                            # 绘制坐标轴
                            cv2.drawFrameAxes(
                                display_image,
                                camera_matrix,
                                dist_coeffs,
                                rvec,
                                tvec,
                                0.1  # 轴长度 10cm
                            )

                            # 显示检测信息
                            info_text = f"Detected: {retval} corners"
                            cv2.putText(
                                display_image,
                                info_text,
                                (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2
                            )
                    else:
                        # 角点不足
                        cv2.putText(
                            display_image,
                            f"Too few corners: {retval}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 0, 255),
                            2
                        )
                else:
                    # 未检测到标记
                    markers_found = len(ids) if ids is not None else 0
                    cv2.putText(
                        display_image,
                        f"Markers found: {markers_found} (need >= 4)",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )

            # 显示提示信息
            help_text = "Press 'd' to toggle detection | 'q' to quit"
            cv2.putText(
                display_image,
                help_text,
                (10, display_image.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            # 显示图像
            cv2.imshow("Camera Preview", display_image)

            # 等待按键
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord('d'):
                detect_mode = not detect_mode
                status = "ON" if detect_mode else "OFF"
                print(f"检测模式: {status}")

    finally:
        # 清理
        pipeline.stop()
        cv2.destroyAllWindows()
        print("\n✓ 相机已关闭")


if __name__ == "__main__":
    preview_camera()