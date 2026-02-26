# VIST系统节点清单与检查指南

**最后更新**: 2026-02-26

---

## 节点概览

VIST系统包含以下ROS2节点：

| 节点名称 | 语言 | 功能 | 源码位置 |
|---------|------|------|---------|
| realsense_camera_node | Python | 相机数据采集 | `src/camera_manager/camera_manager/realsense_camera_node.py` |
| linkerta_node | C++ | 外骨骼数据采集 | `external_sdk/arm_teleop/src/linkerta/src/main_ros2.cpp` |
| unified_filter_node | Python | One-Euro滤波 | `src/nodes/unified_filter_node.py` |
| handretarget_node | Python | 数据手套重定向 | `external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2/...` |
| linker_hand_advanced_l10 | Python | 灵巧手驱动 | `external_sdk/linkerhand-ros2-sdk/...` |
| lbot_main_node | Python | 机械臂主节点 | `external_sdk/arm_teleop/src/lbot_driver/...` |
| lbot_left_arm_node | Python | 机械臂左臂服务 | `external_sdk/arm_teleop/src/lbot_driver/...` |
| lbot_right_arm_node | Python | 机械臂右臂服务 | `external_sdk/arm_teleop/src/lbot_driver/...` |
| teleop_bridge_node | Python | 遥操桥接 | `external_sdk/arm_teleop/src/lbot_teleop/...` |

---

## 节点详细信息

### 1. realsense_camera_node（相机节点）

**语言**: Python
**源码**: `src/camera_manager/camera_manager/realsense_camera_node.py`

**功能**:
- 采集RealSense D435i相机的彩色和深度图像
- 发布图像数据和相机内参

**发布的Topic**:
- `/camera/color/image_raw` (sensor_msgs/Image) - 彩色图像
- `/camera/color/camera_info` (sensor_msgs/CameraInfo) - 相机内参
- `/camera/depth/image_raw` (sensor_msgs/Image) - 深度图像（如果启用）

**参数**:
- `color_width`: 彩色图像宽度（默认: 848）
- `color_height`: 彩色图像高度（默认: 480）
- `color_fps`: 彩色图像帧率（默认: 30）
- `enable_depth`: 是否启用深度流（默认: true）
- `serial_number`: 相机序列号

**配置文件**: `scripts/start_camera.sh`

**查看源码**:
```bash
nano ~/Dev/VIST/src/camera_manager/camera_manager/realsense_camera_node.py
```

---

### 2. linkerta_node（外骨骼节点）

**语言**: C++
**源码**: `external_sdk/arm_teleop/src/linkerta/src/main_ros2.cpp`

**功能**:
- 通过CAN总线读取Linkerta外骨骼的关节角度
- 发布7个关节的状态数据

**发布的Topic**:
- `/left_arm_joint_control` (sensor_msgs/JointState) - 左臂关节状态
- `/right_arm_joint_control` (sensor_msgs/JointState) - 右臂关节状态

**参数**:
- `calibration`: 是否标定（0/1）
- `arm_channel`: CAN接口（can0/can1）
- `arm_baudrate`: CAN波特率（默认: 1000000）

**配置文件**: `external_sdk/arm_teleop/src/linkerta/config/lta.yaml`

**查看源码**:
```bash
nano ~/Dev/VIST/external_sdk/arm_teleop/src/linkerta/src/main_ros2.cpp
```

**关键类**:
- `LinkerArm`: 外骨骼通信类（`src/LinkerArm.h`）
- `CanBus`: CAN总线通信类（`src/CanBus.cpp`）

---

### 3. unified_filter_node（滤波节点）

**语言**: Python
**源码**: `src/nodes/unified_filter_node.py`

**功能**:
- 对关节数据进行滤波处理
- 支持One-Euro、EMA、Kalman等滤波算法

**订阅的Topic**:
- `/left_arm_joint_control` (sensor_msgs/JointState) - 输入数据

**发布的Topic**:
- `/filtered_joint_states` (sensor_msgs/JointState) - 滤波后数据

