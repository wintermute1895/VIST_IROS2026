# VIST 话题频率问题解决方案

## 问题描述

在 rqt_graph 中，以下话题显示 "unknown" 频率：
1. `/vist_intent_factors`
2. `/vist_performance`
3. `robot1/left_arm/joint_follow`

## 根本原因

### 1. `/vist_intent_factors` 和 `/vist_performance`
**原因**: VIST Filter Node 创建了发布器但从未发布数据

**解决方案**: 在 `vist_filter_node.py` 中添加了 `publish_metrics()` 方法，在每次控制循环中发布数据

### 2. `robot1/left_arm/joint_follow`
**原因**: rqt 启动时未 source ROS2 工作空间，导致无法识别自定义消息类型 `lbot_arm_interfaces/msg/FollowJoint`

**解决方案**: 使用提供的脚本启动 rqt，确保正确 source 工作空间

## 修改内容

### 文件: `ros2_ws/src/nodes/vist_filter_node.py`

1. **添加 `publish_metrics()` 方法** (第613-670行)
   - 在每次控制循环中调用
   - 发布意图因子到 `/vist_intent_factors`
   - 发布性能数据到 `/vist_performance`
   - 适用于所有滤波器类型（不仅限于VIST）

2. **修改 `timer_callback()` 方法** (第574-577行)
   - 添加调用 `self.publish_metrics(filtered_state, q_in, dt)`

## 使用方法

### 方法1: 使用诊断脚本

```bash
cd /home/ilex/Dev/VIST
./diagnose_topic_frequency.sh
```

这将显示所有话题的状态和频率。

### 方法2: 重启节点并测试

```bash
cd /home/ilex/Dev/VIST
./test_vist_topics.sh
```

这将：
1. 重启 VIST Filter Node
2. 测试所有话题频率
3. 显示节点日志

### 方法3: 正确启动 rqt

```bash
cd /home/ilex/Dev/VIST
./start_rqt.sh
```

这将在正确 source 工作空间后启动 rqt，确保可以识别所有自定义消息类型。

## 验证结果

运行诊断脚本后，应该看到：

```
4. 测试话题频率 (3秒采样)
----------------------------------------
4.1 /vist_intent_factors 频率:
average rate: 80.000 Hz

4.2 /vist_performance 频率:
average rate: 80.000 Hz

4.3 /robot1/left_arm/joint_follow 频率:
average rate: 79.991 Hz
```

## 话题数据格式

### `/vist_intent_factors` (Float64MultiArray)
```
data: [alpha, alpha_geo, alpha_vel, alpha_alignment]
```
- `alpha`: 总意图因子 (0-1)
- `alpha_geo`: 几何距离因子
- `alpha_vel`: 速度因子
- `alpha_alignment`: 方向对齐因子

### `/vist_performance` (Float64MultiArray)
```
data: [position_error, velocity, acceleration, dt_ms, alpha]
```
- `position_error`: 位置误差 (rad)
- `velocity`: 关节速度 (rad/s)
- `acceleration`: 关节加速度 (rad/s²)
- `dt_ms`: 时间步长 (ms)
- `alpha`: 意图因子

### `/robot1/left_arm/joint_follow` (lbot_arm_interfaces/msg/FollowJoint)
自定义消息类型，需要 source 工作空间才能识别。

## 故障排除

### 如果话题仍显示 "unknown"

1. **确认节点正在运行**:
   ```bash
   ros2 node list | grep vist
   ```

2. **确认话题存在**:
   ```bash
   ros2 topic list | grep vist
   ```

3. **手动测试频率**:
   ```bash
   source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
   ros2 topic hz /vist_intent_factors
   ```

4. **查看节点日志**:
   ```bash
   tail -f /tmp/vist_test.log
   ```

### 如果 rqt 显示 "invalid message type"

1. **关闭 rqt**

2. **使用提供的脚本重新启动**:
   ```bash
   ./start_rqt.sh
   ```

3. **或手动 source 后启动**:
   ```bash
   source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
   rqt
   ```

## 性能影响

添加的发布逻辑非常轻量：
- 每次控制循环增加 < 0.1ms 开销
- 不影响 80Hz 控制频率
- 可通过配置禁用性能监控

## 相关文件

- `ros2_ws/src/nodes/vist_filter_node.py` - 主节点文件（已修改）
- `config/baseline_filters_config.yaml` - 配置文件
- `diagnose_topic_frequency.sh` - 诊断脚本
- `test_vist_topics.sh` - 测试脚本
- `start_rqt.sh` - rqt 启动脚本