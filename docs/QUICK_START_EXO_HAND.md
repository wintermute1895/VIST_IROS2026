# 外骨骼遥操 + 数据手套 - 快速启动

## 🚀 一键启动（推荐）

### 完整系统（臂 + 手指）

**终端1** - 数据手套：
```bash
cd ~/Dev/VIST/external_sdk/linkerhand-ros2-sdk
source install/setup.bash
sudo ip link set can0 up type can bitrate 1000000
ros2 launch linker_hand_ros2_sdk linker_hand.launch.py
```

**终端2** - 外骨骼遥操：
```bash
cd ~/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop.launch.py
```

**终端3** - 数据采集：
```bash
cd ~/Dev/VIST
./scripts/test_exo_teleop_pipeline.sh 30 my_task
```

## 📊 采集的数据

### 臂数据（7个关节）
- `/right_arm_joint_control` - 外骨骼原始 ~250Hz
- `/robot1/right_arm/joint_follow` - 跟随命令 ~250Hz
- `/robot1/right_arm/joint_states` - 真机反馈 ~50Hz

### 手指数据（10个关节 - L10）
- `/cb_left_hand_control_cmd` - 手指命令 ~30Hz
- `/cb_left_hand_state` - 手指反馈 ~40Hz

### 视觉数据
- `/camera/color/image_raw` - RGB ~30Hz
- `/camera/depth/image_rect_raw` - 深度 ~30Hz

## 🔍 快速验证

```bash
# 检查所有topics
ros2 topic list | grep -E "arm|hand|camera"

# 查看频率
ros2 topic hz /right_arm_joint_control
ros2 topic hz /cb_left_hand_state

# 查看手指数据
ros2 topic echo /cb_left_hand_state --once
```

## 📁 数据位置

```
data/collection/<task_name>_<timestamp>/
├── rosbag/                    # ROS2 bag数据
├── metadata.json              # 元数据（包含has_hand_data标志）
├── frequency_report.json      # 频率分析
└── sync_report.json           # 时间同步报告
```

## ⚠️ 常见问题

### 找不到can0
```bash
sudo ip link set can0 up type can bitrate 1000000
```

### 手指topic不存在
检查数据手套是否启动：
```bash
ros2 node list | grep linker_hand
```

### 录制文件太大
- 降低相机分辨率到424x240
- 或不录制相机数据

## 📖 详细文档

- 完整指南: [docs/EXO_TELEOP_WITH_HAND_GUIDE.md](EXO_TELEOP_WITH_HAND_GUIDE.md)
- 仅臂控制: [docs/EXO_TELEOP_TEST_GUIDE.md](EXO_TELEOP_TEST_GUIDE.md)
