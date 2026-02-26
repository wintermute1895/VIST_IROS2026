# VIST系统完整启动指南

## 系统架构

```
外骨骼(can1) → /left_arm_joint_control → 滤波器 → /filtered_joint_states → 遥操作桥接 → 机械臂
数据手套 → /cb_left_hand_control_cmd → 灵巧手(can0)
相机 → /camera/color/image_raw
```

## 硬件连接

- **CAN0**: 灵巧手
- **CAN1**: 外骨骼
- **USB**: 数据手套 (/dev/ttyUSB0)
- **USB**: 相机 (序列号: 348122071157)
- **网络**: 机械臂 (192.168.10.21)

## 启动顺序

### 终端1 - 相机
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/start_camera.sh
```

**验证**:
```bash
ros2 topic hz /camera/color/image_raw
# 预期: ~12-15 Hz (禁用深度流后)
```

---

### 终端2 - 外骨骼
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
cd external_sdk/arm_teleop
source install/setup.bash
cd ~/Dev/VIST
source install/setup.bash
./scripts/start_left_arm_teleop.sh
```

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

**验证**:
- 观察数据手套是否能控制灵巧手
- 检查CAN通信是否正常（无错误信息）

---

### 终端6 - 机械臂驱动
```bash
cd ~/Dev/VIST/external_sdk/arm_teleop
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch lbot_driver lbot_start_driver.launch.py
```

**验证**:
- 检查是否成功连接到 192.168.10.21
- 无连接错误

---

### 终端7 - 遥操作桥接
```bash
cd ~/Dev/VIST
./scripts/start_teleop_bridge.sh
```

**验证**:
- 移动外骨骼，观察机械臂是否跟随运动
- 检查topic连接: `/filtered_joint_states` → `/robot1/left_arm/joint_follow`

---

## 完整系统验证

### 1. 检查所有topic
```bash
ros2 topic list
```

应该看到:
- `/camera/color/image_raw`
- `/left_arm_joint_control`
- `/filtered_joint_states`
- `/cb_left_hand_control_cmd`
- `/robot1/left_arm/joint_follow`

### 2. 功能测试
1. **外骨骼 → 机械臂**: 移动外骨骼，观察机械臂是否跟随
2. **数据手套 → 灵巧手**: 移动数据手套，观察灵巧手是否响应
3. **相机**: 检查图像是否正常采集

### 3. 频率监控
```bash
# 在新终端中
ros2 topic hz /camera/color/image_raw
ros2 topic hz /left_arm_joint_control
ros2 topic hz /filtered_joint_states
ros2 topic hz /cb_left_hand_control_cmd
```

---

## 常见问题

### CAN设备冲突
**症状**: "No buffer space available" 错误

**解决**: 确保只连接一个CAN设备到每个CAN接口
- CAN0: 灵巧手
- CAN1: 外骨骼

### Python环境问题
**症状**: `ModuleNotFoundError: No module named 'rclpy._rclpy_pybind11'`

**解决**:
```bash
conda deactivate  # 或使用 robot_env 环境
source /opt/ros/humble/setup.bash
source ~/Dev/VIST/install/setup.bash
```

### 机械臂不动
**症状**: 外骨骼移动但机械臂不响应

**检查**:
1. 遥操作桥接节点是否启动
2. 滤波器是否正常输出
3. 机械臂驱动是否连接成功
4. Topic映射是否正确

---

## 关闭系统

按照相反顺序关闭各个节点（Ctrl+C）:
1. 遥操作桥接
2. 机械臂驱动
3. 灵巧手
4. 数据手套
5. 滤波器
6. 外骨骼
7. 相机

---

## 配置文件位置

- 相机: `scripts/start_camera.sh`
- 外骨骼: `external_sdk/arm_teleop/src/linkerta/config/lta.yaml`
- 滤波器: `scripts/start_filter.sh`
- 遥操作桥接: `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`
- 灵巧手: `external_sdk/linkerhand-ros2-sdk/linker_hand_ros2_sdk/linker_hand_ros2_sdk/LinkerHand/config/setting.yaml`

---

## 测试结果总结

| 模块 | 状态 | 频率 | 备注 |
|------|------|------|------|
| 相机 | ✅ | ~12-15 Hz | 禁用深度流 |
| 外骨骼 | ✅ | ~80 Hz | CAN1 |
| 滤波器 | ✅ | ~80 Hz | One-Euro |
| 数据手套 | ✅ | ~30 Hz | 左手 |
| 灵巧手 | ✅ | - | CAN0, 左手 |
| 机械臂 | ✅ | - | 192.168.10.21 |
| 遥操作桥接 | ✅ | - | 连接滤波器到机械臂 |

---

最后更新: 2026-02-26