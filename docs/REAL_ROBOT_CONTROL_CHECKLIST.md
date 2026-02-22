# 真机控制系统检查清单

## 给 Claude 的提示词

```
我需要你系统性地检查真机控制代码，找出可能导致以下问题的根本原因：
1. 关节振荡（高频来回抖动）
2. 运动不平滑（咣当、jerky motion）
3. 跟踪误差累积
4. 控制频率不稳定
5. 状态同步问题

请按照以下维度进行深度分析：
```

---

## 1. 控制流程完整性检查

### 1.1 数据流路径
```
视觉节点 → UDP接收 → VIST控制器 → 轨迹插值器 → 关节锁定 → 状态反馈 → 机器人硬件
```

**检查点**：
- [ ] 每个环节的输入输出维度是否匹配？
- [ ] 是否有数据丢失或未传递的情况？
- [ ] 坐标系转换是否正确？

**关键文件**：
- `scripts/run_real_robot_vist_refactored.py` (主控制循环)
- `src/robot/robot_interface.py` (硬件接口)
- `src/control/vist_controller.py` (算法层)

---

## 2. 时间同步与频率稳定性

### 2.1 控制频率
**目标**：20 Hz (dt = 0.05s)
**实际**：需要测量

**检查点**：
- [ ] `get_state()` 的调用频率是否稳定？
- [ ] UDP接收是否有延迟或丢包？
- [ ] 插值器的 dt 是否与实际控制周期一致？
- [ ] 是否有阻塞操作影响频率？

**可能问题**：
```python
# 问题1：dt 假设与实际不符
config.dt = 0.05  # 假设 20Hz
actual_dt = 0.059  # 实际 16.9Hz
# 影响：速度/加速度计算不准确

# 问题2：阻塞读取
q_actual = robot.get_state()  # 可能阻塞
```

---

## 3. 状态反馈与闭环控制

### 3.1 状态读取
**当前实现**：
```python
_, q_actual, _ = self.robot.driver.get_state()
self.controller.safety_controller.update_actual_command(q_actual)
self.interpolator.q_current = q_actual.copy()
```

**检查点**：
- [ ] `get_state()` 是否每帧都调用？
- [ ] 返回的是实际位置还是命令位置？
- [ ] 是否有读取失败的异常处理？
- [ ] 状态更新的顺序是否正确？

**可能问题**：
```python
# 问题1：状态更新顺序错误
self.interpolator.q_current = q_actual  # 先更新插值器
self.safety_controller.update(q_actual)  # 后更新安全控制器
# 可能导致：插值器和安全控制器状态不一致

# 问题2：异常时回退到命令值
except Exception:
    self.safety_controller.update(q_command)  # 开环模式
# 可能导致：误差累积
```

---

## 4. 速度估计与数值稳定性

### 4.1 速度估计方法
**当前配置**：
```yaml
velocity_estimation_method: "kalman"  # 使用卡尔曼滤波
```

**检查点**：
- [ ] VIST 卡尔曼滤波器的速度估计是否被正确传递？
- [ ] 如果回退到数值微分，是否有低通滤波？
- [ ] 速度估计是否有异常值（NaN, Inf）？

**可能问题**：
```python
# 问题1：速度估计未传递
q_dot_estimated = self._get_velocity_estimate()
if q_dot_estimated is None:
    # 回退到数值微分（噪声大）
    q_dot = (q_current - q_previous) / dt

# 问题2：数值微分噪声
q_dot_numerical = (q[k] - q[k-1]) / dt
# 高频噪声 → 加速度估计不准 → 安全限制误触发
```

---

## 5. 轨迹插值器

### 5.1 插值器状态同步
**关键代码**：
```python
q_interpolated = self.interpolator.interpolate(q_target)
# ... 发送命令 ...
q_actual = robot.get_state()
self.interpolator.q_current = q_actual  # 同步实际位置
```

