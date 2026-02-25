# 右臂测试完整启动指南（修复版）
# Complete Startup Guide for Right Arm Test (Fixed)

## 核心修复

**问题**: teleop_bridge发布到 `/robot1/right_arm/joint_follow`，但lbot_driver订阅 `/right_arm/joint_follow`

**解决方案**: 使用ros2 topic remap重映射话题名称（不修改源码）

## 手动启动流程（5个终端）

### Terminal 1: lbot_driver
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 run lbot_driver lbot_driver --ros-args \
  --params-file src/lbot_driver/config/lbot_config.yaml
```

### Terminal 2: linkerta
```bash
ros2 run linkerta linkerta_node --ros-args \
  -p publish_left:=false \
  -p publish_right:=true
```

### Terminal 3: unified_filter_node
```bash
cd /home/ilex/Dev/VIST
./scripts/start_right_arm_filter.sh none
```

### Terminal 4: teleop_bridge（带话题重映射修复）⚠️ 关键
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

# 关键修复：使用 -r 参数重映射话题
ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file src/lbot_teleop/config/teleop_bridge_params.yaml \
  -r /robot1/right_arm/joint_follow:=/right_arm/joint_follow \
  -r /robot1/left_arm/joint_follow:=/left_arm/joint_follow
```

**重要**: Terminal 4的命令包含了话题重映射，这是修复的关键！

### Terminal 5: 验证和数据采集
```bash
cd /home/ilex/Dev/VIST

# 等待5秒让所有节点启动
sleep 5

# 检查系统状态
./scripts/check_topic_safety.sh

# 如果一切正常，开始数据采集
./scripts/collect_right_arm_data.sh exp0_no_filter 30
```

## 修复说明

### 话题重映射参数
```bash
-r /robot1/right_arm/joint_follow:=/right_arm/joint_follow
```

这个参数的作用：
- 将teleop_bridge发布的 `/robot1/right_arm/joint_follow`
- 重映射到 `/right_arm/joint_follow`
- 这样lbot_driver就能接收到控制指令了

### 修复后的数据流

```
linkerta (80Hz)
  ↓ /right_arm_joint_control
unified_filter_node (80Hz)
  ↓ /filtered_right_joint_control
teleop_bridge (80Hz)
  ↓ /robot1/right_arm/joint_follow (发布)
  ↓ [ros2 remap] (重映射)
  ↓ /right_arm/joint_follow (实际话题)
lbot_driver (50Hz)
  ↓ 机械臂硬件
```

## 验证修复

启动所有节点后，运行以下命令验证：

```bash
# 1. 检查话题连接
ros2 topic info /right_arm/joint_follow

# 应该显示:
# Publisher count: 1  ✅
# Subscription count: 1  ✅

# 2. 检查数据流
ros2 topic hz /right_arm/joint_follow

# 应该显示约80Hz

# 3. 检查机械臂是否接收到数据
ros2 topic echo /right_arm/joint_states --once

# 应该显示机械臂的实时状态
```

## 停止所有节点

### 如果使用tmux脚本
```bash
tmux kill-session -t right_arm_test
```

### 如果手动启动
在每个终端按 `Ctrl+C`

## 常见问题

### Q: 为什么不直接修改源码？
A: 保持arm_teleop SDK的原始状态，便于后续更新和维护。

### Q: 话题重映射会影响性能吗？
A: 不会，ros2的话题重映射是在节点启动时完成的，运行时没有额外开销。

### Q: 如果还是不工作怎么办？
A:
1. 检查机械臂是否已使能（web控制器）
2. 检查所有节点是否正常运行（ros2 node list）
3. 检查话题连接（./scripts/check_topic_safety.sh）
4. 查看TROUBLESHOOTING_SUMMARY.md获取详细诊断信息

---

更新日期: 2026-02-25
修复: 话题名称不匹配问题（使用ros2 remap）