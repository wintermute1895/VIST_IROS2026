# 双相机配置指南

本文档说明如何配置和使用两个Intel RealSense相机（D435i + D405）。

## 1. 获取D405相机序列号

在启动相机之前，需要先获取D405相机的序列号：

```bash
# 连接D405相机后运行
rs-enumerate-devices | grep "Serial Number"
```

或者使用Python脚本：

```python
import pyrealsense2 as rs

ctx = rs.context()
devices = ctx.query_devices()

for dev in devices:
    print(f"设备名称: {dev.get_info(rs.camera_info.name)}")
    print(f"序列号: {dev.get_info(rs.camera_info.serial_number)}")
    print("---")
```

## 2. 配置launch文件

编辑 `ros2_ws/src/bringup/launch/camera.launch.py`，将D405的序列号填入：

```python
d405_serial_arg = DeclareLaunchArgument(
    'd405_serial',
    default_value='YOUR_D405_SERIAL_NUMBER',  # 替换为实际序列号
    description='D405 camera serial number'
)
```

## 3. 启动双相机

```bash
ros2 launch bringup camera.launch.py
```

或者指定序列号：

```bash
ros2 launch bringup camera.launch.py d435i_serial:=348122071157 d405_serial:=YOUR_D405_SERIAL
```

## 4. 验证相机话题

启动后，检查话题是否正常发布：

```bash
# 查看所有相机话题
ros2 topic list | grep camera

# 应该看到：
# /camera_d435i/color/image_raw
# /camera_d435i/depth/image_raw
# /camera_d435i/color/camera_info
# /camera_d435i/depth/camera_info
# /camera_d405/color/image_raw
# /camera_d405/depth/image_raw
# /camera_d405/color/camera_info
# /camera_d405/depth/camera_info

# 查看话题频率
ros2 topic hz /camera_d435i/color/image_raw
ros2 topic hz /camera_d405/color/image_raw
```

## 5. 数据录制

运行录制脚本时，两个相机的数据会自动被录制：

```bash
python3 scripts/experiment/collect_experiment.py 60
```

录制的rosbag会包含：
- D435i相机的彩色图像、深度图像和相机信息
- D405相机的彩色图像、深度图像和相机信息
- 所有其他配置的话题

## 6. 相机命名规则

- **D435i（主相机）**: 话题前缀为 `/camera_d435i/`
- **D405（辅助相机）**: 话题前缀为 `/camera_d405/`

## 7. 禁用某个相机

如果只想使用一个相机，可以在 `config/recording_config.yaml` 中禁用：

```yaml
camera_d405_color_image:
  enabled: false  # 禁用D405彩色图像
  topic: "/camera_d405/color/image_raw"
```

## 8. 调整相机参数

可以在launch时指定分辨率和帧率：

```bash
ros2 launch bringup camera.launch.py width:=640 height:=480 fps:=30
```

## 9. 故障排查

### 问题：相机无法启动
- 检查USB连接是否稳定
- 确认序列号是否正确
- 检查是否有足够的USB带宽（建议使用USB 3.0）

### 问题：只有一个相机工作
- 使用 `rs-enumerate-devices` 确认两个相机都被识别
- 检查序列号配置是否正确
- 尝试分别启动两个相机测试

### 问题：录制数据量过大
- 可以在 `recording_config.yaml` 中禁用深度图像
- 降低分辨率或帧率
- 只启用必要的相机

## 10. 性能建议

- 两个相机同时运行需要较高的USB带宽，建议：
  - 使用USB 3.0或更高版本
  - 将两个相机连接到不同的USB控制器
  - 如果带宽不足，可以降低分辨率或帧率
  - 考虑禁用点云功能以节省带宽
