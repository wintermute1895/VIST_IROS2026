#!/usr/bin/env python3
"""
更新数据存储结构
"""
from pathlib import Path
from datetime import datetime
import shutil

# 创建新的目录结构
base_dir = Path("calibration_data")
intrinsics_dir = base_dir / "camera_intrinsics"
calibrations_dir = base_dir / "calibrations"

print("创建新的数据结构...")
intrinsics_dir.mkdir(parents=True, exist_ok=True)
calibrations_dir.mkdir(parents=True, exist_ok=True)

# 移动现有的相机内参
old_intrinsics = base_dir / "camera_intrinsics.npz"
if old_intrinsics.exists():
    new_intrinsics = intrinsics_dir / "d405_intrinsics.npz"
    shutil.copy(old_intrinsics, new_intrinsics)
    print(f"✓ 已复制相机内参到: {new_intrinsics}")

# 移动现有的标定数据到新文件夹
old_images = base_dir / "images"
if old_images.exists() and any(old_images.iterdir()):
    # 创建带时间戳的文件夹
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    calib_dir = calibrations_dir / f"hand_camera_{timestamp}"
    calib_dir.mkdir(parents=True, exist_ok=True)
    
    # 移动数据
    if old_images.exists():
        shutil.copytree(old_images, calib_dir / "images", dirs_exist_ok=True)
        print(f"✓ 已移动图像到: {calib_dir / 'images'}")
    
    for file in ["robot_poses.npy", "hand_eye_matrix.npy", "calibration_result.json"]:
        old_file = base_dir / file
        if old_file.exists():
            shutil.copy(old_file, calib_dir / file)
            print(f"✓ 已移动 {file} 到: {calib_dir}")

print("\n新的数据结构:")
print(f"  相机内参: {intrinsics_dir}/")
print(f"  标定数据: {calibrations_dir}/")
print("\n✓ 数据结构更新完成")
