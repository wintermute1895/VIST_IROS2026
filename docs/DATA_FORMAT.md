# 数据格式说明
# Data Format Documentation

## ROS2 Bag 数据格式

使用 `ros2 bag record` 采集的数据保存为 **ROS2 Bag 格式**。

### 文件结构

```
exp1_one_euro/
├── metadata.yaml          # 元数据（话题列表、消息类型、时间戳等）
└── exp1_one_euro_0.db3   # SQLite3 数据库文件（实际数据）
```

### 数据库格式

ROS2 Bag 使用 **SQLite3** 数据库存储消息数据：
- 每条消息序列化为二进制格式（CDR 编码）
- 包含时间戳、话题名称、消息类型等元数据

## 相机数据话题

### 1. 彩色图像 (`/camera/color/image_raw`)

**消息类型**: `sensor_msgs/msg/Image`

**数据格式**:
- **编码**: `rgb8` (24-bit RGB)
- **分辨率**: 848x480 (默认) 或 1280x720
- **帧率**: 30 fps (默认)
- **数据大小**: 约 1.2 MB/帧 (848x480) 或 2.7 MB/帧 (1280x720)

**字段**:
```yaml
header:
  stamp: {sec: 1234567890, nanosec: 123456789}
  frame_id: "camera_color_optical_frame"
height: 480
width: 848
encoding: "rgb8"
is_bigendian: 0
step: 2544  # width * 3 (RGB)
data: [...]  # 原始像素数据
```

### 2. 深度图像 (`/camera/depth/image_raw`)

**消息类型**: `sensor_msgs/msg/Image`

**数据格式**:
- **编码**: `16UC1` (16-bit 无符号整数)
- **分辨率**: 848x480 (默认)
- **帧率**: 30 fps (默认)
- **单位**: 毫米 (mm)
- **数据大小**: 约 0.8 MB/帧

**深度值解释**:
- 0 = 无效深度
- 1-65535 = 深度值（毫米）
- 例如: 1000 = 1 米

### 3. 相机参数 (`/camera/color/camera_info`)

**消息类型**: `sensor_msgs/msg/CameraInfo`

**数据格式**:
```yaml
header:
  stamp: {sec: 1234567890, nanosec: 123456789}
  frame_id: "camera_color_optical_frame"
height: 480
width: 848
distortion_model: "plumb_bob"
D: [0.0, 0.0, 0.0, 0.0, 0.0]  # 畸变系数
K: [...]  # 3x3 内参矩阵
R: [...]  # 3x3 旋转矩阵
P: [...]  # 3x4 投影矩阵
```

### 4. 手部姿态 (`/hand_pose`) (如果启用)

**消息类型**: `geometry_msgs/msg/PoseStamped`

**数据格式**:
```yaml
header:
  stamp: {sec: 1234567890, nanosec: 123456789}
  frame_id: "camera_color_optical_frame"
pose:
  position: {x: 0.5, y: 0.2, z: 0.8}  # 米
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}  # 四元数
```

## 机械臂数据话题

### 1. 外骨骼原始数据 (`/right_arm_joint_control`)

**消息类型**: `sensor_msgs/msg/JointState`

**数据格式**:
```yaml
header:
  stamp: {sec: 1234567890, nanosec: 123456789}
name: ['joint51', 'joint52', 'joint53', 'joint54', 'joint55', 'joint56', 'joint57']
position: [0.2, -0.7, -2.1, 3.5, -4.1, 1.2, 0.0]  # 弧度
velocity: []  # 通常为空
effort: []    # 通常为空
```

### 2. 滤波后数据 (`/filtered_right_joint_control`)

**消息类型**: `sensor_msgs/msg/JointState`

**数据格式**: 与原始数据相同，但经过滤波处理

### 3. 机械臂状态 (`/right_arm/joint_states`)

**消息类型**: `sensor_msgs/msg/JointState`

**数据格式**: 机械臂实际关节角度（来自编码器反馈）

## 数据大小估算

### 30 秒数据采集（不含相机）

| 话题 | 频率 | 消息大小 | 总大小 |
|------|------|---------|--------|
| `/right_arm_joint_control` | 80 Hz | ~200 B | ~480 KB |
| `/filtered_right_joint_control` | 80 Hz | ~200 B | ~480 KB |
| `/right_arm/joint_follow` | 80 Hz | ~300 B | ~720 KB |
| `/right_arm/joint_states` | 50 Hz | ~200 B | ~300 KB |
| `/filter_performance` | 80 Hz | ~100 B | ~240 KB |

**总计**: 约 **2.2 MB**

### 30 秒数据采集（含相机）

| 话题 | 频率 | 消息大小 | 总大小 |
|------|------|---------|--------|
| 机械臂数据 | - | - | ~2.2 MB |
| `/camera/color/image_raw` | 30 Hz | ~1.2 MB | ~36 MB |
| `/camera/depth/image_raw` | 30 Hz | ~0.8 MB | ~24 MB |
| `/camera/color/camera_info` | 30 Hz | ~1 KB | ~30 KB |

**总计**: 约 **62 MB**

## 数据读取和分析

### 查看 Bag 信息

```bash
ros2 bag info data/exp_right_arm_only_20260225/exp1_one_euro
```

### 播放 Bag 数据

```bash
ros2 bag play data/exp_right_arm_only_20260225/exp1_one_euro
```

### Python 读取示例

```python
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Image, JointState
import cv2
import numpy as np

# 打开 bag 文件
storage_options = StorageOptions(uri='exp1_one_euro', storage_id='sqlite3')
converter_options = ConverterOptions('', '')
reader = SequentialReader()
reader.open(storage_options, converter_options)

# 读取消息
while reader.has_next():
    topic, data, timestamp = reader.read_next()
    
    if topic == '/camera/color/image_raw':
        msg = deserialize_message(data, Image)
        # 转换为 OpenCV 格式
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        cv2.imshow('Camera', img)
        cv2.waitKey(1)
    
    elif topic == '/right_arm_joint_control':
        msg = deserialize_message(data, JointState)
        print(f"Joint positions: {msg.position}")
```

### 导出为其他格式

**导出图像序列**:
```bash
# 使用 image_transport 工具
ros2 run image_transport republish raw in:=/camera/color/image_raw out:=/camera/color/image_compressed
```

**导出为 CSV**:
```python
import pandas as pd

# 读取关节数据并保存为 CSV
joint_data = []
# ... 读取 bag 数据 ...
df = pd.DataFrame(joint_data, columns=['timestamp', 'j1', 'j2', 'j3', 'j4', 'j5', 'j6', 'j7'])
df.to_csv('joint_data.csv', index=False)
```

## 数据压缩

ROS2 Bag 支持压缩以减小文件大小：

```bash
# 录制时启用压缩
ros2 bag record -o exp1_compressed --compression-mode file --compression-format zstd /camera/color/image_raw

# 压缩现有 bag
ros2 bag compress exp1_one_euro --compression-mode file --compression-format zstd
```

**压缩率**: 通常可减小 50-70% 的文件大小

---

更新日期: 2026-02-25
