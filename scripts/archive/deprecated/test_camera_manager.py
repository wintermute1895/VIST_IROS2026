#!/usr/bin/env python3
"""
测试鲁棒相机管理器
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, '/home/ilex/Dev/VIST')

try:
    import rclpy
    from src.camera_manager.camera_manager.robust_camera_manager import RobustCameraManager

    print("✅ 导入成功")

    # 初始化ROS2
    rclpy.init()

    print("✅ ROS2初始化成功")

    # 创建节点
    node = RobustCameraManager()

    print("✅ 相机管理器创建成功")
    print(f"   管理的相机数量: {len(node.cameras)}")

    # 运行一小段时间
    import time
    print("运行5秒...")

    for i in range(5):
        rclpy.spin_once(node, timeout_sec=1.0)
        print(f"  {i+1}/5 秒")

    print("✅ 测试完成")

    # 清理
    node.destroy_node()
    rclpy.shutdown()

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
