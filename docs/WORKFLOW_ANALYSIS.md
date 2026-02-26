# VIST系统完整工作流程分析

**基于实际运行的脚本序列**

---

## 📋 脚本启动顺序

```bash
1. ./scripts/start_camera.sh
2. ./scripts/startup/start_vist_filter.sh
3. bash scripts/start_6_dexterous_hand.sh left
4. ./scripts/start_left_arm_teleop.sh
5. ros2 launch lbot_driver lbot_start_driver.launch.py
6. ./scripts/start_teleop_bridge.sh
7. ./scripts/start_hand_keyboard.sh
8. ./scripts/experiment/collect_experiment.sh
```

---

## 🔍 详细分析

### 1. start_camera.sh - 相机节点

**启动的节点**:
- `realsense_camera_node`

**发布的Topic**:
- `/camera/color/image_raw` (sensor_msgs/Image) - 彩色图像
- `/camera/color/camera_info` (sensor_msgs/CameraInfo) - 相机内参
- `/camera/depth/image_rect_raw` (sensor_msgs/Image) - 深度图像（如果启用）

**订阅的Topic**: 无

**功能**: 采集RealSense D435i相机的图像数据

---

### 2. start_vist_filter.sh - VIST滤波器节点

**启动的节点**:
- `vist_filter_node`

**订阅的Topic**:
- `/left_arm_joint_control` (sensor_msgs/JointState) - 外骨骼原始数据

**发布的Topic**:
- `/filtered_left_joint_control` (sensor_msgs/JointState) - 滤波后的关节数据
- `/filter_performance` (自定义消息) - 滤波器性能指标

**功能**: 对外骨骼数据进行滤波处理（支持passthrough, ema, one_euro, vist_kalman）

**配置文件**: `config/vist_filter_config.yaml`

---

### 3. start_6_dexterous_hand.sh left - 灵巧手节点

**启动的节点**:
- `linker_hand_advanced_l10`

**订阅的Topic**:
- `/cb_left_hand_control_cmd` (sensor_msgs/JointState) - 手部控制命令

**发布的Topic**:
- `/cb_left_hand_state` (sensor_msgs/JointState) - 手部状态反馈

**功能**: 通过CAN0控制Linker Hand L10灵巧手

**参数**:
- `--hand_type left` - 左手
- `--can can0` - CAN接口
- `--is_touch false` - 不启用触觉传感器

---

### 4. start_left_arm_teleop.sh - 外骨骼节点

**启动的节点**:
- `linkerta_node`

**订阅的Topic**: 无

**发布的Topic**:
- `/left_arm_joint_control` (sensor_msgs/JointState) - 左臂关节状态（7个关节）

**功能**: 通过CAN1读取Linkerta外骨骼的关节角度

**配置文件**: `external_sdk/arm_teleop/src/linkerta/config/lta.yaml`
- CAN接口: can1
- 波特率: 1000000

---

### 5. lbot_start_driver.launch.py - 机械臂驱动

**启动的节点**:
- `robot1.lbot_main_node` - 主节点
- `robot1.lbot_left_arm_node` - 左臂服务节点
- `robot1.lbot_right_arm_node` - 右臂服务节点

**订阅的Topic**:
- `/robot1/left_arm/joint_follow` (sensor_msgs/JointState) - 左臂跟随命令
- `/robot1/right_arm/joint_follow` (sensor_msgs/JointState) - 右臂跟随命令

**发布的Topic**:
- `/robot1/left_arm/joint_states` (sensor_msgs/JointState) - 左臂状态反馈
- `/robot1/left_arm/pose_states` (geometry_msgs/PoseStamped) - 左臂位姿
- `/robot1/right_arm/joint_states` (sensor_msgs/JointState) - 右臂状态反馈
- `/robot_joint_states` (sensor_msgs/JointState) - 机器人整体关节状态

**功能**: 通过网络（192.168.10.21）控制LBot机械臂

---

### 6. start_teleop_bridge.sh - 遥操桥接节点

**启动的节点**:
- `teleop_bridge_node`

**订阅的Topic**:
- `/filtered_left_joint_control` (sensor_msgs/JointState) - 滤波后的外骨骼数据

