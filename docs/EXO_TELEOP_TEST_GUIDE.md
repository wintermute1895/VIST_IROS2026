# 外骨骼遥操测试指南

## 系统架构

```
外骨骼遥操臂 (Linkerta)
    ↓ ~250Hz
/right_arm_joint_control (原始关节角度)
    ↓
teleop_bridge_node (单位转换、限位检查)
    ↓ ~250Hz
/robot1/right_arm/joint_follow (跟随命令)
    ↓
lbot_driver (机器人驱动)
    ↓ 底层自动降频到 ~50Hz
真机执行
    ↓ ~50Hz
/robot1/right_arm/joint_states (反馈)
```

## 相机设备

你的电脑连接了3个相机：

1. **HP 5MP Camera** (笔记本内置) - /dev/video0-3
2. **RealSense D435I #1**
   - 序列号: `348122071157`
   - 设备: /dev/video10-15
3. **RealSense D435I #2**
   - 序列号: `327122074150`
   - 设备: /dev/video4-9

## 快速开始

### 1. 准备工作

确保以下设备已连接：
- 外骨骼遥操臂（Linkerta）已连接并上电
- 机器人左臂已连接（IP: 192.168.10.21）
- RealSense相机已连接

### 2. 启动外骨骼遥操系统

**终端1** - 启动外骨骼遥操：
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop.launch.py
```

这个launch文件会启动：
- `lbot_driver`: 机器人驱动（连接真机）
- `linkerta`: 外骨骼遥操臂驱动
- `teleop_bridge_node`: 桥接节点（单位转换、限位检查）

### 3. 运行数据采集测试

**终端2** - 运行测试脚本：
```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash  # 或你的ROS2版本

# 基础测试（30秒，使用默认相机）
./scripts/test_exo_teleop_pipeline.sh

# 自定义时长和任务名
./scripts/test_exo_teleop_pipeline.sh 60 "pick_and_place"

# 指定相机序列号
./scripts/test_exo_teleop_pipeline.sh 30 "test" "327122074150"
```

### 4. 查看结果

测试完成后，数据保存在 `data/collection/<task_name>_<timestamp>/`

```bash
# 查看频率报告
cat data/collection/exo_teleop_test_*/frequency_report.json

# 查看时间同步报告
cat data/collection/exo_teleop_test_*/sync_report.json

# 查看元数据
cat data/collection/exo_teleop_test_*/metadata.json
```

## 手动步骤（如果自动脚本有问题）

### 1. 启动外骨骼遥操
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop.launch.py
```

### 2. 验证topics
```bash
# 检查外骨骼原始输出
ros2 topic hz /right_arm_joint_control

# 检查跟随命令
ros2 topic hz /robot1/right_arm/joint_follow

# 检查真机反馈
ros2 topic hz /robot1/right_arm/joint_states
```

### 3. 启动相机
```bash
# 使用第一个D435I
ros2 launch realsense2_camera rs_launch.py \
    serial_no:=348122071157 \
    depth_module.profile:=640x480x30 \
    rgb_camera.profile:=640x480x30 \
    enable_gyro:=false \
    enable_accel:=false
```

### 4. 录制数据
```bash
# 创建目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EPISODE_DIR="data/collection/exo_test_${TIMESTAMP}"
mkdir -p "$EPISODE_DIR"

# 录制30秒
ros2 bag record \
    -o "$EPISODE_DIR/rosbag" \
    /right_arm_joint_control \
    /robot1/right_arm/joint_follow \
    /robot1/right_arm/joint_states \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    --max-bag-duration 30
```

### 5. 分析数据
```bash
# 验证时间同步
python3 scripts/validate_time_sync.py \
    "$EPISODE_DIR/rosbag" \
    --topic1 /right_arm_joint_control \
    --topic2 /robot1/right_arm/joint_follow

# 分析episode
python3 scripts/analyze_episode.py "$EPISODE_DIR"
```

## 配置说明

### 外骨骼遥操配置
配置文件: `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_config.yaml`

关键参数：
- `slave_arm_ips`: 机器人IP列表（当前: 192.168.10.21）
- `follow_mode`: 跟随模式（true）
- `scale_factor`: 缩放比例（1.0 = 1:1映射）
- `negation`: 关节方向映射（14个值，左臂7个+右臂7个）

### 录制配置
配置文件: `config/recording_config.yaml`

当前配置：
- 录制外骨骼原始输出 (`/right_arm_joint_control`)
- 录制处理后的跟随命令 (`/robot1/right_arm/joint_follow`)
- 录制真机反馈 (`/robot1/right_arm/joint_states`)

## 性能指标分析

采集数据后，可以分析以下指标：

### 1. 频率分析
- 外骨骼输出频率（期望 ~250Hz）
- 跟随命令频率（期望 ~250Hz）
- 真机反馈频率（期望 ~50Hz）
- 相机频率（期望 ~30Hz）

### 2. 时间同步质量
- 外骨骼输出 vs 跟随命令的时间差
- 评级标准：
  - A级: <10ms
  - B级: 10-33ms
  - C级: 33-100ms
  - D级: 100-200ms
  - F级: >200ms

### 3. 延迟分析
- 外骨骼→跟随命令延迟
- 跟随命令→真机执行延迟
- 端到端延迟

### 4. 轨迹质量
- 关节角度平滑度
- 速度/加速度连续性
- 是否有异常跳变

## 常见问题

### Q1: 找不到相机
```bash
# 列出所有RealSense相机
rs-enumerate-devices

# 检查USB连接
lsusb | grep Intel
```

### Q2: 无法连接机器人
```bash
# 检查网络连接
ping 192.168.10.21

# 检查机器人是否上电
# 检查IP配置是否正确
```

### Q3: Topic频率不对
```bash
# 实时监控频率
ros2 topic hz /right_arm_joint_control

# 检查CPU负载
htop

# 检查ROS2 DDS配置
echo $RMW_IMPLEMENTATION
```

### Q4: 录制的bag文件太大
- 降低相机分辨率（640x480 → 424x240）
- 降低相机帧率（30Hz → 15Hz）
- 只录制必要的topics
- 使用压缩格式

## 下一步

1. **基础测试**: 先运行30秒测试，验证链路是否打通
2. **性能测试**: 录制更长时间（60-120秒），分析性能指标
3. **任务测试**: 执行具体任务（抓取、放置等），评估任务完成质量
4. **对比测试**: 对比不同配置（有/无滤波、不同缩放比例等）

## 注意事项

⚠️ **安全提醒**：
- 确保机器人工作空间内无障碍物
- 首次测试时使用较小的 `scale_factor`（如0.5）
- 随时准备按下急停按钮
- 外骨骼和机器人的关节方向映射可能需要调整

⚠️ **已知问题**（来自系统分析）：
- 关节限位配置可能不正确（需要验证）
- 缺少硬件急停集成
- 无工作空间边界检查
- 建议先在安全环境下小范围测试