**检查点**：
- [ ] 插值器的起点是否是实际位置？
- [ ] 插值器的 dt 是否与控制周期一致？
- [ ] 速度和加速度限制是否合理？
- [ ] 是否有状态重置的时机？

**可能问题**：
```python
# 问题1：起点不连续
q_interpolated = interpolator.interpolate(q_target)
# 如果 interpolator.q_current != q_actual
# 会导致：突然的跳变

# 问题2：参数不匹配
interpolator.dt = 0.05  # 假设
actual_dt = 0.059       # 实际
# 影响：速度/加速度计算偏差
```

---

## 6. 安全控制器

### 6.1 限制触发频率
**观察**：速度限制 542/542 次，加速度限制 542/542 次

**检查点**：
- [ ] 限制参数是否过于保守？
- [ ] 速度/加速度计算是否准确？
- [ ] 是否有累积误差导致频繁触发？

**可能问题**：
```python
# 问题1：参数过于保守
max_velocity = 0.3 rad/s  # 17°/s，可能太小
max_acceleration = 0.5 rad/s²  # 29°/s²，可能太小

# 问题2：速度计算不准确
q_dot = (q_target - q_current) / dt  # 数值微分
# 如果 q_current 不是实际位置 → 速度估计错误

# 问题3：每帧都触发限制
if abs(q_dot) > max_vel:
    # 每帧都限制 → "咣当"现象
```

---

## 7. 关节锁定机制

### 7.1 锁定逻辑
**当前实现**：
```python
for i in range(len(q_command)):
    if not self.joint_enabled[i]:
        q_command[i] = self.q_init[i]  # 锁定到初始位置
```

**检查点**：
- [ ] 锁定后是否更新了安全控制器状态？
- [ ] 锁定后是否更新了插值器状态？
- [ ] 锁定的关节是否会影响其他关节？

**可能问题**：
```python
# 问题1：状态不同步
q_command[i] = q_init[i]  # 锁定
safety_controller.update(q_command)  # 正确 ✓
interpolator.q_current = q_actual    # 但 q_actual[i] 可能不等于 q_init[i]
# 导致：插值器和安全控制器状态不一致

# 问题2：锁定关节的耦合
# 如果关节 i 被锁定，但其他关节的运动会影响关节 i
# 可能导致：锁定失效或振荡
```

---

## 8. 非阻塞模式与命令发送

### 8.1 命令发送
**当前配置**：
```yaml
move_joint_block: false  # 非阻塞模式
```

**检查点**：
- [ ] 非阻塞模式下，命令是否被覆盖？
- [ ] 机器人是否能跟上命令频率？
- [ ] 是否有命令队列积压？

**可能问题**：
```python
# 问题1：命令覆盖
robot.send_command(q1, blocking=False)  # 发送命令1
# ... 50ms 后 ...
robot.send_command(q2, blocking=False)  # 发送命令2
# 如果命令1还没执行完，会被命令2覆盖

# 问题2：跟踪延迟
# 机器人实际位置落后于命令位置
# 如果不读取实际位置 → 误差累积
```

---

## 9. SDK 参数与硬件限制

### 9.1 SDK 运动参数
**当前配置**：
```yaml
move_joint_speed: 0.3 rad/s
move_joint_accel: 0.5 rad/s²
```

**检查点**：
- [ ] SDK 参数是否与安全控制器参数一致？
- [ ] SDK 是否有内部限制？
- [ ] 是否有电机过热保护？

**可能问题**：
```python
# 问题1：双重限制
# 安全控制器限制：0.3 rad/s
# SDK 内部限制：0.3 rad/s
# 结果：实际速度可能更低

# 问题2：参数不匹配
safety_controller.max_vel = 0.3
sdk.move_joint_speed = 0.5  # 不一致
# 可能导致：行为不可预测
```

---

## 10. 负载与物理效应

### 10.1 重负载影响
**观察**：末端手的重量导致振荡

