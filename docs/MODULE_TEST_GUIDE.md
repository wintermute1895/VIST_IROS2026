# 模块测试指南

在进行完整数据采集实验前，需要逐个测试各个模块的功能。

## 测试环境

- 任务：基础堆叠（stacking）
- 配置：数据手套 + 遥操臂 + 相机 + One-Euro滤波

## 测试流程

### 测试1: 相机模块

**目标**：确认相机能正常启动并发布图像

**步骤**：
```bash
# 终端1: 启动相机
cd ~/Dev/VIST
bash scripts/start_camera.sh
```

**验证**：
```bash
# 终端2: 检查相机节点
source /opt/ros/humble/setup.bash
ros2 node list | grep realsense

# 检查相机话题
ros2 topic list | grep camera

# 查看图像发布频率
ros2 topic hz /camera/color/image_raw

# 查看一帧图像（可选）
ros2 run rqt_image_view rqt_image_view
```

**预期结果**：
- 节点 `/realsense_camera` 存在
- 话题 `/camera/color/image_raw` 存在
- 图像发布频率约30Hz
- 能在rqt_image_view中看到图像

**通过标准**：✅ / ❌

---

### 测试2: 外骨骼模块

**目标**：确认外骨骼能正常连接并发布关节数据

**步骤**：
```bash
# 终端1: 启动外骨骼
cd ~/Dev/VIST
bash scripts/start_left_arm_teleop.sh
```

**验证**：
```bash
# 终端2: 检查外骨骼节点
source /opt/ros/humble/setup.bash
ros2 node list | grep linkerta

# 检查关节状态话题
ros2 topic list | grep joint

# 查看关节数据发布频率
ros2 topic hz /exo_joint_states

# 查看关节数据内容
ros2 topic echo /exo_joint_states --once
```

**预期结果**：
- 节点 `/linkerta_node` 存在
- 话题 `/exo_joint_states` 存在
- 数据发布频率约80Hz
- 能看到7个关节的角度数据

**通过标准**：✅ / ❌

---

### 测试3: 滤波器模块

**目标**：确认滤波器能正常接收外骨骼数据并输出滤波后的数据

**前提**：测试1和测试2已通过

**步骤**：
```bash
# 终端1: 保持相机运行
# 终端2: 保持外骨骼运行

# 终端3: 启动滤波器
cd ~/Dev/VIST
bash scripts/start_filter.sh
```

**验证**：
```bash
# 终端4: 检查滤波器节点
source /opt/ros/humble/setup.bash
ros2 node list | grep filter

# 检查滤波后的话题
ros2 topic list | grep filtered

# 查看滤波数据发布频率
ros2 topic hz /filtered_joint_states

# 对比原始和滤波后的数据
ros2 topic echo /exo_joint_states --once
ros2 topic echo /filtered_joint_states --once
```

**预期结果**：
- 节点 `/filter_node` 存在
- 话题 `/filtered_joint_states` 存在
- 数据发布频率与输入一致
- 滤波后的数据更平滑

**通过标准**：✅ / ❌

---

### 测试4: 数据手套模块

**目标**：确认数据手套能正常连接并发布手部数据

**步骤**：
```bash
# 终端1: 启动数据手套
cd ~/Dev/VIST
bash scripts/start_5_data_glove.sh
```

**验证**：
```bash
# 终端2: 检查数据手套节点
source /opt/ros/humble/setup.bash
ros2 node list | grep handretarget

# 检查手部数据话题
ros2 topic list | grep hand

# 查看手部数据发布频率
ros2 topic hz /cb_left_hand_control_cmd

# 查看手部数据内容
ros2 topic echo /hand_joint_states --once
```

**预期结果**：
- 节点 `/handretarget_node` 存在
- 话题 `/hand_joint_states` 存在
- 能看到手指关节数据
- 移动手指时数据有变化

**通过标准**：✅ / ❌

---

