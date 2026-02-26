# VIST系统完整启动指南

**最后更新**: 2026-02-26
**系统版本**: ROS2 Humble

---

## 系统概述

VIST系统包含以下组件：
- **相机**: RealSense D435i（序列号: 348122071157）
- **遥操臂**: Linkerta外骨骼（CAN1）
- **数据手套**: 左手数据手套（USB）
- **灵巧手**: Linker Hand L10（CAN0）
- **滤波器**: One-Euro滤波器
- **机械臂**: LBot机械臂（192.168.10.21）
- **遥操桥接**: 连接滤波器输出到机械臂

**数据流**:
```
外骨骼(CAN1) → /left_arm_joint_control → 滤波器 → /filtered_joint_states → 遥操桥接 → 机械臂
数据手套(USB) → /cb_left_hand_control_cmd → 灵巧手(CAN0)
相机(USB) → /camera/color/image_raw
```

---

## 硬件准备

### 1. CAN设备连接
- **CAN0**: 灵巧手
- **CAN1**: 外骨骼

**重要**: 确保只有一个CAN设备连接到每个CAN接口，否则会导致"No buffer space available"错误。

### 2. 启动CAN接口

```bash
# 启动CAN0（灵巧手）
sudo ip link set can0 up type can bitrate 1000000

# 启动CAN1（外骨骼）
sudo ip link set can1 up type can bitrate 1000000

# 验证状态
ip -details link show can0
ip -details link show can1
# 应该看到: state UP, can state ERROR-ACTIVE
```

### 3. USB设备
- 数据手套: /dev/ttyUSB0
- 相机: 自动识别

### 4. 网络
- 机械臂IP: 192.168.10.21
- 确保网络连接正常

---

## 启动顺序

### 终端1 - 相机

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_camera.sh
```

**预期输出**:
- 相机初始化成功
- 序列号: 348122071157
- 分辨率: 848x480
- 深度流: 禁用

**验证**:
```bash
# 在新终端
ros2 topic hz /camera/color/image_raw
# 预期: ~12-15 Hz
```

---

### 终端2 - 遥操臂（Linkerta外骨骼）

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
cd external_sdk/arm_teleop
source install/setup.bash
cd ~/Dev/VIST
source install/setup.bash
./scripts/start_left_arm_teleop.sh
```

**预期输出**:
- CAN channel: can1
- 关节数据持续输出

**验证**:
```bash
ros2 topic hz /left_arm_joint_control
# 预期: ~80 Hz
```

---

### 终端3 - 滤波器

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_filter.sh
```

**预期输出**:
- 输入topic: /left_arm_joint_control
- 输出topic: /filtered_joint_states
- 滤波类型: one_euro

**验证**:
```bash
ros2 topic hz /filtered_joint_states
# 预期: ~80 Hz
```

---

### 终端4 - 数据手套

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
bash scripts/start_5_data_glove.sh
```

**预期输出**:
- 找到USB设备: /dev/ttyUSB0
- 左手数据手套连接成功
- 标定数据加载成功

**验证**:
```bash
ros2 topic hz /cb_left_hand_control_cmd
# 预期: ~30 Hz
```

---

### 终端5 - 灵巧手

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_6_dexterous_hand.sh
```

**预期输出**:
- CAN端口: can0
- 手部: left
- 序列号正常识别（不是-1）

**验证**:
- 移动数据手套，观察灵巧手是否响应

---

### 终端6 - 机械臂驱动

```bash
cd ~/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch lbot_driver lbot_start_driver.launch.py
```

**预期输出**:
- Connected to LBot at 192.168.10.21
- State monitor started successfully
- 无连接错误

---

### 终端7 - 遥操桥接

```bash
cd ~/Dev/VIST
./scripts/start_teleop_bridge.sh
```

**预期输出**:
- 输入: /filtered_joint_states
- 输出: /robot1/left_arm/joint_follow
- 桥接节点启动成功

**验证**:
- 移动外骨骼，观察机械臂是否跟随运动

---

### 终端8 - 数据采集（可选）

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash

# 开始录制，指定实验名称
./scripts/record_experiment.sh stacking_task_trial1

# 按Ctrl+C停止录制
```

**录制的topic**:
- /camera/color/image_raw
- /camera/color/camera_info
- /left_arm_joint_control
- /filtered_joint_states
- /cb_left_hand_control_cmd
- /cb_left_hand_control_angle_cmd
- /robot1/left_arm/joint_states
- /robot1/left_arm/joint_follow

**数据保存位置**: `~/Dev/VIST/data/experiments/`

