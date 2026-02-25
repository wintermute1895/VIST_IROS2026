# 话题冲突分析：多发布者导致频率叠加

## 🔍 问题假设

用户提出的关键假设：
> "有没有可能是经过中间处理以后以高频发布了消息，同时没有连接和延续而是以原来的topic名称发布，订阅的节点也订阅这个名称的消息，就导致了同时订阅了不同频率的同一个消息"

**这是一个非常重要的线索！**

## 📊 话题发布者分析

### 目标话题: `/robot1/right_arm/joint_follow`

根据代码分析，以下节点会发布到这个话题：

1. **teleop_bridge_node** (外骨骼桥接)
   - 文件: [teleop_bridge_node.cpp:38](external_sdk/arm_teleop/src/lbot_teleop/src/teleop_bridge_node.cpp#L38)
   - 频率: 80Hz (来自linkerta)
   - 启动文件: `teleop.launch.py`, `teleop_exo.launch.py`

2. **high_freq_resampler_node** (高频重采样器)
   - 文件: [high_freq_resampler_node.cpp:56](external_sdk/arm_teleop/src/lbot_teleop/src/high_freq_resampler_node.cpp#L56)
   - 频率: 200Hz (插值输出)
   - 启动文件: `teleop_with_resampler.launch.py`, `vision_resampler.launch.py`
   - 手动启动: `replay_to_robot.sh`

## ⚠️ 危险场景：多发布者冲突

### 场景1: 同时启动两个launch文件

```bash
# 终端1: 启动外骨骼遥操作
ros2 launch lbot_teleop teleop_exo.launch.py
# → 启动 teleop_bridge_node (80Hz)

# 终端2: 误启动视觉重采样器
ros2 run lbot_teleop high_freq_resampler_node
# → 启动 high_freq_resampler_node (200Hz)
```

**结果**: 两个节点同时发布到 `/robot1/right_arm/joint_follow`
- teleop_bridge: 80Hz
- high_freq_resampler: 200Hz
- **总频率**: 280Hz！

### 场景2: 后台进程未清理

```bash
# 之前运行了视觉控制测试
ros2 run lbot_teleop high_freq_resampler_node &

# 忘记关闭，然后启动外骨骼遥操作
ros2 launch lbot_teleop teleop_exo.launch.py
```

**结果**: 后台的 high_freq_resampler 仍在运行，导致频率叠加

### 场景3: 多个launch文件同时运行

```bash
# 可能同时运行了多个launch文件
ros2 launch lbot_teleop teleop.launch.py &
ros2 launch lbot_teleop teleop_with_resampler.launch.py &
```

**结果**: 多个 teleop_bridge 和 resampler 同时运行

## 🔬 验证方法

### 1. 检查当前运行的节点

```bash
ros2 node list | grep -E "teleop_bridge|high_freq_resampler"
```

### 2. 检查话题的发布者数量

```bash
ros2 topic info /robot1/right_arm/joint_follow
```

**正常输出**（只有1个发布者）:
```
Type: lbot_arm_interfaces/msg/FollowJoint
Publisher count: 1
Subscription count: 1
```

**异常输出**（多个发布者）:
```
Type: lbot_arm_interfaces/msg/FollowJoint
Publisher count: 2  ⚠️ 危险！
Subscription count: 1
```

### 3. 检查进程

```bash
ps aux | grep -E "teleop_bridge|high_freq_resampler"
```

## 🎯 可能的原因

### 1. 脚本启动顺序问题

检查是否有脚本同时启动了多个节点：

```bash
# 检查所有启动脚本
grep -r "teleop_bridge\|high_freq_resampler" /home/ilex/Dev/VIST/scripts/*.sh
```

### 2. Launch文件冲突

检查是否有launch文件同时包含了两个节点：

```bash
# 检查所有launch文件
grep -r "teleop_bridge\|high_freq_resampler" /home/ilex/Dev/VIST/external_sdk/arm_teleop/src/lbot_teleop/launch/*.py
```

### 3. 后台进程未清理

```bash
# 查找所有ROS2节点进程
pkill -f "teleop_bridge_node"
pkill -f "high_freq_resampler_node"
```

## 📋 建议措施

### 1. 立即检查

- [ ] 检查当前运行的节点: `ros2 node list`
- [ ] 检查话题发布者数量: `ros2 topic info /robot1/right_arm/joint_follow`
- [ ] 检查后台进程: `ps aux | grep ros2`

### 2. 防止冲突

- [ ] 在启动新节点前，先清理所有ROS2进程
- [ ] 使用互斥锁机制，确保只有一个节点发布到同一话题
- [ ] 在launch文件中添加检查，防止重复启动

### 3. 监控工具

创建一个监控脚本，实时检查话题发布者数量：

```bash
#!/bin/bash
while true; do
    echo "=== $(date) ==="
    ros2 topic info /robot1/right_arm/joint_follow | grep "Publisher count"
    sleep 1
done
```

## 🔗 相关文件

- [teleop_bridge_node.cpp](external_sdk/arm_teleop/src/lbot_teleop/src/teleop_bridge_node.cpp)
- [high_freq_resampler_node.cpp](external_sdk/arm_teleop/src/lbot_teleop/src/high_freq_resampler_node.cpp)
- [teleop_exo.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_exo.launch.py)
- [teleop_with_resampler.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py)

---

**创建时间**: 2026-02-25
**分析人员**: VIST项目组