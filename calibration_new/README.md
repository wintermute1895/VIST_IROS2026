# 手眼标定系统使用指南

## 📁 文件结构

```
calibration_new/
├── config.py              # 超级配置中心
├── robot_interface.py     # 机器人接口与仿真
├── main.py               # 主程序入口
└── README.md             # 本文档
```

## 🎯 系统特点

1. **高度模块化**: 三个文件实现完整功能
2. **通用配置**: 通过修改 `config.py` 适配不同机器人
3. **纯软件仿真**: 无需硬件即可验证算法正确性
4. **双模式支持**: Eye-in-Hand 和 Eye-to-Hand

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install numpy scipy opencv-contrib-python
# 如果需要使用真实相机
pip install pyrealsense2
```

### 2. 仿真验证（推荐首先运行）

```bash
python main.py --mode simulate
```

这个模式会：
- 生成 20 组合成数据
- 运行标定算法
- 对比计算结果与 Ground Truth
- 输出误差分析

**预期结果**: 平移误差 < 1mm，旋转误差 < 1°

### 3. 配置你的机器人

编辑 `config.py` 中的 `ROBOT_POSE_FMT`:

```python
ROBOT_POSE_FMT = {
    'type': 'euler',        # 'euler', 'quat', 'rotvec', 'matrix'
    'unit': 'rad',          # 'rad' 或 'deg'
    'seq': 'xyz',           # 欧拉角顺序
    'is_position_first': True,
    'position_unit': 'm',   # 'm' 或 'mm'
}
```

### 4. 真实数据采集

```python
# 在 main.py 中实现你的机器人接口
from robot_interface import RobotInterface, process_raw_pose
import config

class MyRobot(RobotInterface):
    def get_pose(self):
        # 从你的机器人 SDK 获取位姿
        raw_pose = your_robot_sdk.get_pose()  # 例如: [x, y, z, rx, ry, rz]

        # 使用通用转换器转换为 4x4 矩阵
        return process_raw_pose(raw_pose, config.ROBOT_POSE_FMT)

# 运行采集
robot = MyRobot()
collector = DataCollector(robot)
collector.collect()
```

### 5. 标定解算

```bash
python main.py --mode calibrate
```

## 📐 ChArUco 标定板制作

### 生成标定板

```python
import cv2
import config

board = config.get_charuco_board()
aruco_dict = cv2.aruco.getPredefinedDictionary(config.CHARUCO_CONFIG['dict_type'])

# 生成图像 (A4 纸: 2480x3508 像素 @ 300 DPI)
board_image = board.generateImage((2480, 3508), marginSize=50)
cv2.imwrite('charuco_board.png', board_image)
```

### ⚠️ 重要：精确测量

打印后**必须**用卡尺测量实际尺寸，并更新 `config.py`:

```python
CHARUCO_CONFIG = {
    'square_size': 0.040,  # 实际测量值（米）
    'marker_size': 0.030,  # 实际测量值（米）
}
```

## 🔧 适配不同机器人

### 示例 1: UR 机器人（轴角表示）

```python
ROBOT_POSE_FMT = {
    'type': 'rotvec',
    'unit': 'rad',
    'is_position_first': True,
    'position_unit': 'm',
}
```

### 示例 2: ABB 机器人（四元数 w,x,y,z）

```python
ROBOT_POSE_FMT = {
    'type': 'quat',
    'quat_format': 'wxyz',
    'is_position_first': True,
    'position_unit': 'mm',  # ABB 通常用毫米
}
```

### 示例 3: KUKA 机器人（ZYX 外旋）

```python
ROBOT_POSE_FMT = {
    'type': 'euler',
    'unit': 'deg',
    'seq': 'ZYX',  # 大写表示外旋（固定坐标系）
    'is_position_first': True,
    'position_unit': 'm',
}
```

## 🧪 验证数学正确性

仿真模式的核心价值：

1. **设定 Ground Truth**: 在 `config.py` 中设定已知的手眼矩阵
2. **生成合成数据**: 根据运动学链反推相机应该看到的标定板位姿
3. **运行标定**: 使用生成的数据执行标定算法
4. **对比结果**: 计算结果与 Ground Truth 的误差

如果误差极小（< 1mm, < 1°），说明：
- 位姿转换逻辑正确
- 运动学链计算正确
- 标定算法实现正确

## 📊 标定结果

标定完成后会生成：

```
calibration_data/
├── hand_eye_matrix.npy      # 4x4 变换矩阵（numpy 格式）
├── calibration_result.json  # 结果详情（JSON 格式）
├── robot_poses.npy          # 机器人位姿数据
└── images/                  # 采集的图像
    ├── image_000.png
    ├── image_001.png
    └── ...
```

## 🔍 常见问题

### Q1: 仿真模式误差很大？

检查：
- `ROBOT_POSE_FMT` 配置是否正确
- `CALIBRATION_MODE` 是否匹配 Ground Truth

### Q2: 真实标定结果不准？

检查：
- ChArUco 板尺寸是否精确测量
- 相机内参是否正确
- 采集的位姿是否多样化（不同角度、距离）
- 至少采集 15-20 组数据

### Q3: 如何验证标定结果？

1. 使用标定结果进行坐标变换
2. 在已知位置放置物体，验证变换后的坐标
3. 重复标定多次，检查结果一致性

## 📚 数学原理

### Eye-in-Hand 模式

```
AX = XB

A: T_base_to_flange (机器人运动)
B: T_camera_to_board (标定板在相机中的位姿)
X: T_flange_to_camera (要求解的手眼矩阵)
```

### Eye-to-Hand 模式

```
AX = ZB

A: T_base_to_flange (机器人运动)
X: T_base_to_camera (要求解的眼到手矩阵)
Z: T_camera_to_board (标定板在相机中的位姿)
B: T_flange_to_board (标定板相对法兰，通常为单位矩阵)
```

## 🎓 进阶使用

### 自定义噪声参数

```python
SIMULATION_CONFIG = {
    'pixel_noise_std': 0.5,           # 像素噪声标准差
    'pose_noise_translation': 0.0001, # 位置噪声（米）
    'pose_noise_rotation': 0.001,     # 旋转噪声（弧度）
}
```

### 修改标定算法

```python
CALIBRATION_PARAMS = {
    'method': cv2.CALIB_HAND_EYE_TSAI,  # 或 PARK, HORAUD, ANDREFF, DANIILIDIS
    'min_samples': 10,
}
```

## 📞 技术支持

如有问题，请检查：
1. 配置文件是否正确
2. 运行仿真模式验证算法
3. 查看详细的错误信息

---

**祝标定顺利！** 🎉