---

### 终端9 - 通信监控（可选）

用于监控系统状态和topic频率。

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash

# 查看所有topic
ros2 topic list

# 监控特定topic频率
ros2 topic hz /camera/color/image_raw
ros2 topic hz /left_arm_joint_control
ros2 topic hz /filtered_joint_states
ros2 topic hz /cb_left_hand_control_cmd

# 查看topic数据
ros2 topic echo /filtered_joint_states
```

---

## 完整系统验证

### 1. 检查所有节点

```bash
ros2 node list
```

应该看到:
- realsense_camera_node
- linkerta_node
- unified_filter_node
- handretarget_node
- linker_hand_advanced_l10
- lbot_driver相关节点
- teleop_bridge_node

### 2. 检查所有topic

```bash
ros2 topic list
```

关键topic:
- /camera/color/image_raw
- /left_arm_joint_control
- /filtered_joint_states
- /cb_left_hand_control_cmd
- /robot1/left_arm/joint_follow
- /robot1/left_arm/joint_states

### 3. 功能测试

1. **外骨骼 → 机械臂**: 移动外骨骼，观察机械臂是否跟随
2. **数据手套 → 灵巧手**: 移动数据手套，观察灵巧手是否响应
3. **相机**: 检查图像是否正常采集

### 4. 频率检查

| Topic | 预期频率 | 实际频率 |
|-------|---------|---------|
| /camera/color/image_raw | ~12-15 Hz | ___ Hz |
| /left_arm_joint_control | ~80 Hz | ___ Hz |
| /filtered_joint_states | ~80 Hz | ___ Hz |
| /cb_left_hand_control_cmd | ~30 Hz | ___ Hz |

---

## 关闭系统

按照相反顺序关闭各个节点（Ctrl+C）:

1. 终端9: 通信监控
2. 终端8: 数据采集
3. 终端7: 遥操桥接
4. 终端6: 机械臂驱动
5. 终端5: 灵巧手
6. 终端4: 数据手套
7. 终端3: 滤波器
8. 终端2: 遥操臂
9. 终端1: 相机

---

## 常见问题

### 1. CAN设备冲突

**症状**: "No buffer space available" 错误

**解决**:
- 确保只有一个CAN设备连接到每个CAN接口
- 重启电脑
- 重新启动CAN接口

### 2. Python环境问题

**症状**: `ModuleNotFoundError: No module named 'rclpy._rclpy_pybind11'`

**解决**:
```bash
conda deactivate  # 或使用 robot_env 环境
source /opt/ros/humble/setup.bash
source ~/Dev/VIST/install/setup.bash
```

### 3. 机械臂不响应

**症状**: 外骨骼移动但机械臂不跟随

**检查**:
1. 遥操桥接节点是否启动
2. 滤波器是否正常输出
3. 机械臂驱动是否连接成功
4. Topic映射是否正确

### 4. 关节方向反了

**解决**: 修改遥操桥接配置文件

```bash
# 编辑配置文件
nano ~/Dev/VIST/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml

# 修改negation参数
# 例如: 如果joint4方向反了
negation: [1, 1, 1, -1, 1, 1, 1, ...]

# 重新编译
cd ~/Dev/VIST/external_sdk/arm_teleop
colcon build --packages-select lbot_teleop
source install/setup.bash

# 重启遥操桥接节点
```

---

## 配置文件位置

- **相机**: `scripts/start_camera.sh`
- **外骨骼**: `external_sdk/arm_teleop/src/linkerta/config/lta.yaml`
- **滤波器**: `scripts/start_filter.sh`
- **遥操桥接**: `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`
- **灵巧手**: `external_sdk/linkerhand-ros2-sdk/.../config/setting.yaml`

---

## 快速启动检查清单

- [ ] CAN0和CAN1已启动
- [ ] 数据手套已连接（/dev/ttyUSB0）
- [ ] 相机已连接
- [ ] 机械臂网络连接正常（192.168.10.21）
- [ ] 所有终端已source ROS2环境
- [ ] 按顺序启动所有节点
- [ ] 验证所有topic频率
- [ ] 测试外骨骼→机械臂控制
- [ ] 测试数据手套→灵巧手控制
- [ ] 开始数据采集

---

## 联系与支持

如有问题，请参考:
- [MODULE_TEST_GUIDE.md](MODULE_TEST_GUIDE.md) - 模块测试记录
- [MONITORING_AND_RECORDING.md](MONITORING_AND_RECORDING.md) - 监控与数据采集详细指南

---

**祝实验顺利！**