### 测试5: 灵巧手模块

**目标**：确认灵巧手能正常接收指令并执行

**前提**：测试4已通过

**步骤**：
```bash
# 终端1: 保持数据手套运行

# 终端2: 启动灵巧手
cd ~/Dev/VIST
bash scripts/start_6_dexterous_hand.sh left
```

**验证**：
```bash
# 终端3: 检查灵巧手节点
source /opt/ros/humble/setup.bash
ros2 node list | grep linker_hand

# 观察灵巧手是否跟随数据手套运动
# 移动数据手套，观察灵巧手响应
```

**预期结果**：
- 节点 `/linker_hand_advanced_l10` 存在
- 灵巧手能跟随数据手套运动
- 响应延迟小于100ms
- 无异常抖动或卡顿

**通过标准**：✅ / ❌

---

### 测试6: 完整系统集成

**目标**：确认所有模块能协同工作

**步骤**：
按顺序启动所有模块：
1. 相机（终端1）
2. 外骨骼（终端2）
3. 滤波器（终端3）
4. 数据手套（终端4）
5. 灵巧手（终端5）

**验证**：
```bash
# 终端6: 检查所有节点
source /opt/ros/humble/setup.bash
ros2 node list

# 检查所有话题
ros2 topic list

# 检查话题连接关系
ros2 node info /filter_node
ros2 node info /handretarget_node
```

**预期结果**：
- 所有节点都在运行
- 所有话题都在发布
- 移动外骨骼，机械臂应该跟随（如果已使能）
- 移动数据手套，灵巧手应该跟随
- 系统稳定运行，无崩溃或错误

**通过标准**：✅ / ❌

---

## 常见问题排查

### 问题1: 相机无法启动
- 检查USB连接
- 检查相机权限：`ls -l /dev/video*`
- 重新插拔相机

### 问题2: 外骨骼无法连接
- 检查串口连接
- 检查串口权限：`sudo chmod 666 /dev/ttyUSB*`
- 检查外骨骼电源

### 问题3: 滤波器无输出
- 确认外骨骼数据正常发布
- 检查话题名称是否匹配
- 查看滤波器日志

### 问题4: 数据手套无数据
- 检查USB连接
- 检查标定是否完成
- 重新标定：`bash scripts/start_5_data_glove.sh true`

### 问题5: 灵巧手不响应
- 检查CAN总线连接
- 检查CAN端口：`ip link show can0`
- 重启CAN端口：`sudo ip link set can0 down && sudo ip link set can0 up`

---

## 测试记录

| 测试项 | 日期 | 结果 | 备注 |
|--------|------|------|------|
| 测试1: 相机 | 2026-02-26 | ✅ 通过 | 20Hz，可接受 |
| 测试2: 外骨骼 | 2026-02-26 | ✅ 通过 | 80Hz，稳定 |
| 测试3: 滤波器 | 2026-02-26 | ✅ 通过 | 80Hz，One-Euro滤波 |
| 测试4: 数据手套 | 2026-02-26 | ✅ 通过 | 左手已连接，标定正常 |
| 测试5: 灵巧手 | 2026-02-26 | ✅ 通过 | CAN连接成功，数据流正常 |
| 测试6: 完整集成 | | | |

**注意**：
- 外骨骼话题名称是 `/left_arm_joint_control`，不是 `/exo_joint_states`
- 滤波器使用 `unified_filter_node.py`，不是 `one_euro_filter` 包
- 数据手套话题是 `/cb_left_hand_control_cmd` 等，不是 `/hand_joint_states`
- 灵巧手节点名称是 `/linker_hand_advanced_l10`，订阅 `/cb_left_hand_control_cmd`

---

## 下一步

所有测试通过后，可以开始正式的数据采集实验：

```bash
# 终端7: 开始数据采集
cd ~/Dev/VIST
bash scripts/collect_full_experiment.sh 60 stacking_test1
```