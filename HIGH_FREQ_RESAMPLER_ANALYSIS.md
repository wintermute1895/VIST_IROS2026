# 高频重采样器分析报告

## 🔍 问题发现

在调查电机烧毁事故时，发现控制指令频率异常高（1340Hz），远超硬件能力（50Hz）。经过深入分析，**确认高频重采样器（high_freq_resampler）是导致问题的关键因素之一**。

## 📊 关键证据

### 1. 高频重采样器节点代码

**文件**: [external_sdk/arm_teleop/src/lbot_teleop/src/high_freq_resampler_node.cpp](external_sdk/arm_teleop/src/lbot_teleop/src/high_freq_resampler_node.cpp)

```cpp
// 第40-44行：创建200Hz定时器
timer_ = this->create_wall_timer(
    std::chrono::milliseconds(static_cast<int>(1000.0 / output_freq_hz_)),
    std::bind(&HighFreqResamplerNode::timer_callback, this)
);
```

**配置文件**: [external_sdk/arm_teleop/src/lbot_teleop/config/high_freq_resampler.yaml](external_sdk/arm_teleop/src/lbot_teleop/config/high_freq_resampler.yaml)

```yaml
high_freq_resampler_node:
  ros__parameters:
    output_freq_hz: 200.0  # 输出频率200Hz
    ema_alpha: 0.3         # EMA平滑系数
```

### 2. 启动文件分析

#### ✅ 正常启动文件（无重采样器）

**文件**: [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py:1-99)

```python
# 启动顺序:
# 1. lbot_driver (从臂)
# 2. linkerta (主臂/外骨骼) - 80Hz
# 3. teleop_bridge (桥接节点) - 直通，不改变频率
```

**架构流程**:
```
linkerta (80Hz) → teleop_bridge → lbot_driver (50Hz)
```

#### ⚠️ 危险启动文件（包含重采样器）

**文件**: [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py:1-97)

```python
# 启动顺序:
# 1. lbot_driver (从臂)
# 2. linkerta (主臂) - 20-30Hz
# 3. high_freq_resampler - 200Hz输出！
# 注意: 不启动teleop_bridge，因为resampler已经处理了转换
```

**架构流程**:
```
linkerta (20-30Hz) → high_freq_resampler (200Hz) → lbot_driver (50Hz)
```

### 3. 实际使用情况

通过检查项目中的脚本和文档，发现：

1. **外骨骼遥操作**使用 `teleop.launch.py` 或 `teleop_exo.launch.py`
   - ✅ 这些启动文件**不包含**高频重采样器
   - ✅ 直接使用 teleop_bridge，保持80Hz频率

2. **视觉控制回放**使用 `replay_to_robot.sh`
   - ⚠️ 这个脚本**明确启动了**高频重采样器！
   - ⚠️ 使用 `vision_resampler.yaml` 配置（200Hz输出）

**文件**: [scripts/archive_unsafe/replay_to_robot.sh](scripts/archive_unsafe/replay_to_robot.sh:94-105)

```bash
echo "启动high_freq_resampler..."
ros2 run lbot_teleop high_freq_resampler_node \
    --ros-args \
    --params-file external_sdk/arm_teleop/src/lbot_teleop/config/vision_resampler.yaml \
    > /tmp/resampler.log 2>&1 &
```

## 🔄 完整数据流分析

### 场景1: 外骨骼遥操作（安全）

```
linkerta_node (80Hz)
    ↓ 发布到 /left_arm_joint_control
teleop_bridge_node (直通，80Hz)
    ↓ 发布到 /robot1/left_arm/joint_follow
lbot_driver (接收80Hz，执行50Hz)
    ↓
机器人硬件 (50Hz)
```

**话题流**:
- `/left_arm_joint_control` (sensor_msgs/JointState, 80Hz)
- `/robot1/left_arm/joint_follow` (lbot_arm_interfaces/FollowJoint, 80Hz)

**结论**: ✅ 安全，频率匹配合理

### 场景2: 视觉控制 + 高频重采样器（危险）