**发布的Topic**:
- `/robot1/left_arm/joint_follow` (sensor_msgs/JointState) - 机械臂左臂控制命令

**功能**:
- 连接滤波后的外骨骼数据到机械臂控制
- 进行关节映射和方向转换
- 实现跟随模式控制

**配置文件**: `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`
- 关节方向映射: `negation: [1, 1, 1, -1, 1, 1, 1, ...]`
- 缩放比例: 1.0
- 跟随模式: true

---

### 7. start_hand_keyboard.sh - 手部键盘控制

**启动的节点**: 无（Python脚本，不是ROS2节点）

**发布的Topic**:
- `/cb_left_hand_control_cmd` (sensor_msgs/JointState) - 手部控制命令

**订阅的Topic**:
- `/cb_left_hand_state` (sensor_msgs/JointState) - 手部状态（用于显示）

**功能**: 通过键盘控制灵巧手的开合

**脚本**: `scripts/hand_control.py`

---

### 8. collect_experiment.sh - 数据采集

**启动的节点**: 无（使用ros2 bag record）

**录制的Topic**:
- `/camera/color/image_raw` - 彩色图像
- `/camera/depth/image_rect_raw` - 深度图像
- `/camera/color/camera_info` - 相机内参
- `/left_arm_joint_control` - 外骨骼原始数据
- `/filtered_left_joint_control` - 滤波后数据
- `/cb_left_hand_control_cmd` - 手部控制命令
- `/cb_left_hand_state` - 手部状态
- `/robot_joint_states` - 机器人关节状态
- `/filter_performance` - 滤波器性能
- `/robot1/left_arm/joint_states` - 左臂状态
- `/robot1/left_arm/joint_follow` - 左臂控制命令
- `/robot1/left_arm/pose_states` - 左臂位姿
- `/vist_performance` - 系统性能指标

**功能**:
- 录制所有关键topic的数据
- 生成实验元数据（metadata.yaml）
- 支持指定录制时长

**参数**:
- 第1个参数: 录制时长（秒，默认60）
- 第2个参数: 实验名称（默认: peg_in_hole_时间戳）

---

## 🔄 完整数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│                        VIST系统数据流                            │
└─────────────────────────────────────────────────────────────────┘

📹 相机 (realsense_camera_node)
   └─> /camera/color/image_raw
   └─> /camera/depth/image_rect_raw
   └─> /camera/color/camera_info

🦾 外骨骼 (linkerta_node) [CAN1]
   └─> /left_arm_joint_control
         └─> 🔄 滤波器 (vist_filter_node)
               ├─> /filtered_left_joint_control
               │     └─> 🔗 遥操桥接 (teleop_bridge_node)
               │           └─> /robot1/left_arm/joint_follow
               │                 └─> 🤖 机械臂 (lbot_main_node) [网络]
               │                       ├─> /robot1/left_arm/joint_states
               │                       ├─> /robot1/left_arm/pose_states
               │                       └─> /robot_joint_states
               └─> /filter_performance

⌨️ 键盘控制 (hand_control.py)
   └─> /cb_left_hand_control_cmd
         └─> 🤚 灵巧手 (linker_hand_advanced_l10) [CAN0]
               └─> /cb_left_hand_state

📊 数据采集 (ros2 bag record)
   └─> 录制所有上述topic
```

---

## 📊 节点通信矩阵

| 节点 | 订阅 | 发布 | 通信方式 |
|------|------|------|---------|
| realsense_camera_node | - | /camera/* | USB |
| linkerta_node | - | /left_arm_joint_control | CAN1 |
| vist_filter_node | /left_arm_joint_control | /filtered_left_joint_control, /filter_performance | ROS2 |
| teleop_bridge_node | /filtered_left_joint_control | /robot1/left_arm/joint_follow | ROS2 |
| lbot_main_node | /robot1/left_arm/joint_follow | /robot1/left_arm/joint_states, /robot1/left_arm/pose_states | 网络 |
| linker_hand_advanced_l10 | /cb_left_hand_control_cmd | /cb_left_hand_state | CAN0 |
| hand_control.py | /cb_left_hand_state | /cb_left_hand_control_cmd | ROS2 |

---

## 🎯 关键数据链路

### 链路1: 外骨骼 → 机械臂

```
外骨骼(CAN1)
  → /left_arm_joint_control (80Hz)
    → 滤波器
      → /filtered_left_joint_control (80Hz)
        → 遥操桥接
          → /robot1/left_arm/joint_follow (80Hz)
            → 机械臂(网络)
              → /robot1/left_arm/joint_states (反馈)
