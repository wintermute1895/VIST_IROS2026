# 手眼标定完整指南

## 📋 概述

本指南介绍如何为 VIST 系统进行手眼标定，包括全局相机和手腕相机。

---

## 🎯 标定目标

### 全局相机（Eye-to-Base）
- **目的**：确定相机相对于机器人基座的位置和姿态
- **输出**：变换矩阵 `T_base_camera` (4x4)
- **用途**：将相机坐标系中的目标位置转换到机器人基座坐标系

### 手腕相机（Eye-in-Hand）
- **目的**：确定相机相对于末端执行器的位置和姿态
- **输出**：变换矩阵 `T_ee_camera` (4x4)
- **用途**：将相机坐标系中的目标位置转换到末端执行器坐标系

---

## 🔧 准备工作

### 1. 硬件准备
- [ ] RealSense 相机（D435/D455）
- [ ] AprilTag 标记（推荐）或 ArUco 标记
  - 尺寸：10cm x 10cm（打印在硬纸板上）
  - ID：0（或其他固定ID）
- [ ] 固定支架（用于固定标记）

### 2. 软件准备
```bash
# 安装依赖
pip install opencv-python opencv-contrib-python
pip install pyrealsense2
pip install apriltag  # 或使用 OpenCV 的 ArUco
```

### 3. 内参标定（可选）

**RealSense 相机通常已有出厂内参**，可以直接使用：

```python
import pyrealsense2 as rs

pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

pipeline.start(config)
profile = pipeline.get_active_profile()
color_stream = profile.get_stream(rs.stream.color)
intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

print(f"fx: {intrinsics.fx}")
print(f"fy: {intrinsics.fy}")
print(f"cx: {intrinsics.ppx}")
print(f"cy: {intrinsics.ppy}")
print(f"distortion: {intrinsics.coeffs}")
```

**如果需要重新标定**（使用棋盘格）：

```bash
# 使用 OpenCV 棋盘格标定
python scripts/calibrate_camera_intrinsics.py
```

---

## 📐 标定方法

### 方法 1: 使用 easy_handeye（推荐）

**优点**：自动化、精度高、有 ROS 支持

```bash
# 安装 easy_handeye
git clone https://github.com/IFL-CAMP/easy_handeye
cd easy_handeye
pip install -e .
```

**标定流程**：

1. **全局相机标定**：
```bash
# 启动标定程序
python scripts/calibrate_eye_to_base.py

# 按照提示移动机器人到不同位置（至少15个位置）
# 每个位置都能看到 AprilTag 标记
# 程序会自动计算变换矩阵
```

2. **手腕相机标定**：
```bash
# 启动标定程序
python scripts/calibrate_eye_in_hand.py

# 移动机器人到不同位置（至少15个位置）
# AprilTag 标记固定在桌面上
# 程序会自动计算变换矩阵
```

### 方法 2: 手动标定（简单但精度较低）

**适用场景**：快速原型、测试

**全局相机标定**：

1. 将 AprilTag 标记放在机器人基座附近的已知位置
2. 使用相机检测标记位置
3. 手动测量标记相对于机器人基座的位置
4. 计算变换矩阵

```python
# 示例代码
import numpy as np
from scipy.spatial.transform import Rotation

# 已知：标记在基座坐标系中的位置
marker_pos_base = np.array([0.5, 0.0, 0.0])  # 机器人前方50cm

# 相机检测到的标记位置（相机坐标系）
marker_pos_camera = np.array([0.0, 0.0, 0.5])  # 相机前方50cm

# 计算平移
translation = marker_pos_base - marker_pos_camera

# 假设相机朝向与机器人一致（简化）
rotation = np.eye(3)

# 构建变换矩阵
T_base_camera = np.eye(4)
T_base_camera[:3, :3] = rotation
T_base_camera[:3, 3] = translation
```

---

## 🎯 标定精度验证

### 1. 重投影误差

