#!/usr/bin/env python3
"""
从RealSense相机获取内参并保存
"""
import pyrealsense2 as rs
import numpy as np

def get_d405_intrinsics():
    """获取D405相机内参"""

    # 创建pipeline
    pipeline = rs.pipeline()
    config = rs.config()

    # 配置彩色流 (640x480)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    print("正在启动RealSense D405相机...")

    try:
        # 启动pipeline
        profile = pipeline.start(config)

        # 获取彩色流的profile
        color_profile = profile.get_stream(rs.stream.color)
        intrinsics = color_profile.as_video_stream_profile().get_intrinsics()

        print("\n" + "="*70)
        print("RealSense D405 相机内参")
        print("="*70)
        print(f"分辨率: {intrinsics.width} x {intrinsics.height}")
        print(f"焦距: fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
        print(f"主点: cx={intrinsics.ppx:.2f}, cy={intrinsics.ppy:.2f}")
        print(f"畸变模型: {intrinsics.model}")
        print(f"畸变系数: {intrinsics.coeffs}")
        print("="*70 + "\n")

        # 构建相机矩阵
        camera_matrix = np.array([
            [intrinsics.fx, 0, intrinsics.ppx],
            [0, intrinsics.fy, intrinsics.ppy],
            [0, 0, 1]
        ], dtype=np.float64)

        # 畸变系数 (k1, k2, p1, p2, k3)
        dist_coeffs = np.array(intrinsics.coeffs[:5], dtype=np.float64)

        # 保存到文件
        output_file = "calibration_data/camera_intrinsics.npz"
        np.savez(
            output_file,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs
        )

        print(f"✓ 相机内参已保存到: {output_file}\n")

        return camera_matrix, dist_coeffs

    finally:
        # 停止pipeline
        pipeline.stop()
        print("✓ 相机已关闭")


if __name__ == "__main__":
    get_d405_intrinsics()