```

**延迟**: 约12.5ms（80Hz）
**滤波器**: VIST Kalman / One-Euro
**关节映射**: 1:1，第4个关节方向反转

### 链路2: 键盘 → 灵巧手

```
键盘控制
  → /cb_left_hand_control_cmd (按键触发)
    → 灵巧手(CAN0)
      → /cb_left_hand_state (反馈)
```

**控制方式**: 离散命令（开/合/预设姿态）
**通信**: CAN总线，1Mbps

### 链路3: 相机 → 数据采集

```
相机(USB)
  → /camera/color/image_raw (12-15Hz)
  → /camera/depth/image_rect_raw (如果启用)
  → /camera/color/camera_info
    → 数据采集(rosbag)
```

**分辨率**: 848x480
**深度流**: 可选（当前禁用以提高帧率）

---

## ⚙️ 配置文件总结

| 组件 | 配置文件 | 关键参数 |
|------|---------|---------|
| 相机 | scripts/start_camera.sh | 分辨率: 848x480, FPS: 30, 深度流: 禁用 |
| 外骨骼 | external_sdk/arm_teleop/src/linkerta/config/lta.yaml | CAN: can1, 波特率: 1000000 |
| 滤波器 | config/vist_filter_config.yaml | 滤波类型: vist_kalman/one_euro |
| 遥操桥接 | external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml | 关节映射, 方向反转 |
| 灵巧手 | external_sdk/linkerhand-ros2-sdk/.../config/setting.yaml | CAN: can0, 手部: left |

---

## 🔧 系统性能指标

| 指标 | 值 | 备注 |
|------|---|------|
| 外骨骼频率 | ~80 Hz | 稳定 |
| 滤波器频率 | ~80 Hz | 与输入同步 |
| 相机频率 | ~12-15 Hz | 禁用深度流后 |
| 键盘控制 | 事件驱动 | 按键触发 |
| 端到端延迟 | ~25-50 ms | 外骨骼→机械臂 |

---

## 📝 实验数据结构

```
data/experiments/
└── peg_in_hole_20260226_HHMMSS/
    ├── metadata.yaml          # 实验元数据
    ├── rosbag2_*.db3         # 数据库文件
    └── metadata.yaml         # rosbag元数据
```

**metadata.yaml 内容**:
- 实验名称和类型
- 时间戳
- 组件列表
- Topic列表

---

## 🚀 启动检查清单

使用此清单确保系统正确启动：

- [ ] CAN0和CAN1已启动（`ip link show can0 can1`）
- [ ] 相机节点运行（`ros2 node list | grep realsense`）
- [ ] 外骨骼节点运行（`ros2 node list | grep linkerta`）
- [ ] 滤波器节点运行（`ros2 node list | grep vist_filter`）
- [ ] 灵巧手节点运行（`ros2 node list | grep linker_hand`）
- [ ] 机械臂驱动运行（`ros2 node list | grep lbot`）
- [ ] 遥操桥接运行（`ros2 node list | grep teleop_bridge`）
- [ ] 所有topic正常发布（`ros2 topic list`）
- [ ] 频率正常（`ros2 topic hz /left_arm_joint_control`）

---

## 🎓 总结

**系统组成**:
- 8个脚本
- 7个ROS2节点（+ 1个Python控制脚本）
- 15+ 个Topic
- 3种通信方式（ROS2、CAN、网络）

**数据流**:
- 主链路: 外骨骼 → 滤波 → 桥接 → 机械臂
- 辅助链路: 键盘 → 灵巧手
- 监控链路: 相机 → 数据采集

**关键特性**:
- 实时性: 80Hz控制频率
- 滤波: VIST Kalman滤波器
- 安全性: 急停按钮支持
- 可追溯: 完整数据记录

---

最后更新: 2026-02-26