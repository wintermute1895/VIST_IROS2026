# 相机管理系统 (Camera Manager)

多RealSense相机管理和数据同步系统，支持D435i和D405相机。

## 功能特性

- 支持同时管理多个RealSense相机（D435i, D405）
- 通过序列号精确识别每个相机，避免混淆
- 发布彩色图像和深度图像到ROS2话题
- 发布相机内参信息（CameraInfo）
- 支持rosbag2数据记录
- 可配置的分辨率和帧率

## 安装依赖

```bash
# 安装pyrealsense2
pip install pyrealsense2

# 安装ROS2依赖
sudo apt install ros-humble-cv-bridge
```

## 使用步骤

### 1. 查找相机序列号

首先连接所有相机，然后运行：

```bash
cd /home/ilex/Dev/VIST
source install/setup.bash
ros2 run camera_manager list_cameras
```

这会列出所有连接的相机及其序列号，例如：
```
检测到 3 个RealSense相机：

相机 #1:
  名称: Intel RealSense D435I
  序列号: 123456789
  固件版本: 5.12.7.100
  ...
```

### 2. 配置相机

编辑配置文件 `src/camera_manager/config/camera_config.yaml`，填入实际的序列号：

```yaml
camera_configs:
  - serial_number: "123456789"  # 替换为实际序列号
    camera_name: "mediapipe_camera"
    enable_color: true
    enable_depth: true
    color_width: 640
    color_height: 480
    color_fps: 30
```

### 3. 编译包

```bash
cd /home/ilex/Dev/VIST
colcon build --packages-select camera_manager
source install/setup.bash
```

### 4. 启动多相机系统

```bash
ros2 launch camera_manager multi_realsense.launch.py
```

### 5. 查看发布的话题

```bash
# 查看所有相机话题
ros2 topic list | grep camera

# 查看特定相机的图像
ros2 topic echo /mediapipe_camera/color/image_raw
ros2 topic echo /robot_head_camera/depth/image_raw
```

### 6. 记录数据

```bash
# 记录所有相机数据
ros2 bag record -a

# 或者只记录特定相机
ros2 bag record /mediapipe_camera/color/image_raw /mediapipe_camera/depth/image_raw
```

## 话题说明

每个相机会发布以下话题：

- `/{camera_name}/color/image_raw` - 彩色图像 (sensor_msgs/Image)
- `/{camera_name}/color/camera_info` - 彩色相机内参 (sensor_msgs/CameraInfo)
- `/{camera_name}/depth/image_raw` - 深度图像 (sensor_msgs/Image)
- `/{camera_name}/depth/camera_info` - 深度相机内参 (sensor_msgs/CameraInfo)

## 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| serial_number | 相机序列号（必填） | - |
| camera_name | 相机名称（用于话题命名） | - |
| enable_color | 是否启用彩色流 | true |
| enable_depth | 是否启用深度流 | true |
| color_width | 彩色图像宽度 | 640 |
| color_height | 彩色图像高度 | 480 |
| color_fps | 彩色图像帧率 | 30 |
| depth_width | 深度图像宽度 | 640 |
| depth_height | 深度图像高度 | 480 |
| depth_fps | 深度图像帧率 | 30 |
| publish_rate | 发布频率 (Hz) | 30.0 |

## 相机用途建议

根据你的需求，建议配置：

1. **MediaPipe骨骼捕捉相机** (D435i)
   - camera_name: `mediapipe_camera`
   - 分辨率: 640x480 @ 30fps
   - 用途: 捕捉操作者骨骼动作和意图计算

2. **机器人头顶相机** (D435i)
   - camera_name: `robot_head_camera`
   - 分辨率: 1280x720 @ 30fps
   - 用途: 数据采集和模型训练

3. **手部精细操作相机** (D405)
   - camera_name: `hand_camera`
   - 分辨率: 640x480 @ 30fps
   - 用途: 近距离手部精细操作

## 故障排查

### 相机无法检测

```bash
# 检查USB连接
lsusb | grep Intel

# 检查RealSense驱动
rs-enumerate-devices
```

### 相机启动失败

- 确认序列号正确
- 检查USB端口供电是否充足（建议使用USB 3.0）
- 确认没有其他程序占用相机

### 帧率不稳定

- 降低分辨率或帧率
- 使用USB 3.0端口
- 减少同时运行的相机数量

## 与遥操作系统集成

相机系统可以与现有的遥操作系统配合使用：

```bash
# 终端1: 启动相机系统
ros2 launch camera_manager multi_realsense.launch.py

# 终端2: 启动手套控制
bash scripts/start_hand_glove_timed.sh

# 终端3: 启动机械臂遥操作
bash scripts/start_arm_teleop_timed.sh

# 终端4: 记录所有数据
ros2 bag record -a
```

## 时间同步

相机使用硬件时间戳，确保多相机之间的时间同步。ROS2的时间戳会在发布时添加，用于与其他ROS2节点同步。