```
vist_ros2_bridge.py (30Hz)
    ↓ 发布到 /vision_left_joint_control
high_freq_resampler_node (200Hz插值！)
    ↓ 发布到 /robot1/left_arm/joint_follow
lbot_driver (接收200Hz，执行50Hz)
    ↓
机器人硬件 (50Hz) ⚠️ 指令堆积！
```

**话题流**:
- `/vision_left_joint_control` (sensor_msgs/JointState, 30Hz)
- `/robot1/left_arm/joint_follow` (lbot_arm_interfaces/FollowJoint, 200Hz)

**结论**: ⚠️ 危险！200Hz远超硬件能力，导致指令堆积

### 场景3: 视觉控制直连（理想）

```
vist_ros2_bridge.py (30Hz)
    ↓ 发布到 /robot1/left_arm/joint_follow
lbot_driver (接收30Hz，执行50Hz)
    ↓
机器人硬件 (50Hz)
```

**话题流**:
- `/robot1/left_arm/joint_follow` (lbot_arm_interfaces/FollowJoint, 30Hz)

**结论**: ✅ 理想，频率低于硬件能力

## 🎯 结论

### 高频重采样器的作用

1. **设计目的**: 将低频视觉输入（20-30Hz）插值到200Hz，提高控制平滑度
2. **实现方式**: 使用EMA（指数移动平均）进行插值
3. **输出频率**: 固定200Hz
4. **话题订阅**: `/vision_left_joint_control`, `/vision_right_joint_control`
5. **话题发布**: `/robot1/left_arm/joint_follow`, `/robot1/right_arm/joint_follow`

### 是否导致电机烧毁？

**确认：高频重采样器是主要原因之一**：

1. ✅ **确认**: 高频重采样器将30Hz视觉输入提升到200Hz
2. ✅ **确认**: 200Hz远超硬件能力（50Hz），导致指令堆积4倍
3. ✅ **确认**: `replay_to_robot.sh` 明确启动了高频重采样器
4. ❓ **疑问**: 为什么监控到的频率是1340Hz而不是200Hz？
   - 可能是测量方法问题（累计多个话题的频率）
   - 可能是多个节点同时发送
   - 可能是ROS2消息队列堆积导致的突发频率
   - 需要进一步调查

### 使用场景分析

| 场景 | 启动文件 | 是否使用重采样器 | 风险等级 |
|------|---------|----------------|---------|
| 外骨骼遥操作 | `teleop.launch.py` | ❌ 否 | ✅ 安全 |
| 外骨骼遥操作（重映射） | `teleop_exo.launch.py` | ❌ 否 | ✅ 安全 |
| 视觉控制回放 | `replay_to_robot.sh` | ⚠️ 是 (200Hz) | ⚠️ 危险 |
| 视觉控制实时 | `vist_ros2_bridge.py` | ❓ 未知 | ❓ 待确认 |

## 📋 建议措施

### 1. 立即措施

- [ ] 停止使用 `replay_to_robot.sh` 中的高频重采样器
- [ ] 检查所有启动脚本，确认是否误用了重采样器
- [ ] 在Safety Gateway中添加频率限制（最大50-100Hz）

### 2. 长期措施

- [ ] 重新评估高频重采样器的必要性
  - 如果硬件只支持50Hz，200Hz插值没有意义
  - 考虑降低输出频率到50-100Hz
- [ ] 添加频率监控和自动限流
- [ ] 在文档中明确标注危险配置

### 3. 进一步调查

- [ ] 确认1340Hz频率的来源（是否还有其他放大因素）
- [ ] 测试不同频率配置下的系统行为
- [ ] 分析为什么200Hz会被放大到1340Hz

## 🔗 相关文件

- [high_freq_resampler_node.cpp](external_sdk/arm_teleop/src/lbot_teleop/src/high_freq_resampler_node.cpp)
- [high_freq_resampler.yaml](external_sdk/arm_teleop/src/lbot_teleop/config/high_freq_resampler.yaml)
- [vision_resampler.yaml](external_sdk/arm_teleop/src/lbot_teleop/config/vision_resampler.yaml)
- [teleop_with_resampler.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py)
- [replay_to_robot.sh](scripts/archive_unsafe/replay_to_robot.sh)

---

**创建时间**: 2026-02-25
**分析人员**: VIST项目组