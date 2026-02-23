#!/usr/bin/env python3
"""
快速测试脚本 - 测试数据采集和保存功能
"""

import os
import sys

print("="*70)
print("数据采集功能测试")
print("="*70)
print()

# 检查数据目录
data_dir = "calibration_data"
images_dir = os.path.join(data_dir, "images")

print("1. 检查数据目录...")
if os.path.exists(data_dir):
    print(f"   ✓ 数据目录存在: {data_dir}")
else:
    print(f"   ✗ 数据目录不存在: {data_dir}")

if os.path.exists(images_dir):
    print(f"   ✓ 图像目录存在: {images_dir}")
    # 统计图像数量
    images = [f for f in os.listdir(images_dir) if f.endswith('.png')]
    print(f"   ✓ 已采集图像数量: {len(images)}")
else:
    print(f"   ✗ 图像目录不存在: {images_dir}")

print()

# 检查位姿数据
poses_file = os.path.join(data_dir, "robot_poses.npy")
print("2. 检查位姿数据...")
if os.path.exists(poses_file):
    print(f"   ✓ 位姿文件存在: {poses_file}")
    try:
        import numpy as np
        poses = np.load(poses_file)
        print(f"   ✓ 位姿数据数量: {len(poses)}")
        print(f"   ✓ 位姿数据形状: {poses.shape}")
    except Exception as e:
        print(f"   ✗ 读取位姿数据失败: {e}")
else:
    print(f"   ✗ 位姿文件不存在: {poses_file}")

print()

# 检查相机内参
intrinsics_file = os.path.join(data_dir, "camera_intrinsics.npz")
print("3. 检查相机内参...")
if os.path.exists(intrinsics_file):
    print(f"   ✓ 内参文件存在: {intrinsics_file}")
    try:
        import numpy as np
        data = np.load(intrinsics_file)
        print(f"   ✓ 相机矩阵形状: {data['camera_matrix'].shape}")
        print(f"   ✓ 畸变系数形状: {data['dist_coeffs'].shape}")
    except Exception as e:
        print(f"   ✗ 读取内参数据失败: {e}")
else:
    print(f"   ✗ 内参文件不存在: {intrinsics_file}")

print()
print("="*70)
print("测试完成")
print("="*70)