**参数**:
- `input_topic`: 输入topic名称
- `output_topic`: 输出topic名称
- `filter_type`: 滤波类型（one_euro/ema/kalman）

**配置文件**: `scripts/start_filter.sh`

**查看源码**:
```bash
nano ~/Dev/VIST/src/nodes/unified_filter_node.py
```

---

### 4. handretarget_node（数据手套节点）

**语言**: Python
**源码**: `external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2/...`

**功能**:
- 读取数据手套的传感器数据
- 将手套数据重定向到灵巧手控制命令

**发布的Topic**:
- `/cb_left_hand_control_cmd` (sensor_msgs/JointState) - 左手控制命令
- `/cb_left_hand_control_angle_cmd` (sensor_msgs/JointState) - 左手角度命令

**参数**:
- 标定相关参数

**配置文件**: `scripts/start_5_data_glove.sh`

**查看源码**:
```bash
find ~/Dev/VIST/external_sdk/linkerhand-ros-teleop -name "*retarget*.py"
```

---

### 5. linker_hand_advanced_l10（灵巧手节点）

**语言**: Python
**源码**: `external_sdk/linkerhand-ros2-sdk/...`

**功能**:
- 通过CAN总线控制Linker Hand L10灵巧手
- 订阅控制命令并发送到灵巧手

**订阅的Topic**:
- `/cb_left_hand_control_cmd` (sensor_msgs/JointState) - 控制命令

**参数**:
- `--hand_type`: 手部类型（left/right）
- `--can`: CAN接口（can0/can1）
- `--is_touch`: 是否启用触觉传感器（true/false）

**配置文件**: `external_sdk/linkerhand-ros2-sdk/.../config/setting.yaml`

**查看源码**:
```bash
find ~/Dev/VIST/external_sdk/linkerhand-ros2-sdk -name "*.py" | grep -i hand
```

---

### 6. lbot_main_node（机械臂主节点）

**语言**: Python
**源码**: `external_sdk/arm_teleop/src/lbot_driver/lbot_driver/lbot_driver_node.py`

**功能**:
- 管理机械臂的网络连接
- 监控机械臂状态
- 协调左右臂服务节点

**发布的Topic**:
- `/robot1/left_arm/joint_states` (sensor_msgs/JointState) - 左臂状态
- `/robot1/right_arm/joint_states` (sensor_msgs/JointState) - 右臂状态

**参数**:
- 机械臂IP地址（从launch文件读取）

**配置文件**: `external_sdk/arm_teleop/src/lbot_driver/config/lbot_config.yaml`

**查看源码**:
```bash
nano ~/Dev/VIST/external_sdk/arm_teleop/src/lbot_driver/lbot_driver/lbot_driver_node.py
```

---

### 7. teleop_bridge_node（遥操桥接节点）

**语言**: Python
**源码**: `external_sdk/arm_teleop/src/lbot_teleop/lbot_teleop/teleop_bridge_node.py`

**功能**:
- 连接滤波后的外骨骼数据到机械臂控制
- 进行关节映射和方向转换
- 实现跟随模式控制

**订阅的Topic**:
- `/filtered_joint_states` (sensor_msgs/JointState) - 滤波后的外骨骼数据

**发布的Topic**:
- `/robot1/left_arm/joint_follow` (sensor_msgs/JointState) - 左臂控制命令
- `/robot1/right_arm/joint_follow` (sensor_msgs/JointState) - 右臂控制命令

**参数**:
- `master_left_topic`: 左臂输入topic
- `master_right_topic`: 右臂输入topic
- `scale_factor`: 缩放比例
- `follow_mode`: 跟随模式
- `negation`: 关节方向映射
- `left_joint_mapping`: 左臂关节映射
- `enable_left_arm`: 启用左臂
- `enable_right_arm`: 启用右臂

**配置文件**: `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`

**查看源码**:
```bash
nano ~/Dev/VIST/external_sdk/arm_teleop/src/lbot_teleop/lbot_teleop/teleop_bridge_node.py
```

---

## 节点检查命令

### 查看运行中的节点

