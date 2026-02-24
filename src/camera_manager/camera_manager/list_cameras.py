#!/usr/bin/env python3
"""
Utility script to list all connected RealSense cameras.
列出所有连接的RealSense相机及其序列号
"""

import pyrealsense2 as rs


def list_realsense_cameras():
    """List all connected RealSense cameras with details."""
    ctx = rs.context()
    devices = ctx.query_devices()

    if len(devices) == 0:
        print("未检测到RealSense相机！")
        print("请检查：")
        print("1. 相机是否已连接到USB端口")
        print("2. USB线缆是否正常工作")
        print("3. 是否安装了librealsense2")
        return

    print(f"\n检测到 {len(devices)} 个RealSense相机：\n")
    print("=" * 80)

    for i, device in enumerate(devices):
        print(f"\n相机 #{i + 1}:")
        print(f"  名称: {device.get_info(rs.camera_info.name)}")
        print(f"  序列号: {device.get_info(rs.camera_info.serial_number)}")
        print(f"  固件版本: {device.get_info(rs.camera_info.firmware_version)}")
        print(f"  USB类型: {device.get_info(rs.camera_info.usb_type_descriptor)}")

        # List available sensors
        sensors = device.query_sensors()
        print(f"  传感器:")
        for sensor in sensors:
            print(f"    - {sensor.get_info(rs.camera_info.name)}")

    print("\n" + "=" * 80)
    print("\n配置说明：")
    print("1. 将上面的序列号复制到 config/camera_config.yaml 文件中")
    print("2. 根据相机用途设置 camera_name (例如: mediapipe_camera, robot_head_camera)")
    print("3. 配置分辨率和帧率参数")
    print("\n示例配置：")
    print("  - serial_number: \"<上面显示的序列号>\"")
    print("    camera_name: \"mediapipe_camera\"")
    print("    enable_color: true")
    print("    enable_depth: true\n")


if __name__ == '__main__':
    try:
        list_realsense_cameras()
    except Exception as e:
        print(f"错误: {e}")
        print("\n请确保：")
        print("1. 已安装 pyrealsense2: pip install pyrealsense2")
        print("2. 相机驱动正常工作")
