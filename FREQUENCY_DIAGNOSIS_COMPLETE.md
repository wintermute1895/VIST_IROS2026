## 完整系统频率诊断指南

### 测试结果总结

#### ✅ 测试1: 外骨骼数据采集（不连接真机）
**日期**: 2026-02-25
**结果**: 正常

- `/right_arm_joint_control`: 80.25 Hz ✅
- `/left_arm_joint_control`: 80.24 Hz ✅
- `/filtered_right_joint_control`: 80.23 Hz ✅

**结论**: 外骨骼和滤波节点的频率正常，问题不在数据采集端。

---

### ⚠️ 待测试: 完整控制流程（连接真机）

#### 测试2: 外骨骼 → 真机控制

**流程**:
```
linkerta (80Hz) → teleop_bridge → /robot1/right_arm/joint_follow → lbot_driver (50Hz)
```

**测试步骤**:

1. **启动真机驱动**（终端1）:
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 run lbot_driver lbot_driver --ros-args -p arm_ip:=192.168.10.21
```

2. **启动外骨骼**（终端2）:
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 run linkerta linkerta_node
```

3. **启动teleop_bridge**（终端3）:
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop_exo.launch.py
```

4. **监控频率**（终端4）:
```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash

# 检查关键话题
ros2 topic hz /right_arm_joint_control
ros2 topic hz /robot1/right_arm/joint_follow
ros2 topic hz /robot1/right_arm/joint_states
```

**预期结果**:
- `/right_arm_joint_control`: ~80 Hz ✅
- `/robot1/right_arm/joint_follow`: **应该 ≤ 100 Hz** ⚠️
- `/robot1/right_arm/joint_states`: ~50 Hz ✅

**危险信号**:
- 如果 `/robot1/right_arm/joint_follow` > 200 Hz → **立即停止！**

---

#### 测试3: 视觉控制 → 真机

**流程**:
```
vision_node → /vision_right_joint_control → control_node → /robot1/right_arm/joint_follow → lbot_driver
```

**测试步骤**:

1. 启动真机驱动（同上）
2. 启动视觉节点
3. 启动控制节点
4. **监控所有话题频率**:

```bash
# 使用自动监控脚本
python3 scripts/monitor_frequency.py

# 或手动检查
ros2 topic hz /vision_right_joint_control
ros2 topic hz /robot1/right_arm/joint_follow
```

**预期结果**:
- 视觉节点: ~30 Hz
- joint_follow: **应该 ≤ 100 Hz**

---

### 🔧 如果发现高频问题

#### 方案1: 在Safety Gateway添加频率限制

修改 `src/nodes/safety_gateway_node.py`:

```python
def __init__(self):
    # ... 现有代码 ...

    # 添加频率限制
    self.min_publish_interval = 0.02  # 20ms = 50Hz
    self.last_publish_time = None

def safety_callback(self, msg):
    current_time = time.time()

    # ========== 频率限制（最高优先级）==========
    if self.last_publish_time is not None:
        elapsed = current_time - self.last_publish_time
        if elapsed < self.min_publish_interval:
            # 丢弃过快的命令
            return

    # ... 其他安全检查 ...

    self.safe_pub.publish(safe_msg)
    self.last_publish_time = current_time
```

#### 方案2: 在控制节点添加定时器

确保控制节点使用定时器而不是回调直接发布：

```python
# 错误方式（可能导致高频）
def data_callback(self, msg):
    result = self.process(msg)
    self.publisher.publish(result)  # ❌ 立即发布

# 正确方式（频率受控）
def __init__(self):
    self.timer = self.create_timer(0.02, self.control_loop)  # 50Hz
    self.latest_data = None

def data_callback(self, msg):
    self.latest_data = msg  # ✅ 只存储

def control_loop(self):
    if self.latest_data:
        result = self.process(self.latest_data)
        self.publisher.publish(result)  # ✅ 定时发布
```

---

### 📋 诊断检查清单

在连接真机前，确认：

- [ ] 外骨骼数据频率正常（~80Hz）✅ 已确认
- [ ] 滤波节点频率正常（~80Hz）✅ 已确认
- [ ] teleop_bridge频率正常（待测试）
- [ ] vision控制节点频率正常（待测试）
- [ ] joint_follow话题频率 < 100Hz（待测试）
- [ ] Safety Gateway已添加频率限制（待实施）

---

### ⚠️ 安全建议

**在完成以下步骤前，不要连接真机运行**:

1. ✅ 完成外骨骼数据采集测试（已完成）
2. ⚠️ 在Safety Gateway中添加频率限制（待实施）
3. ⚠️ 测试完整控制流程的频率（待测试）
4. ⚠️ 确认所有话题频率 < 100Hz（待确认）

只有在确认所有频率正常后，才能安全地连接真机！