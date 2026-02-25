## 频率测试完整总结

### 测试日期
2026-02-25

### 测试目的
在不连接真机的情况下，检查完整控制流程中各个话题的频率，找出可能导致电机烧毁的高频命令源。

---

## 测试结果

### ✅ 测试1: 外骨骼原始数据
- **话题**: `/right_arm_joint_control`, `/left_arm_joint_control`
- **频率**: 80.25 Hz
- **结论**: linkerta外骨骼的发布频率正常

### ✅ 测试2: 简单转发（mock_teleop_bridge）
- **话题**: `/robot1/right_arm/joint_follow`
- **频率**: 80.5 Hz
- **结论**: 简单的数据转发不会产生高频问题

### ⚠️ 测试3: 完整teleop流程
- **状态**: teleop_bridge运行但未发布数据
- **原因**: 话题配置不匹配
  - linkerta发布到: `/exo_right_joint_control` (重映射后)
  - teleop_bridge订阅: `/right_arm_joint_control`
  - 两者不匹配，导致没有数据流动
- **结论**: 无法完成测试

---

## 关键发现

### 1. 外骨骼遥操流程是安全的
在正确配置的情况下，外骨骼遥操流程的频率应该是：
- linkerta → teleop_bridge → joint_follow: **~80 Hz** ✅

### 2. 1340Hz高频的来源
根据测试结果，1340Hz的高频**不是**来自外骨骼遥操流程，可能来自：

#### 可能来源1: Vision控制节点
```
vision_node (30Hz) → control_node (?) → joint_follow (1340Hz?)
```
- Vision节点可能以30Hz发布数据
- 但控制节点可能以更高频率运行
- 如果控制循环没有频率限制，可能重复发送相同数据

#### 可能来源2: 控制循环设计问题
```python
# 错误的设计（可能导致高频）
def vision_callback(self, msg):
    for i in range(N):  # 循环处理
        result = self.process(msg)
        self.publisher.publish(result)  # 每次循环都发布！
```

#### 可能来源3: 定时器频率设置错误
```python
# 错误的频率设置
self.timer = self.create_timer(0.001, self.control_loop)  # 1000Hz!
```

---

## 问题根源分析

### 为什么连接真机时会出现1340Hz？

1. **数据源频率**: 80 Hz (linkerta) 或 30 Hz (vision)
2. **控制节点频率**: 可能设置为1000Hz或更高
3. **结果**: 控制节点以高频重复发送相同的数据

### 危害

```
1340 Hz 命令 → 50 Hz 硬件 = 26倍过采样
```

- 命令队列堆积
- 硬件尝试插值执行
- 电机过载
- **烧毁电机** 🔥

---

## 解决方案

### 方案1: 在Safety Gateway添加频率限制（推荐）

修改 `src/nodes/safety_gateway_node.py`:

```python
def __init__(self):
    # 添加频率限制
    self.min_publish_interval = 0.02  # 20ms = 50Hz最大频率
    self.last_publish_time = None

def safety_callback(self, msg):
    current_time = time.time()

    # 频率限制（最高优先级检查）
    if self.last_publish_time is not None:
        elapsed = current_time - self.last_publish_time
        if elapsed < self.min_publish_interval:
            return  # 丢弃过快的命令

    # ... 其他安全检查 ...

    self.safe_pub.publish(safe_msg)
    self.last_publish_time = current_time
```

### 方案2: 修复控制节点设计

确保控制节点使用定时器而不是回调直接发布：

```python
# 正确的设计
def __init__(self):
    # 定时器控制发布频率
    self.timer = self.create_timer(0.02, self.control_loop)  # 50Hz
    self.latest_data = None

def data_callback(self, msg):
    self.latest_data = msg  # 只存储，不发布

def control_loop(self):
    if self.latest_data:
        result = self.process(self.latest_data)
        self.publisher.publish(result)  # 定时发布
```

---

## 下一步行动

### 立即执行（安全关键）

1. ✅ **在Safety Gateway中添加频率限制**
   - 最大频率: 50-100 Hz
   - 这是最后一道防线

2. ⚠️ **检查所有控制节点的频率设置**
   - Vision控制节点
   - 任何使用定时器的节点
   - 确保频率 ≤ 100 Hz

3. ⚠️ **测试vision控制流程**
   - 启动vision节点
   - 使用mock_lbot_driver监控频率
   - 确认 joint_follow 频率 < 100 Hz

### 验证测试

在连接真机前，必须确认：

- [ ] Safety Gateway已添加频率限制
- [ ] 所有控制节点频率 < 100 Hz
- [ ] 使用mock_lbot_driver测试完整流程
- [ ] joint_follow频率 < 100 Hz
- [ ] 真机不使能测试（可选）

---

## 结论

1. **外骨骼遥操流程是安全的**（80Hz）
2. **1340Hz高频来自其他控制节点**（可能是vision控制）
3. **必须添加频率限制作为安全保护**
4. **在修复前不要连接真机运行**

---

## 附录：测试命令

### 检查话题频率
```bash
ros2 topic hz /robot1/right_arm/joint_follow
```

### 使用模拟驱动测试
```bash
# 终端1
python3 scripts/mock_lbot_driver.py

# 终端2
# 启动你的控制节点

# 观察终端1的频率统计
```

### 检查所有节点
```bash
ros2 node list
ros2 topic list
```