**检查点**：
- [ ] 是否有重力补偿？
- [ ] 参数是否针对负载调整？
- [ ] 是否有自适应机制？

**可能问题**：
```python
# 问题1：无重力补偿
# 机器人需要更大的力矩来克服重力
# 但控制器不知道 → 跟踪误差 → 振荡

# 问题2：参数固定
# 有负载时需要更保守的参数
# 无负载时可以更激进
# 当前：固定参数 → 不适应
```

---

## 11. 测试建议

### 11.1 基础测试（无视觉）
```python
# 测试1：固定目标位置
q_target = q_init + [0.1, 0, 0, 0, 0, 0, 0]  # 只移动关节0
# 观察：是否平滑到达？是否振荡？

# 测试2：正弦波跟踪
q_target[0] = q_init[0] + 0.1 * sin(2*pi*0.5*t)
# 观察：跟踪误差？频率响应？

# 测试3：阶跃响应
q_target = q_init
# t=1s 时突然变为 q_init + [0.2, 0, 0, 0, 0, 0, 0]
# 观察：是否有"咣当"？过冲？
```

### 11.2 消融实验
```yaml
# 实验1：关闭插值器
# 直接发送 VIST 输出
# 观察：是否更"咣当"？

# 实验2：关闭闭环反馈
# 不读取实际位置
# 观察：误差是否累积？

# 实验3：不同速度估计方法
velocity_estimation_method: "numerical"
# 观察：是否更抖动？
```

---

## 12. 诊断工具

### 12.1 数据记录
```python
# 记录关键数据
log = {
    'timestamp': [],
    'q_target': [],      # VIST 输出
    'q_interpolated': [], # 插值器输出
    'q_command': [],     # 发送的命令
    'q_actual': [],      # 实际位置
    'q_dot_estimated': [], # 速度估计
    'tracking_error': [], # 跟踪误差
    'safety_triggers': [] # 安全限制触发
}
```

### 12.2 可视化
```python
# 绘制时间序列
plt.plot(t, q_target, label='Target')
plt.plot(t, q_actual, label='Actual')
plt.plot(t, tracking_error, label='Error')

# 绘制频谱
fft_result = np.fft.fft(q_actual)
# 观察：是否有高频振荡？
```

---

## 13. 关键问题清单

请重点检查以下问题：

1. **状态同步**：
   - [ ] 插值器、安全控制器、VIST 滤波器的状态是否一致？
   - [ ] 关节锁定后状态是否正确更新？

2. **时间一致性**：
   - [ ] 所有模块的 dt 是否一致？
   - [ ] 实际控制频率是否稳定？

3. **速度估计**：
   - [ ] 卡尔曼滤波的速度是否被使用？
   - [ ] 数值微分是否有滤波？

4. **参数匹配**：
   - [ ] 安全控制器参数 vs SDK 参数
   - [ ] 插值器参数 vs 配置参数

5. **闭环反馈**：
   - [ ] 是否每帧读取实际位置？
   - [ ] 读取失败时的处理是否正确？

6. **物理约束**：
   - [ ] 负载是否考虑？
   - [ ] 是否有重力补偿？

---

## 14. 预期输出

请提供以下分析：

1. **潜在问题列表**：按严重程度排序
2. **根本原因分析**：每个问题的物理/数学解释
3. **修复建议**：具体的代码修改
4. **测试方案**：如何验证修复效果
5. **优先级排序**：哪些问题应该先解决

---

## 15. 参考信息

**当前状态**：
- 控制频率：16.9 Hz（目标 20 Hz）
- 安全限制触发：542/542 次（100%）
- 跟踪误差：需要测量
- 视觉系统：未标定，不可用

**已实现的改进**：
- ✅ 轨迹插值器（梯形速度曲线）
- ✅ 闭环状态反馈
- ✅ 速度估计配置化
- ✅ 状态同步修复

**待测试**：
- 真机控制效果
- 消融实验
- 参数优化