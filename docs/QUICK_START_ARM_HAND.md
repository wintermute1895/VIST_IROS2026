# 快速启动指南：手臂+手部控制

本指南说明如何启动完整的遥操作系统，包括外骨骼手臂控制和灵巧手控制。

## 系统架构

```
外骨骼 → 滤波器 → 遥操作桥接 → 机械臂驱动 → 机械臂硬件
数据手套 → 手部映射 → 灵巧手驱动 → 灵巧手硬件
```

## 启动步骤

### 1. 启动外骨骼 (Terminal 1)
```bash
./scripts/start_1_exoskeleton.sh
```

### 2. 启动滤波器 (Terminal 2)
```bash
# 选择滤波器类型: none, ema, one_euro, vist_kalman
./scripts/start_2_filter.sh one_euro
```

### 3. 启动机械臂驱动 (Terminal 3)
```bash
./scripts/start_3_robot_driver.sh
```

### 4. 启动遥操作桥接 (Terminal 4)
```bash
./scripts/start_4_teleop_bridge.sh
```

### 5. 启动数据手套 (Terminal 5)
```bash
# 正常模式
./scripts/start_5_data_glove.sh

# 强制标定模式
./scripts/start_5_data_glove.sh true
```

### 6. 启动灵巧手驱动 (Terminal 6)
```bash
# 默认参数: right hand, can0, 不启用触觉
./scripts/start_6_dexterous_hand.sh

# 自定义参数: <hand_type> <can_port> <enable_touch>
./scripts/start_6_dexterous_hand.sh right can0 false
```

## 数据采集

数据采集脚本默认采集所有数据（手臂、相机、手部控制），采集后可以根据需要筛选和训练模型。

### 基本用法
```bash
# 采集所有数据（手臂+相机+手部）
./scripts/collect_right_arm_data.sh <实验名称> <时长秒数>

# 示例：采集30秒数据
./scripts/collect_right_arm_data.sh exp_baseline 30
./scripts/collect_right_arm_data.sh exp_with_filter 30
```

### 采集的话题
脚本会自动检测并录制以下话题（如果可用）：

**手臂控制话题：**
- `/right_arm_joint_control` - 外骨骼原始数据（7个关节角度）
- `/filtered_right_joint_control` - 滤波后的关节控制命令
- `/right_arm/joint_follow` - 发送给机械臂的控制命令
- `/right_arm/joint_states` - 机械臂状态反馈（当前关节角度、速度、力矩等）

**相机话题（尾号7相机 - 348122071157）：**
- `/camera/color/image_raw` - RGB 图像（用于意图因子计算）
- `/camera/depth/image_raw` - 深度图像（用于3D空间理解）
- `/camera/color/camera_info` - 相机标定信息（内参、畸变参数等）

**手部控制话题：**
- `/cb_right_hand_control_cmd` - 手部控制命令（数据手套 → 灵巧手，10个关节角度）
- `/cb_right_hand_state` - 灵巧手状态反馈（当前关节角度、力矩、触觉传感器等）

**说明：**
- 如果某个话题不存在（例如未启动相机或手部控制），脚本会显示警告但继续采集其他话题
- 采集的数据保存为 ROS2 bag 格式（SQLite3 + 元数据），可以使用 `ros2 bag play` 回放
- 建议采集完整数据后再根据需要筛选，避免遗漏重要信息
- 滤波器性能指标（延迟、抖动等）通过离线分析计算，不在采集时记录

## 配置文件

系统配置位于 `config/system_config.yaml`，包含以下部分：

- `startup.data_glove` - 数据手套配置
- `startup.dexterous_hand` - 灵巧手配置
- `startup.exoskeleton` - 外骨骼配置
- `startup.filter` - 滤波器配置
- `startup.robot_driver` - 机械臂驱动配置
- `startup.teleop_bridge` - 遥操作桥接配置

**注意：** 配置文件中的 `enabled` 字段默认为 `false`，表示不自动启动。用户需要手动启动相应的节点。数据采集脚本会自动尝试采集所有话题，如果话题不存在就跳过。

## 术语解释

### 数据手套标定（Calibration）
数据手套在首次使用或更换使用者时需要标定，用于：
- 校准传感器零点（手指伸直时的基准值）
- 适应不同手部尺寸
- 补偿传感器漂移

启动时可以选择是否强制标定：
```bash
# 正常模式（使用上次标定结果）
./scripts/start_5_data_glove.sh

# 强制标定模式（重新标定）
./scripts/start_5_data_glove.sh true
```

### 相机配置说明
系统有两个 D435i 相机：
- **尾号7相机（348122071157）**：机器人头顶相机，用于数据采集和意图因子计算（α_geo, α_vel, α_dir）
- **尾号0相机（327122074150）**：备用相机，可用于手部姿态估计（暂不使用）

当前数据采集使用尾号7相机，采集 RGB 图像、深度图像和相机标定信息。

### 机械臂状态反馈（Joint States）
话题 `/right_arm/joint_states` 包含机械臂的实时状态：
- `position` - 当前关节角度（弧度）
- `velocity` - 当前关节速度（弧度/秒）
- `effort` - 当前关节力矩（牛·米）

用于：
- 闭环控制（比较期望值和实际值）
- 安全监控（检测异常力矩）
- 性能分析（跟踪误差、响应时间）

### 滤波器性能分析
滤波器性能指标（延迟、抖动、平滑度等）通过离线分析计算，不在数据采集时实时记录。分析方法：
- 比较原始数据和滤波后数据的时间戳差异（延迟）
- 计算输出信号的标准差（抖动）
- 评估轨迹平滑度（加速度变化率）

用于消融实验，比较不同滤波器（none, EMA, One Euro, VIST Kalman）的效果。

## 故障排查

### 数据手套无法连接
```bash
# 检查 USB 设备
ls /dev/ttyUSB*

# 设置权限
sudo chmod 777 /dev/ttyUSB0
```

### CAN 端口未激活
```bash
# 手动激活 CAN 端口
sudo ip link set can0 up type can bitrate 1000000

# 检查状态
ip -details link show can0
```

### 话题未发布
```bash
# 检查所有话题
ros2 topic list

# 检查特定话题
ros2 topic echo /cb_right_hand_control_cmd
```

## 注意事项

1. 启动顺序很重要，请按照上述顺序依次启动各个节点
2. 数据手套需要 USB 设备权限，脚本会自动设置
3. 灵巧手需要 CAN 端口激活，脚本会自动检查并激活
4. 如果遇到话题碰撞，请检查是否有重复的节点在运行
5. 数据采集时，确保所有相关节点都已正常启动