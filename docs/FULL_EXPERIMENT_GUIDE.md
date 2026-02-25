# 完整实验启动指南

## 实验目标
插孔实验（Peg-in-Hole）- 使用左臂外骨骼+数据手套+灵巧手控制机械臂完成插孔任务

## 硬件准备
- [ ] 机械臂已连接并上电
- [ ] Linkerta左臂外骨骼已连接
- [ ] 数据手套（左手）已连接并开机
- [ ] 灵巧手（左手）CAN总线已连接
- [ ] RealSense相机已连接

## 启动顺序

### 步骤1: 机械臂使能
在机械臂控制台执行使能操作（具体步骤根据你的机械臂型号）

### 步骤2: 启动相机（终端1）
```bash
cd ~/Dev/VIST
bash scripts/start_camera.sh
```
等待相机初始化完成

### 步骤3: 启动左臂外骨骼（终端2）
```bash
cd ~/Dev/VIST
bash scripts/start_left_arm_teleop.sh
```
等待外骨骼连接成功

### 步骤4: 启动滤波器（终端3）
```bash
cd ~/Dev/VIST
bash scripts/start_filter.sh
```

### 步骤5: 启动数据手套（终端4）
```bash
cd ~/Dev/VIST
bash scripts/start_5_data_glove.sh
```
如果需要标定，使用：
```bash
bash scripts/start_5_data_glove.sh true
```

### 步骤6: 启动灵巧手（终端5）
```bash
cd ~/Dev/VIST
bash scripts/start_6_dexterous_hand.sh left
```

### 步骤7: 验证系统状态（终端6）
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
ros2 node list
```

应该看到以下节点：
- `/realsense_camera`
- `/linkerta_node` (或类似名称)
- `/filter_node`
- `/handretarget_node`
- `/linker_hand_advanced_l10`

### 步骤8: 开始数据采集（终端7）
```bash
cd ~/Dev/VIST
bash scripts/collect_full_experiment.sh 60 peg_in_hole_test1
```

参数说明：
- 第一个参数：采集时长（秒），默认60秒
- 第二个参数：实验名称，默认自动生成

## 数据采集的Topic

### 视觉数据
- `/camera/color/image_raw` - 彩色图像
- `/camera/depth/image_rect_raw` - 深度图像
- `/camera/color/camera_info` - 相机参数

### 遥操作数据
- `/left_arm_joint_control` - 原始外骨骼数据
- `/filtered_left_joint_control` - 滤波后的数据

### 手部数据
- `/cb_left_hand_control_cmd` - 手套控制命令
- `/cb_left_hand_state` - 灵巧手状态

### 机器人数据
- `/robot_joint_states` - 机械臂关节状态

### 性能数据
- `/filter_performance` - 滤波器性能指标

## 实验流程

1. **准备阶段（0-5秒）**
   - 确认所有设备响应正常
   - 调整姿态到初始位置

2. **执行阶段（5-55秒）**
   - 执行插孔任务
   - 保持平稳操作

3. **结束阶段（55-60秒）**
   - 返回初始位置
   - 准备停止

## 数据保存位置

数据保存在：`data/experiments/<实验名称>/`

包含：
- rosbag数据文件
- metadata.yaml（实验元数据）

## 故障排查

### 问题1: 外骨骼未连接
检查USB连接，确认设备在 `/dev/ttyUSB*`

### 问题2: 灵巧手不动
- 检查CAN总线状态：`ip link show can0`
- 检查topic连接：`ros2 topic hz /cb_left_hand_control_cmd`

### 问题3: 相机无图像
重启相机节点，检查USB3.0连接

### 问题4: 机械臂不响应
确认机械臂已使能，检查 `/robot_joint_states` topic

## 注意事项

1. **安全第一**：确保机械臂工作空间内无障碍物
2. **急停准备**：随时准备按下急停按钮
3. **数据备份**：实验后及时备份数据
4. **标定检查**：每次实验前检查手套标定是否正常