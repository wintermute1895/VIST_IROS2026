# VIST 系统简化启动指南
# Simplified Startup Guide for VIST System

## 概述

本指南提供了简化的、鲁棒的启动流程，所有参数都已配置化，无需手动输入复杂参数。

## 启动前检查

在启动系统之前，**必须**运行配置验证脚本：

```bash
cd /home/ilex/Dev/VIST
./scripts/validate_startup_config.sh
```

该脚本会检查：
- ROS2 环境
- 工作空间完整性
- 配置文件存在性
- 机械臂连接状态
- 话题碰撞
- 已运行的节点

**只有所有检查通过后才能启动系统！**

## 启动流程

### Terminal 1: 外骨骼驱动

```bash
cd /home/ilex/Dev/VIST
./scripts/start_1_exoskeleton.sh
```

**功能**: 启动外骨骼驱动，只发布右臂数据

**输出话题**:
- `/right_arm_joint_control` (sensor_msgs/JointState)

---

### Terminal 2: 滤波节点

```bash
cd /home/ilex/Dev/VIST
./scripts/start_2_filter.sh [filter_type] [params...]
```

**参数**:
- `filter_type`: 滤波器类型（可选，默认 `one_euro`）
  - `none`: 无滤波（直通）
  - `ema [alpha]`: EMA 滤波，例如 `ema 0.3`
  - `one_euro [min_cutoff] [beta]`: One-Euro 滤波，例如 `one_euro 1.0 0.007`
  - `vist_kalman`: VIST Kalman 滤波

**示例**:
```bash
# 使用默认 One-Euro 滤波
./scripts/start_2_filter.sh

# 使用无滤波
./scripts/start_2_filter.sh none

# 使用 EMA 滤波，alpha=0.3
./scripts/start_2_filter.sh ema 0.3

# 使用 One-Euro 滤波，自定义参数
./scripts/start_2_filter.sh one_euro 1.0 0.007
```

**输入话题**: `/right_arm_joint_control`  
**输出话题**: `/filtered_right_joint_control`

---

### Terminal 3: 机械臂驱动

```bash
cd /home/ilex/Dev/VIST
./scripts/start_3_robot_driver.sh
```

**功能**: 启动机械臂驱动，连接到机械臂控制器

**订阅话题**: `/right_arm/joint_follow`  
**发布话题**: `/right_arm/joint_states`

**重要**: 启动后，需要在 web 控制器手动使能机械臂！

---

### Terminal 4: 遥操作桥接

```bash
cd /home/ilex/Dev/VIST
./scripts/start_4_teleop_bridge.sh
```

**功能**: 启动遥操作桥接，连接滤波节点和机械臂驱动

**输入话题**: `/filtered_right_joint_control`  
**输出话题**: `/right_arm/joint_follow`

**重要**: 该脚本自动处理话题和服务重映射，无需手动配置！

---

## 数据采集

系统启动并运行后，可以使用数据采集脚本：

```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh <实验名称> <时长秒数>
```

**示例**:
```bash
# 采集 30 秒的 One-Euro 滤波数据
./scripts/collect_right_arm_data.sh exp1_one_euro 30

# 采集 30 秒的无滤波数据
./scripts/collect_right_arm_data.sh exp0_no_filter 30
```

## 停止系统

在每个终端按 `Ctrl+C` 停止对应的节点。

建议停止顺序（从后往前）：
1. Terminal 4: teleop_bridge
2. Terminal 3: robot_driver
3. Terminal 2: filter
4. Terminal 1: exoskeleton

## 故障排除

### 问题: 机械臂不响应外骨骼运动

**检查清单**:
1. 所有 4 个终端的节点都在运行吗？
2. 机械臂在 web 控制器上使能了吗？
3. 运行 `ros2 topic hz /filtered_right_joint_control` 检查数据流
4. 运行 `ros2 topic info /right_arm/joint_follow` 检查发布者和订阅者数量

### 问题: 话题碰撞

**解决方案**:
1. 停止所有节点
2. 运行 `ros2 node list` 确认没有残留节点
3. 重新按顺序启动

### 问题: 数据采集无法停止

**解决方案**:
1. 按 `Ctrl+C` 停止
2. 如果无法停止，运行 `ps aux | grep "ros2 bag"` 找到进程 ID
3. 运行 `kill -9 <PID>` 强制停止

## 配置文件

所有系统参数都在以下配置文件中：

- **系统配置**: `/home/ilex/Dev/VIST/config/system_config.yaml`
- **teleop_bridge 配置**: `/home/ilex/Dev/VIST/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`
- **lbot_driver 配置**: `/home/ilex/Dev/VIST/external_sdk/arm_teleop/src/lbot_driver/config/lbot_config.yaml`

修改配置后无需重新编译，直接重启对应节点即可。

## 安全注意事项

1. **启动前必须运行验证脚本** - 确保系统配置正确
2. **机械臂使能前确认工作空间安全** - 无障碍物，急停按钮在手边
3. **首次测试保持低速运动** - 观察机械臂响应是否正常
4. **发现异常立即按急停** - 不要犹豫

---

更新日期: 2026-02-25  
版本: 2.0 (简化配置化版本)
