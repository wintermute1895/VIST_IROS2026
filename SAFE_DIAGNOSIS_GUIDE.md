# 安全诊断指南：完整控制流程测试（不连接真机）

## 🎯 目标

在不连接真实机械臂的情况下，测试完整的控制数据流，检测话题冲突和频率问题。

## ⚠️ 安全说明

- ✅ 不会连接真实机械臂
- ✅ 使用mock节点代替真实驱动
- ✅ 机械臂保持急停状态
- ✅ 只测试软件数据流

## 🚀 方法1: 自动诊断脚本（推荐）

### 运行诊断脚本

```bash
cd /home/ilex/Dev/VIST
./scripts/diagnose_control_flow.sh
```

这个脚本会：
1. 清理所有现有ROS2进程
2. 启动mock驱动（代替真实硬件）
3. 启动linkerta（外骨骼）
4. 启动teleop_bridge（桥接节点）
5. **检查每个话题的发布者数量**（关键！）
6. 测量话题频率
7. 显示所有运行的节点和进程

### 观察重点

脚本会显示每个话题的发布者数量：

```
话题: /robot1/left_arm/joint_follow
  ✓ 发布者数量: 1 (正常)     ← 这是正常的
  订阅者数量: 1
```

如果看到：
```
话题: /robot1/left_arm/joint_follow
  ⚠️  发布者数量: 2 (危险！多个发布者)  ← 这就是问题！
  订阅者数量: 1
  发布者节点:
    Node name: teleop_bridge_node
    Node name: high_freq_resampler_node  ← 发现了第二个发布者
```

这就确认了话题冲突问题！

## 🔧 方法2: 手动逐步测试

### 终端1: 启动mock驱动

```bash
cd /home/ilex/Dev/VIST
python3 scripts/mock_lbot_driver.py
```

**观察**：应该看到 "等待接收 /robot1/right_arm/joint_follow..."

### 终端2: 启动linkerta

```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 run linkerta linkerta_node
```

**观察**：应该看到外骨骼数据发布

### 终端3: 检查linkerta发布的话题

```bash
# 检查话题是否存在
ros2 topic list | grep joint_control

# 检查发布者数量
ros2 topic info /left_arm_joint_control
ros2 topic info /right_arm_joint_control

# 测量频率
ros2 topic hz /left_arm_joint_control
```

**预期结果**：
- 话题存在
- Publisher count: 1
- 频率约80Hz

### 终端4: 启动teleop_bridge

```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

ros2 run lbot_teleop teleop_bridge_node \
    --ros-args \
    --params-file src/lbot_teleop/config/teleop_config.yaml \
    -p slave_namespaces:="['robot1']"
```

**观察**：应该看到 "Teleop Bridge Node initialized successfully"

### 终端5: 关键检查 - 话题发布者数量

```bash
# 检查 joint_follow 话题的发布者数量
ros2 topic info /robot1/left_arm/joint_follow
ros2 topic info /robot1/right_arm/joint_follow
```

**关键观察**：
```
Type: lbot_arm_interfaces/msg/FollowJoint
Publisher count: ?  ← 这个数字是多少？
Subscription count: 1
```

- 如果 Publisher count = 1 → ✅ 正常
- 如果 Publisher count = 2 或更多 → ⚠️ 发现问题！

### 终端6: 查看详细的发布者信息

```bash
# 使用 -v 参数查看详细信息
ros2 topic info /robot1/right_arm/joint_follow -v
```

**观察**：
```
Publishers:
  Node name: teleop_bridge_node  ← 应该只有这一个
  Node name: ???                 ← 如果有第二个，就是问题所在
```

### 终端7: 测量频率

```bash
# 测量 joint_follow 话题的频率
ros2 topic hz /robot1/right_arm/joint_follow
```

**预期结果**：
- 正常情况：约80Hz
- 异常情况：>200Hz 或 不稳定

### 终端8: 检查所有运行的节点

```bash
# 列出所有节点
ros2 node list

# 检查是否有意外的节点
ros2 node list | grep -E "teleop_bridge|high_freq_resampler"
```

**预期结果**：
- 应该只看到 `teleop_bridge_node`
- 不应该看到 `high_freq_resampler_node`

## 🔍 诊断检查清单

### 1. 话题发布者检查

- [ ] `/left_arm_joint_control` 有1个发布者（linkerta）
- [ ] `/right_arm_joint_control` 有1个发布者（linkerta）
- [ ] `/robot1/left_arm/joint_follow` 有1个发布者（teleop_bridge）
- [ ] `/robot1/right_arm/joint_follow` 有1个发布者（teleop_bridge）

### 2. 频率检查

- [ ] `/left_arm_joint_control` 约80Hz
- [ ] `/right_arm_joint_control` 约80Hz
- [ ] `/robot1/left_arm/joint_follow` 约80Hz
- [ ] `/robot1/right_arm/joint_follow` 约80Hz

### 3. 节点检查

- [ ] linkerta_node 运行中
- [ ] teleop_bridge_node 运行中
- [ ] mock_lbot_driver 运行中
- [ ] **没有** high_freq_resampler_node 运行

### 4. 进程检查

```bash
# 检查是否有多余的进程
ps aux | grep -E "teleop_bridge|high_freq_resampler" | grep -v grep
```

- [ ] 只有1个 teleop_bridge_node 进程
- [ ] 没有 high_freq_resampler_node 进程

## 🎯 如果发现问题

### 发现多个发布者

如果发现 Publisher count > 1：

1. **查看是哪些节点**：
```bash
ros2 topic info /robot1/right_arm/joint_follow -v
```

2. **停止多余的节点**：
```bash
# 如果发现 high_freq_resampler_node
pkill -f "high_freq_resampler_node"

# 如果有多个 teleop_bridge
pkill -f "teleop_bridge_node"
```

3. **重新启动**：
```bash
# 清理所有
pkill -f "linkerta_node"
pkill -f "teleop_bridge_node"
pkill -f "high_freq_resampler_node"

# 等待2秒
sleep 2

# 重新启动
./scripts/diagnose_control_flow.sh
```

### 频率异常

如果频率 > 100Hz：

1. 检查是否有多个发布者
2. 检查是否有后台进程
3. 检查是否误启动了 high_freq_resampler

## 📝 记录结果

请记录以下信息：

1. **话题发布者数量**：
   - `/robot1/right_arm/joint_follow`: ___ 个发布者
   - 发布者节点名称: _______________

2. **话题频率**：
   - `/left_arm_joint_control`: ___ Hz
   - `/robot1/right_arm/joint_follow`: ___ Hz

3. **运行的节点**：
   ```
   (粘贴 ros2 node list 的输出)
   ```

4. **异常情况**：
   - [ ] 发现多个发布者
   - [ ] 频率异常
   - [ ] 发现意外的节点
   - [ ] 其他: _______________

## 🔗 相关工具

- [check_topic_collision.sh](check_topic_collision.sh) - 话题冲突检测
- [diagnose_control_flow.sh](diagnose_control_flow.sh) - 自动诊断脚本
- [MOTOR_BURNOUT_ROOT_CAUSE.md](../MOTOR_BURNOUT_ROOT_CAUSE.md) - 根因分析

---

**创建时间**: 2026-02-25