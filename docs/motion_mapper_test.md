# 运动映射测试指南

## 概述

本指南说明如何测试 VIST 项目的三向量运动映射（Three-Vector Motion Mapping）功能。

## 系统架构

```
[测试脚本] --UDP--> [ArmNode] --映射--> [目标位姿] --可视化--> [MeshCat]
   (模拟人体关键点)      (运动映射器)      (位置+姿态)        (3D显示)
```

## 测试步骤

### 1. 启动 ArmNode（接收端）

在终端 1 中运行：

```bash
cd /home/ilex/Dev/VIST
python -m src.nodes.arm_node
```

这将启动：
- ✅ MockArmDriver（模拟机械臂驱动）
- ✅ ArmMotionMapper（运动映射器）
- ✅ UDP 接收器（端口 6001）
- ✅ MeshCat 可视化（自动打开浏览器）

### 2. 发送测试数据（发送端）

在终端 2 中运行：

```bash
cd /home/ilex/Dev/VIST
python scripts/test_motion_mapper.py
```

这将以 30 Hz 的频率发送模拟的人体关键点数据。

### 3. 观察可视化

在 MeshCat 浏览器窗口中，你应该能看到：
- 🤖 机器人模型（灰色）
- 🎯 目标坐标系（红/绿/蓝坐标轴）
  - 红色 = X 轴
  - 绿色 = Y 轴
  - 蓝色 = Z 轴

目标坐标系会随着模拟的人体运动而移动和旋转。

## 数据格式

UDP 数据包格式（JSON）：

```json
{
  "shoulder": [x, y, z],
  "elbow": [x, y, z],
  "wrist": [x, y, z],
  "palm": [x, y, z]
}
```

所有坐标单位为米（m）。

## 参数配置

### ArmMotionMapper 参数

在 `src/nodes/arm_node.py` 中可以调整：

```python
self.mapper = ArmMotionMapper(
    robot_shoulder_pos=[0.0, 0.0, 0.0],  # 机器人肩部位置
    arm_lengths={'upper': 0.30, 'fore': 0.25}  # 臂长（米）
)
self.mapper.set_filter_alpha(0.5)  # 平滑因子 [0, 1]
```

### 滤波器参数

- `filter_alpha = 0.0`: 最大平滑（输出几乎不变）
- `filter_alpha = 0.5`: 中等平滑（推荐）
- `filter_alpha = 1.0`: 无滤波（直接输出）

## 故障排除

### 问题：MeshCat 无法启动

**解决方案**：
```bash
pip install meshcat pinocchio
```

### 问题：看不到目标坐标系

**可能原因**：
1. 没有收到 UDP 数据 → 检查 `test_motion_mapper.py` 是否在运行
2. 映射失败 → 检查终端输出的错误信息
3. 坐标系在视野外 → 在 MeshCat 中调整相机视角

### 问题：UDP 端口被占用

**解决方案**：
修改 `arm_node.py` 中的端口号：
```python
node = ArmNode(visualize=True, dof=7, udp_port=6002)  # 改为其他端口
```

同时修改 `test_motion_mapper.py` 中的目标端口。

## 下一步

- [ ] 集成真实的 MediaPipe 人体姿态估计
- [ ] 添加逆运动学求解器（IK）
- [ ] 集成虚拟夹具（Virtual Fixture）
- [ ] 添加意图推理（Intent Inference）
- [ ] 连接真实机械臂硬件

## 相关文件

- `src/core/motion_mapper.py` - 三向量映射算法实现
- `src/nodes/arm_node.py` - 手臂控制节点
- `scripts/test_motion_mapper.py` - 测试数据发送脚本
- `src/robot/viz_server.py` - MeshCat 可视化服务器
