# VIST系统健康监控工具使用指南

## 🎯 功能概述

这是一个专业的ROS2频率监控工具，提供实时、面板化的系统健康状态显示。

### 核心特性

- ✅ **面板化显示**：类似 `top` 命令，每2秒刷新一次，不会疯狂刷屏
- ✅ **异常报警**：自动标记无数据话题和频率异常话题
- ✅ **资源优化**：对图像话题只计算频率，不反序列化内容，避免系统卡顿
- ✅ **彩色输出**：正常（绿色）、异常（黄色）、无数据（红色）
- ✅ **实时统计**：显示活跃话题数、正常话题数等统计信息

## 📋 监控的话题

| 话题名称 | 类型 | 说明 | 预期频率 |
|---------|------|------|---------|
| `/right_arm_joint_control` | JointState | 遥操源指令 | 70-90 Hz |
| `/robot1/right_arm/joint_follow` | FollowJoint | VIST下发指令 | 70-90 Hz |
| `/robot1/right_arm/joint_states` | JointState | 机械臂状态反馈 | 40-60 Hz |
| `/cb_right_hand_control_cmd` | String | 灵巧手控制 | 10-100 Hz |
| `/cb_right_hand_state` | String | 灵巧手状态 | 10-100 Hz |
| `/camera_top/camera/color/image_raw` | Image | 顶部相机RGB | 25-35 Hz |

## 🚀 使用方法

### 1. 依赖检查

确保已安装以下依赖：

```bash
# ROS2 Humble（或其他版本）
source /opt/ros/humble/setup.bash

# VIST工作空间
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

# Python依赖（通常已安装）
# - rclpy (ROS2 Python客户端库)
# - sensor_msgs
# - lbot_arm_interfaces
```

### 2. 运行监控工具

```bash
cd /home/ilex/Dev/VIST
python3 scripts/monitor_system_health.py
```

或者直接执行：

```bash
./scripts/monitor_system_health.py
```

### 3. 输出示例

```
====================================================================================================
VIST系统健康监控 - 2026-02-25 11:15:30 - 运行时长: 1分23秒
====================================================================================================

状态  话题名称                                      显示名称              实时频率      预期范围
----------------------------------------------------------------------------------------------------
✅   /right_arm_joint_control                     遥操源指令            81.5 Hz       70-90 Hz
✅   /robot1/right_arm/joint_follow               VIST下发指令          81.3 Hz       70-90 Hz
✅   /robot1/right_arm/joint_states               机械臂状态反馈        50.2 Hz       40-60 Hz
❌   /cb_right_hand_control_cmd                   灵巧手控制            0.0 Hz [WARNING: NO DATA]  10-100 Hz
❌   /cb_right_hand_state                         灵巧手状态            0.0 Hz [WARNING: NO DATA]  10-100 Hz
✅   /camera_top/camera/color/image_raw           顶部相机RGB           30.1 Hz       25-35 Hz
----------------------------------------------------------------------------------------------------

📊 统计: 总话题数 6 | 活跃话题 4 | 正常话题 4

图例: ✅ 正常 | ⚠️ 频率异常 | ❌ 无数据

按 Ctrl+C 停止监控
====================================================================================================
```

## 🔍 状态说明

### 状态符号

- **✅ 正常**：话题频率在预期范围内
- **⚠️ 频率异常**：话题有数据，但频率超出预期范围
- **❌ 无数据**：话题在过去2秒内没有收到任何消息

### 颜色编码

- **绿色**：频率正常
- **黄色**：频率异常（过高或过低）
- **红色**：无数据（带 `[WARNING: NO DATA]` 标记）

## 🛠️ 自定义配置

如果需要监控其他话题，编辑脚本中的 `self.topics` 字典：

```python
self.topics = {
    # 话题名称: (消息类型, 显示名称, 预期频率范围)
    '/your_topic': (YourMsgType, '显示名称', (最小频率, 最大频率)),
}
```

## 📊 性能优化

### 图像话题优化

对于图像话题（如 `/camera_top/camera/color/image_raw`），工具只计算消息头的接收频率，**不会反序列化图像数据**，因此不会产生额外的CPU和内存开销。

### 资源占用

- **CPU占用**：< 1%（仅计算时间戳）
- **内存占用**：< 10 MB（每个话题保存最近100个时间戳）
- **网络带宽**：极小（只接收消息头）

## 🔧 故障排查

### 问题1：提示"未检测到ROS2环境"

**解决方案**：
```bash
source /opt/ros/humble/setup.bash
source /home/ilex/Dev/VIST/external_sdk/arm_teleop/install/setup.bash
```

### 问题2：提示"No module named 'lbot_arm_interfaces'"

**解决方案**：
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
```

### 问题3：所有话题显示"无数据"

**可能原因**：
1. 系统节点未启动
2. 话题名称不匹配
3. ROS2域ID不匹配

**检查方法**：
```bash
# 查看当前活跃的话题
ros2 topic list

# 查看特定话题的信息
ros2 topic info /right_arm_joint_control
```

## 💡 使用场景

### 场景1：日常开发调试

在开发过程中，持续监控系统健康状态，及时发现频率异常。

```bash
# 终端1：启动系统
ros2 launch lbot_teleop teleop.launch.py

# 终端2：启动监控
./scripts/monitor_system_health.py
```

### 场景2：性能测试

在性能测试时，监控各个话题的频率是否稳定。

### 场景3：故障诊断

当系统出现问题时，快速定位哪个环节的数据流出现异常。

## 🔗 相关工具

- [diagnose_control_flow.sh](diagnose_control_flow.sh) - 完整控制流程诊断
- [check_topic_collision.sh](check_topic_collision.sh) - 话题冲突检测
- [SAFE_DIAGNOSIS_GUIDE.md](../SAFE_DIAGNOSIS_GUIDE.md) - 安全诊断指南

---

**创建时间**: 2026-02-25
**作者**: VIST项目组