```python
def verify_calibration(T_base_camera, test_positions):
    """
    验证标定精度

    Args:
        T_base_camera: 标定得到的变换矩阵
        test_positions: 测试位置列表（相机坐标系）

    Returns:
        平均误差（mm）
    """
    errors = []
    for pos_camera in test_positions:
        # 转换到基座坐标系
        pos_camera_homo = np.append(pos_camera, 1)
        pos_base_pred = T_base_camera @ pos_camera_homo

        # 与真实位置比较（需要手动测量）
        pos_base_true = measure_true_position()

        error = np.linalg.norm(pos_base_pred[:3] - pos_base_true)
        errors.append(error)

    return np.mean(errors) * 1000  # 转换为 mm
```

### 2. 精度指标

| 标定方法 | 平移精度 | 旋转精度 | 适用场景 |
|---------|---------|---------|---------|
| easy_handeye | 1-2mm | 0.5° | 生产环境 |
| 手动标定 | 5-10mm | 2-5° | 快速原型 |
| 几何测量 | 10-20mm | 5-10° | 测试 |

---

## 💾 保存标定结果

### 配置文件格式

```yaml
# config/camera_calibration.yaml

global_camera:
  # 全局相机（Eye-to-Base）
  intrinsics:
    fx: 615.123
    fy: 615.456
    cx: 320.0
    cy: 240.0
    distortion: [0.0, 0.0, 0.0, 0.0, 0.0]

  extrinsics:
    # 相机到机器人基座的变换矩阵（4x4）
    T_base_camera:
      - [0.0, -1.0, 0.0, 0.5]   # 相机在基座右侧50cm
      - [1.0, 0.0, 0.0, 0.0]
      - [0.0, 0.0, 1.0, 0.8]    # 高度80cm
      - [0.0, 0.0, 0.0, 1.0]

wrist_camera:
  # 手腕相机（Eye-in-Hand）
  intrinsics:
    fx: 615.123
    fy: 615.456
    cx: 320.0
    cy: 240.0
    distortion: [0.0, 0.0, 0.0, 0.0, 0.0]

  extrinsics:
    # 相机到末端执行器的变换矩阵（4x4）
    T_ee_camera:
      - [1.0, 0.0, 0.0, 0.0]
      - [0.0, 1.0, 0.0, 0.0]
      - [0.0, 0.0, 1.0, 0.05]   # 相机在末端前方5cm
      - [0.0, 0.0, 0.0, 1.0]
```

---

## 🚀 快速开始（推荐流程）

### Day 1: 准备和内参标定
1. 打印 AprilTag 标记（10cm x 10cm，ID=0）
2. 验证 RealSense 相机内参
3. 测试 AprilTag 检测

### Day 2: 手眼标定
1. 全局相机标定（1-2小时）
   - 移动机器人到15个不同位置
   - 运行标定程序
   - 验证精度
2. 手腕相机标定（1-2小时）
   - 移动机器人到15个不同位置
   - 运行标定程序
   - 验证精度

### Day 3: 集成测试
1. 将标定结果保存到配置文件
2. 测试坐标转换
3. 运行完整的 VIST 流程

---

## 📝 注意事项

### 1. 标定质量影响因素
- ✅ 标记尺寸：越大越好（推荐 10cm）
- ✅ 标记平整度：必须完全平整
- ✅ 光照条件：均匀、充足
- ✅ 位置多样性：至少 15 个不同位置和姿态
- ✅ 相机稳定性：避免抖动

### 2. 常见问题
- **检测不到标记**：检查光照、标记尺寸、相机焦距
- **精度不够**：增加标定位置数量、使用更大的标记
- **结果不稳定**：检查标记是否平整、相机是否固定牢固

### 3. 调试技巧
```python
# 可视化标定结果
import cv2

def visualize_calibration(image, T_base_camera):
    # 在图像上绘制坐标轴
    # 验证变换是否正确
    pass
```

---

## 🔗 参考资料

- [easy_handeye](https://github.com/IFL-CAMP/easy_handeye)
- [OpenCV 手眼标定](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#gaebfc1c9f7434196a374c382abf43439b)
- [AprilTag](https://april.eecs.umich.edu/software/apriltag)
- [RealSense SDK](https://github.com/IntelRealSense/librealsense)

---

**最后更新**: 2026-02-09
