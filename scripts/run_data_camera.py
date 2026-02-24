#!/usr/bin/env python3
"""
直接启动数据采集相机节点
序列号: 348122071157
"""

import sys
import os

# 添加路径
sys.path.insert(0, '/home/ilex/Dev/VIST/src/camera_manager')

import rclpy
from camera_manager.realsense_camera_node import RealSenseCameraNode

def main():
    print("=" * 60)
    print("启动数据采集相机")
    print("=" * 60)
    print("相机序列号: 348122071157")
    print("用途: 模仿学习数据收集")
    print()

    # 初始化ROS2
    rclpy.init()

    # 创建节点，设置参数
    node = RealSenseCameraNode()

    # 设置参数
    node.set_parameters([
        rclpy.parameter.Parameter('serial_number', rclpy.Parameter.Type.STRING, '348122071157'),
        rclpy.parameter.Parameter('camera_name', rclpy.Parameter.Type.STRING, 'data_camera'),
        rclpy.parameter.Parameter('camera_id', rclpy.Parameter.Type.INTEGER, 1),

        # 彩色流配置
        rclpy.parameter.Parameter('color_width', rclpy.Parameter.Type.INTEGER, 848),
        rclpy.parameter.Parameter('color_height', rclpy.Parameter.Type.INTEGER, 480),
        rclpy.parameter.Parameter('color_fps', rclpy.Parameter.Type.INTEGER, 30),

        # 深度流配置
        rclpy.parameter.Parameter('depth_width', rclpy.Parameter.Type.INTEGER, 848),
        rclpy.parameter.Parameter('depth_height', rclpy.Parameter.Type.INTEGER, 480),
        rclpy.parameter.Parameter('depth_fps', rclpy.Parameter.Type.INTEGER, 30),

        # 功能开关
        rclpy.parameter.Parameter('enable_color', rclpy.Parameter.Type.BOOL, True),
        rclpy.parameter.Parameter('enable_depth', rclpy.Parameter.Type.BOOL, True),
        rclpy.parameter.Parameter('enable_pointcloud', rclpy.Parameter.Type.BOOL, False),
        rclpy.parameter.Parameter('enable_imu', rclpy.Parameter.Type.BOOL, False),
        rclpy.parameter.Parameter('align_depth_to_color', rclpy.Parameter.Type.BOOL, True),
    ])

    print("✅ 节点已创建")
    print()
    print("发布的话题:")
    print("  - /data_camera/color/image_raw")
    print("  - /data_camera/color/camera_info")
    print("  - /data_camera/depth/image_rect_raw")
    print("  - /data_camera/depth/camera_info")
    print()
    print("按 Ctrl+C 停止")
    print()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n停止相机节点...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
