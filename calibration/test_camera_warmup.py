#!/usr/bin/env python3
"""
改进的RealSense相机测试 - 增加预热时间
"""
import pyrealsense2 as rs
import time

print("检查RealSense相机...")
print()

try:
    # 创建context
    ctx = rs.context()
    devices = ctx.query_devices()

    if len(devices) == 0:
        print("✗ 没有检测到RealSense相机")
        exit(1)

    print(f"✓ 检测到 {len(devices)} 个RealSense设备")
    for i, dev in enumerate(devices):
        print(f"  设备 {i+1}: {dev.get_info(rs.camera_info.name)}")

    # 尝试启动相机
    print("\n正在启动相机...")
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    profile = pipeline.start(config)
    print("✓ 相机pipeline启动成功")

    # 给相机预热时间
    print("\n等待相机预热 (2秒)...")
    time.sleep(2)

    # 尝试获取多帧
    print("\n尝试获取图像帧...")
    for i in range(5):
        try:
            print(f"  尝试 {i+1}/5...", end=" ")
            frames = pipeline.wait_for_frames(timeout_ms=10000)  # 10秒超时
            color_frame = frames.get_color_frame()
            if color_frame:
                print(f"✓ 成功 (帧号: {color_frame.get_frame_number()})")
            else:
                print("✗ 未获取到彩色帧")
        except Exception as e:
            print(f"✗ 失败: {e}")

    pipeline.stop()
    print("\n✓ 相机测试完成")

except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