```bash
# 列出所有节点
ros2 node list

# 查看节点信息
ros2 node info /realsense_camera_node
ros2 node info /linkerta_node
ros2 node info /unified_filter_node
ros2 node info /teleop_bridge_node
```

### 查看节点的Topic

```bash
# 查看节点发布的topic
ros2 node info /realsense_camera_node | grep Publications

# 查看节点订阅的topic
ros2 node info /teleop_bridge_node | grep Subscriptions
```

### 查看节点参数

```bash
# 列出节点的所有参数
ros2 param list /linkerta_node

# 获取特定参数的值
ros2 param get /linkerta_node arm_channel

# 设置参数（运行时）
ros2 param set /linkerta_node calibration 1
```

### 查看节点日志

```bash
# 实时查看节点日志
ros2 run rqt_console rqt_console

# 或使用命令行
ros2 topic echo /rosout
```

---

## 源码查找技巧

### 1. 查找Python节点

```bash
# 查找所有Python节点
find ~/Dev/VIST -name "*.py" -path "*/nodes/*"

# 搜索特定功能
grep -r "class.*Node" ~/Dev/VIST/src --include="*.py"
```

### 2. 查找C++节点

```bash
# 查找C++主文件
find ~/Dev/VIST -name "main*.cpp"

# 查找ROS2节点定义
grep -r "rclcpp::Node" ~/Dev/VIST/external_sdk --include="*.cpp"
```

### 3. 查找配置文件

```bash
# 查找YAML配置
find ~/Dev/VIST -name "*.yaml" -o -name "*.yml"

# 查找launch文件
find ~/Dev/VIST -name "*.launch.py"
```

---

## 节点依赖关系

```
相机节点 (realsense_camera_node)
  └─> /camera/color/image_raw

外骨骼节点 (linkerta_node)
  └─> /left_arm_joint_control
        └─> 滤波节点 (unified_filter_node)
              └─> /filtered_joint_states
                    └─> 遥操桥接节点 (teleop_bridge_node)
                          └─> /robot1/left_arm/joint_follow
                                └─> 机械臂节点 (lbot_main_node)

数据手套节点 (handretarget_node)
  └─> /cb_left_hand_control_cmd
        └─> 灵巧手节点 (linker_hand_advanced_l10)
```

---

## 快速检查清单

使用此清单快速检查所有节点：

```bash
# 1. 检查所有节点是否运行
ros2 node list

# 2. 检查每个节点的状态
for node in $(ros2 node list); do
    echo "=== $node ==="
    ros2 node info $node
    echo ""
done

# 3. 检查所有topic
ros2 topic list

# 4. 检查topic频率
ros2 topic hz /camera/color/image_raw &
ros2 topic hz /left_arm_joint_control &
ros2 topic hz /filtered_joint_states &
ros2 topic hz /cb_left_hand_control_cmd &
```

---

## 调试技巧

### 1. 查看节点输出

```bash
# 启动节点时查看详细输出
ros2 run <package> <node> --ros-args --log-level debug
```

### 2. 使用rqt工具

```bash
# 节点图可视化
rqt_graph

# 参数配置
rqt_reconfigure

# 日志查看
rqt_console
```

### 3. 录制和回放

```bash
# 录制特定节点的输出
ros2 bag record /left_arm_joint_control /filtered_joint_states

# 回放数据
ros2 bag play <bag_file>
```

---

## 常见问题

### 节点无法启动

1. 检查ROS2环境是否source
2. 检查包是否编译
3. 查看错误日志

### 节点运行但无输出

1. 检查topic名称是否正确
2. 检查节点参数配置
3. 使用`ros2 topic echo`查看数据

### C++节点难以理解

1. 先看头文件（.h）了解接口
2. 查看main函数了解初始化流程
3. 关注ROS2相关的回调函数

---

## 参考资源

- ROS2文档: https://docs.ros.org/en/humble/
- RealSense SDK: https://github.com/IntelRealSense/librealsense
- 项目文档: `docs/`目录

---

最后更新: 2026-02-26