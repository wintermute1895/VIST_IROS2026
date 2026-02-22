#!/usr/bin/env python3
"""
测试RealSense相机连接
"""
import pyrealsense2 as rs

print("检查RealSense相机...")
print()

try:
    # 创建context
    ctx = rs.context()
    devices = ctx.query_devices()

    if len(devices) == 0:
        print("✗ 没有检测到RealSense相机")
        print("  请检查:")
        print("  1. 相机是否已连接")
        print("  2. USB线是否插好")
        print("  3. 是否有权限访问USB设备")
    else:
        print(f"✓ 检测到 {len(devices)} 个RealSense设备:")
        for i, dev in enumerate(devices):
            print(f"\n设备 {i+1}:")
            print(f"  名称: {dev.get_info(rs.camera_info.name)}")
            print(f"  序列号: {dev.get_info(rs.camera_info.serial_number)}")
            print(f"  固件版本: {dev.get_info(rs.camera_info.firmware_version)}")

        # 尝试启动相机
        print("\n尝试启动相机...")
        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        profile = pipeline.start(config)
        print("✓ 相机启动成功")

        # 获取一帧
        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        if color_frame:
            print("✓ 成功获取图像帧")

        pipeline.stop()
        print("✓ 相机测试完成")

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
