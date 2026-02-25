## 控制频率不匹配问题总结

### 问题描述
- **数据源**: linkerta外骨骼 @ 80 Hz
- **控制指令**: joint_follow @ 1340 Hz (异常高！)
- **硬件处理**: lbot_driver @ 50 Hz

### 危险性分析
1. **命令堆积**: 1340Hz的命令发送到50Hz的硬件，造成26倍过采样
2. **插值错误**: 硬件可能尝试在相邻命令间插值，产生不必要的高频运动
3. **电机过载**: 电机尝试跟随过快的指令变化，导致过热和烧毁
4. **控制不稳定**: 高频命令可能包含重复数据或插值数据，不是真实的控制意图

### 根本原因
控制节点的发布频率没有与数据源频率同步：
- 控制循环可能在每次收到数据时立即发布
- 或者控制循环以固定高频运行，但重复发送相同数据
- 缺少频率限制机制

### 解决方案

#### 方案1: 在控制节点添加频率限制（推荐）
```python
class ControlNode(Node):
    def __init__(self):
        # ...
        # 创建定时器，固定频率发布
        self.control_timer = self.create_timer(
            1.0 / 50.0,  # 50Hz，匹配硬件频率
            self.control_callback
        )

        self.latest_data = None

    def data_callback(self, msg):
        # 只存储数据，不立即发布
        self.latest_data = msg

    def control_callback(self):
        # 定时发布，频率受控
        if self.latest_data is not None:
            self.publish_command(self.latest_data)
```

#### 方案2: 使用ROS2的频率限制
```python
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# 设置QoS，限制发布频率
qos = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1  # 只保留最新的一条消息
)
```

#### 方案3: 在Safety Gateway中添加频率限制
在 `safety_gateway_node.py` 中添加最小时间间隔检查：

```python
def safety_callback(self, msg):
    current_time = time.time()

    # 频率限制：最小20ms间隔（50Hz）
    if self.last_publish_time is not None:
        elapsed = current_time - self.last_publish_time
        if elapsed < 0.02:  # 20ms
            return  # 丢弃过快的命令

    # ... 其他安全检查 ...

    self.safe_pub.publish(safe_msg)
    self.last_publish_time = current_time
```

### 建议的安全频率设置
- **数据采集**: 80 Hz (linkerta原生频率)
- **控制发布**: **50 Hz** (匹配硬件重采样频率)
- **硬件处理**: 50 Hz (固件频率)

### 验证方法
```bash
# 检查话题频率
ros2 topic hz /right_arm_joint_control
ros2 topic hz /robot1/right_arm/joint_follow

# 应该看到：
# /right_arm_joint_control: ~80 Hz
# /robot1/right_arm/joint_follow: ~50 Hz (不应该超过100Hz)
```

### 紧急建议
⚠️ **在修复频率问题之前，不要连接真机运行！**

1. 先在仿真或数据采集模式下验证频率
2. 确认 `joint_follow` 频率不超过100Hz
3. 添加Safety Gateway的频率限制
4. 然后才能安全地连接真机

---

**结论**: 1340Hz的控制频率确实很可能是烧电机的重要原因之一。必须添加频率限制机制。