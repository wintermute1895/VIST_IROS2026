# Eye-in-Hand 视觉标定系统

完整的 Eye-in-Hand（眼在手）手眼标定解决方案，适用于 Intel RealSense D405 相机和通用机械臂。

## 📋 目录

- [系统概述](#系统概述)
- [硬件要求](#硬件要求)
- [软件依赖](#软件依赖)
- [快速开始](#快速开始)
- [详细使用说明](#详细使用说明)
- [坐标系说明](#坐标系说明)
- [常见问题](#常见问题)

## 系统概述

本系统用于计算机械臂末端法兰（End-Effector）到相机光心（Camera Optical Frame）的变换矩阵 `T_end_to_cam`。

**标定流程：**
1. **配置参数** - 设置标定板参数和相机内参
2. **数据采集** - 采集多组图像和机械臂位姿
3. **标定计算** - 使用 OpenCV 计算手眼变换矩阵
4. **精度验证** - 通过重投影验证标定精度

## 硬件要求

- **相机**: Intel RealSense D405（或其他 RealSense 系列）
- **机械臂**: 任意品牌（需要能够获取末端位姿）
- **标定板**: ChArUco Board（基于 OpenCV ArUco 字典）

### 标定板制作

1. 使用 OpenCV 生成 ChArUco 标定板图案
2. 打印到平整的硬质板上（推荐 A4 或更大）
3. **⚠️ 重要**: 使用卡尺精确测量以下参数：
   - `square_size`: 棋盘格方格边长（米）
   - `marker_size`: ArUco 二维码边长（米）
4. 在 [config.py](scripts/config.py) 中填写真实测量值

## 软件依赖

### Python 版本
- Python 3.8+

### 必需库
```bash
pip install numpy opencv-contrib-python pyrealsense2 scipy
```

### 依赖说明
- `numpy`: 数值计算
- `opencv-contrib-python`: OpenCV 完整版（包含 ArUco 模块）
- `pyrealsense2`: Intel RealSense SDK Python 绑定
- `scipy`: 旋转矩阵转换

## 快速开始

### 1. 实现机械臂接口

编辑 [robot_interface.py](scripts/robot_interface.py)，实现 `YourRobotInterface` 类：

```python
class YourRobotInterface(RobotInterface):
    def __init__(self):
        # 初始化你的机械臂连接
        from your_robot_sdk import RobotController
        self.robot = RobotController()
        self.robot.connect()

    def get_current_pose(self) -> np.ndarray:
        # 获取当前末端位姿（返回 4x4 矩阵）
        pose = self.robot.get_tcp_pose()  # [x, y, z, rx, ry, rz]
        x, y, z, rx, ry, rz = pose
        return self.pose_to_matrix(x, y, z, rx, ry, rz, rotation_type="euler_xyz")
```

**位姿格式说明：**
- 返回值必须是 4x4 齐次变换矩阵
- 表示从 Base（基座）到 End-Effector（末端）的变换
- 如果你的 SDK 返回其他格式，使用提供的辅助函数转换：
  - `pose_to_matrix()`: [x, y, z, rx, ry, rz] → 4x4 矩阵
  - `quaternion_to_matrix()`: [x, y, z, qx, qy, qz, qw] → 4x4 矩阵

### 2. 配置参数

编辑 [config.py](scripts/config.py)，设置标定板参数：

```python
# ⚠️ 必须填写真实测量值！
self.square_size = 0.040  # 方格边长（米），例如 40mm
self.marker_size = 0.030  # 二维码边长（米），例如 30mm
```

### 3. 数据采集

运行数据采集脚本：

```bash
cd scripts
python data_collection.py
```

**操作步骤：**
1. 移动机械臂到不同位置和姿态
2. 确保标定板在相机视野内且清晰可见
3. 按 `s` 键保存当前数据
4. 重复步骤 1-3，至少采集 **15 组**数据
5. 按 `q` 键退出

**采集建议：**
- 覆盖工作空间的不同区域
- 包含不同的相机角度和距离
- 避免位姿过于相似的数据
- 标定板应占据画面的 30%-70%

### 4. 标定计算

运行标定计算脚本：

```bash
python calibration_solver.py
```

脚本会：
1. 检测所有图像中的 ChArUco 角点
2. 估计标定板在相机坐标系下的位姿
3. 使用 `cv2.calibrateHandEye` 计算手眼矩阵
4. 保存结果到 `calibration_data/T_end_to_cam.npy`

### 5. 精度验证

运行验证脚本：

```bash
python visual_verification.py
```

**验证方法：**
1. 实时显示相机画面
2. 检测标定板并绘制坐标轴
3. 将标定板原点重投影到图像（红色圆点）
4. 移动机械臂，观察红点是否跟随标定板原点

**精度评估：**
- **Excellent** (< 5 像素): 标定精度很好
- **Good** (5-10 像素): 标定精度可接受
- **Poor** (> 10 像素): 需要重新标定

## 详细使用说明

### 文件结构

```
scripts/
├── config.py                  # 配置文件
├── robot_interface.py         # 机械臂接口（需要用户实现）
├── data_collection.py         # 数据采集脚本
├── calibration_solver.py      # 标定计算脚本
├── visual_verification.py     # 验证脚本
└── README.md                  # 本文件

calibration_data/              # 数据存储目录（自动创建）
├── images/                    # 采集的图像
│   ├── sample_000.png
│   ├── sample_001.png
│   └── ...
├── hand_eye_robot_poses.npy   # 手眼标定机械臂位姿数组
├── metadata.json              # 元数据
├── T_end_to_cam.npy          # 标定结果（4x4 矩阵）
└── hand_eye_result.json       # 标定结果（JSON 格式）
```

### 配置选项

在 [config.py](scripts/config.py) 中可以调整：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `aruco_dict_type` | ArUco 字典类型 | `DICT_4X4_50` |
| `charuco_board_rows` | 棋盘格行数 | 5 |
| `charuco_board_cols` | 棋盘格列数 | 7 |
| `square_size` | 方格边长（米）| 0.040 |
| `marker_size` | 二维码边长（米）| 0.030 |
| `calibration_method` | 标定算法 | `CALIB_HAND_EYE_TSAI` |
| `min_samples` | 最小样本数 | 15 |

**标定算法选项：**
- `CALIB_HAND_EYE_TSAI`: Tsai 方法（推荐）
- `CALIB_HAND_EYE_PARK`: Park 方法
- `CALIB_HAND_EYE_HORAUD`: Horaud 方法
- `CALIB_HAND_EYE_ANDREFF`: Andreff 方法
- `CALIB_HAND_EYE_DANIILIDIS`: Daniilidis 方法

## 坐标系说明

### 坐标系定义

```
Base (机器人基座)
  ↓ T_base_to_end (机械臂运动学)
End-Effector (末端法兰)
  ↓ T_end_to_cam (手眼标定结果)
Camera (相机光心)
  ↓ T_cam_to_board (视觉检测)
Board (标定板)
```

### 变换矩阵

**手眼标定求解的是**: `T_end_to_cam`（末端到相机的变换）

**使用示例**：将标定板坐标转换到机器人基座坐标系

```python
# 1. 检测标定板在相机坐标系下的位姿
rvec, tvec = detect_board_pose(image)
T_cam_to_board = build_transform_matrix(rvec, tvec)

# 2. 获取机械臂当前位姿
T_base_to_end = robot.get_current_pose()

# 3. 加载手眼标定结果
T_end_to_cam = np.load("calibration_data/T_end_to_cam.npy")

# 4. 计算标定板在基座坐标系下的位姿
T_base_to_board = T_base_to_end @ T_end_to_cam @ T_cam_to_board
```

### 旋转表示

系统支持多种旋转表示：
- **旋转矩阵** (3x3): OpenCV 和 NumPy 标准格式
- **旋转向量** (3x1): OpenCV `solvePnP` 输出格式
- **欧拉角** (3x1): 常见机械臂 SDK 格式
- **四元数** (4x1): 部分机械臂 SDK 格式

使用 `robot_interface.py` 中的辅助函数进行转换。

## 常见问题

### Q1: 标定精度不够怎么办？

**可能原因：**
1. 采集的数据量不足（< 15 组）
2. 数据多样性不够（位姿过于相似）
3. 标定板参数测量不准确
4. 相机内参不准确
5. 机械臂位姿读取有误

**解决方法：**
1. 增加采集数据量（推荐 20-30 组）
2. 覆盖更大的工作空间范围
3. 重新精确测量标定板尺寸
4. 使用 RealSense SDK 自动读取内参
5. 检查机械臂接口实现

### Q2: 检测不到 ChArUco 角点？

**可能原因：**
1. 标定板不在相机视野内
2. 标定板距离相机太近或太远
3. 光照条件不好
4. 标定板打印质量差

**解决方法：**
1. 调整机械臂位置，确保标定板完整可见
2. 保持标定板距离相机 30-80cm
3. 使用均匀的环境光照
4. 使用高质量打印机，确保边缘清晰

### Q3: 如何生成 ChArUco 标定板？

使用 OpenCV 生成：

```python
import cv2
import numpy as np

# 创建 ArUco 字典
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# 创建 ChArUco 板
board = cv2.aruco.CharucoBoard(
    (7, 5),      # 列数, 行数
    0.040,       # 方格边长（米）
    0.030,       # 二维码边长（米）
    aruco_dict
)

# 生成图像（A4 纸：210mm x 297mm，300 DPI）
img = board.generateImage((2480, 3508))  # 像素尺寸

# 保存
cv2.imwrite("charuco_board.png", img)
```

### Q4: 机械臂接口返回的位姿格式不对？

使用 `robot_interface.py` 中的辅助函数转换：

```python
# 情况 1: [x, y, z, rx, ry, rz] 格式
matrix = RobotInterface.pose_to_matrix(x, y, z, rx, ry, rz, rotation_type="euler_xyz")

# 情况 2: 四元数 [x, y, z, qx, qy, qz, qw]
matrix = RobotInterface.quaternion_to_matrix(x, y, z, qx, qy, qz, qw)

# 情况 3: 已经是 4x4 矩阵
# 直接返回即可
```

### Q5: 如何在实际应用中使用标定结果？

```python
import numpy as np

# 加载标定结果
T_end_to_cam = np.load("calibration_data/T_end_to_cam.npy")

# 示例：将相机检测到的物体坐标转换到机器人基座坐标系
def camera_to_base(point_in_camera, robot_pose):
    """
    Args:
        point_in_camera: 物体在相机坐标系下的坐标 [x, y, z]
        robot_pose: 当前机械臂位姿 (4x4 矩阵)
    Returns:
        物体在基座坐标系下的坐标 [x, y, z]
    """
    # 转换为齐次坐标
    point_homo = np.append(point_in_camera, 1)

    # 相机 -> 末端 -> 基座
    T_cam_to_end = np.linalg.inv(T_end_to_cam)
    point_in_base = robot_pose @ T_cam_to_end @ point_homo

    return point_in_base[:3]
```

## 技术支持

如有问题，请检查：
1. 所有依赖库是否正确安装
2. RealSense 相机是否正常连接
3. 机械臂接口是否正确实现
4. 标定板参数是否准确测量

## 许可证

本项目仅供学习和研究使用。

---

**祝标定顺利！** 🎯