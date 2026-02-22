# 真机控制系统代码检查报告

**检查日期**: 2026-02-22
**检查范围**: 控制流程、状态同步、速度估计、安全控制器、轨迹插值器
**检查方法**: 基于 Gemini 检查清单的系统性代码审查

---

## 执行摘要

通过系统性检查，发现了 **3个严重问题（P0）** 和 **5个中等问题（P1）**，这些问题是导致关节振荡、"咣当"现象和跟踪误差累积的根本原因。

**最关键的发现**：
1. 卡尔曼滤波的速度估计被数值微分覆盖，导致完全没有被使用
2. 安全控制器的速度/加速度计算基于错误的状态，导致频繁误触发限制
3. 状态同步顺序混乱，导致插值器、安全控制器、VIST滤波器状态不一致

---

## P0 严重问题（必须立即修复）

### 问题 1: 卡尔曼滤波速度估计被覆盖 ⚠️⚠️⚠️

**位置**: [src/control/safe_robot_controller.py:209-266](src/control/safe_robot_controller.py#L209-L266)

**问题描述**:
```python
def process_command(self, q_target, q_dot_estimated=None):
    # 第223行：接收卡尔曼滤波的速度估计
    if q_dot_estimated is not None:
        self.q_dot_current = np.array(q_dot_estimated).copy()

    # ... 中间处理 ...

    # 第266行：重新用数值微分计算速度，覆盖了卡尔曼滤波的估计！
    self.q_dot_current = (q_safe - self.q_previous) / self.dt
```

**影响**:
- 即使配置了 `velocity_estimation_method: "kalman"`，卡尔曼滤波的速度估计也完全没有被使用
- 回退到噪声更大的数值微分
- 导致加速度估计不准确，频繁触发加速度限制
- 这是导致"咣当"现象的主要原因之一

**根本原因**:
`process_command()` 方法在结尾无条件地重新计算速度，覆盖了传入的 `q_dot_estimated`

**修复建议**:
```python
def process_command(self, q_target, q_dot_estimated=None):
    # ... 前面的代码不变 ...

    # 更新状态
    self.q_previous = self.q_current.copy()
    self.q_dot_previous = self.q_dot_current.copy()
    self.q_current = q_safe.copy()

    # 只有在没有提供速度估计时才使用数值微分
    if q_dot_estimated is None:
        self.q_dot_current = (q_safe - self.q_previous) / self.dt
    # 否则保持使用传入的 q_dot_estimated（已在开头设置）

    return q_safe, safety_status
```

---

### 问题 2: 安全控制器速度/加速度计算基于错误状态 ⚠️⚠️

**位置**: [src/control/safe_robot_controller.py:143-207](src/control/safe_robot_controller.py#L143-L207)

**问题描述**:
```python
def limit_velocity(self, q_target):
    # 第155行：基于 self.q_current 计算速度
    q_dot_target = (q_target - self.q_current) / self.dt
    # ...

def limit_acceleration(self, q_target):
    # 第186行：基于 self.q_current 计算速度
    q_dot_target = (q_target - self.q_current) / self.dt
    # 第189行：基于 self.q_dot_current 计算加速度
    q_ddot_target = (q_dot_target - self.q_dot_current) / self.dt
    # ...
```

**问题分析**:
在真机控制循环中，状态更新顺序是：
1. `process_command(q_target)` → 更新 `q_current = q_safe`（命令位置）
2. `send_command(q_command)` → 发送到机器人
3. `get_state()` → 读取实际位置 `q_actual`
4. `update_actual_command(q_actual)` → 更新 `q_current = q_actual`（实际位置）

这导致：
- 在下一帧调用 `process_command()` 时，`self.q_current` 是上一帧的实际位置
- 但 `self.q_dot_current` 可能是基于命令位置计算的
- 两者不一致，导致速度/加速度计算错误

**影响**:
- 速度/加速度限制频繁误触发（542/542次 = 100%）
- 即使目标速度在限制范围内，也会被错误地限制
- 导致运动不平滑，出现"咣当"现象

**修复建议**:
方案1：确保状态一致性
```python
def update_actual_command(self, q_actual):
    """更新实际发送给机器人的指令"""
    # 先计算速度（基于旧的 q_current）
    q_dot_new = (q_actual - self.q_current) / self.dt

    # 再更新位置和速度
    self.q_previous = self.q_current.copy()
    self.q_dot_previous = self.q_dot_current.copy()
    self.q_current = np.array(q_actual).copy()
    self.q_dot_current = q_dot_new
```

方案2：分离命令状态和实际状态
```python
class SafeRobotController:
    def __init__(self, ...):
        # 命令状态（用于限制计算）
        self.q_command = np.zeros(7)
        self.q_dot_command = np.zeros(7)

        # 实际状态（用于反馈）
        self.q_actual = np.zeros(7)
        self.q_dot_actual = np.zeros(7)
```

---

### 问题 3: 状态同步顺序混乱 ⚠️⚠️

**位置**: [scripts/run_real_robot_vist_refactored.py:276-281](scripts/run_real_robot_vist_refactored.py#L276-L281)

**问题描述**:
```python
# 第276-277行：先更新安全控制器
self.controller.safety_controller.update_actual_command(q_actual)

# 第280-281行：再更新插值器
self.interpolator.q_current = q_actual.copy()
```

但是，`update_actual_command()` 会重新计算速度：
```python
def update_actual_command(self, q_actual):
    self.q_current = np.array(q_actual).copy()
    self.q_dot_current = (self.q_current - self.q_previous) / self.dt
```

**问题分析**:
1. 插值器有自己的速度状态 `q_dot_current`
2. 安全控制器也有自己的速度状态 `q_dot_current`
3. 两者的速度计算方式不同：
   - 插值器：基于加速度限制的梯形速度曲线
   - 安全控制器：基于数值微分
4. 当更新实际位置时，两者的速度状态不一致

**影响**:
- 插值器认为当前速度是 v1
- 安全控制器认为当前速度是 v2
- 下一帧计算加速度时，基于不同的速度基准
- 导致加速度估计错误，频繁触发限制

**修复建议**:
```python
# 方案1：同步速度状态
q_actual_velocity = self.interpolator.get_current_velocity()
self.controller.safety_controller.update_actual_command(q_actual)
# 覆盖安全控制器的速度为插值器的速度
self.controller.safety_controller.q_dot_current = q_actual_velocity.copy()

# 方案2：让插值器也读取实际位置和速度
_, q_actual, q_dot_actual = self.robot.driver.get_state()
self.interpolator.q_current = q_actual.copy()
self.interpolator.q_dot_current = q_dot_actual.copy()  # 如果SDK提供速度
```

---

## P1 中等问题（应该尽快修复）

### 问题 4: 实际控制频率不稳定

**观察**: 目标20Hz，实际16.9Hz（偏差15.5%）

**可能原因**:
1. `get_state()` 调用耗时过长
2. VIST求解耗时不稳定
3. UDP接收阻塞
4. 其他计算开销

**影响**:
- 插值器和安全控制器假设 dt=0.05s
- 实际 dt≈0.059s
- 速度/加速度计算偏差 18%
- 导致限制参数不准确

**修复建议**:
```python
# 方案1：测量实际dt
actual_dt = time.time() - last_update_time
self.interpolator.dt = actual_dt
self.controller.safety_controller.dt = actual_dt

# 方案2：优化性能
# - 使用非阻塞的get_state()
# - 减少VIST求解迭代次数
# - 优化UDP接收
```

---

### 问题 5: 关节锁定后的状态不一致

**位置**: [scripts/run_real_robot_vist_refactored.py:256-260](scripts/run_real_robot_vist_refactored.py#L256-L260)

**问题描述**:
```python
q_command = q_interpolated.copy()
for i in range(len(q_command)):
    if not self.joint_enabled[i]:
        q_command[i] = self.q_init[i]  # 锁定到初始位置
```

**问题分析**:
- 锁定的关节被设置为 `q_init[i]`
- 但实际位置可能不等于 `q_init[i]`（由于重力、摩擦等）
- 当读取 `q_actual` 时，`q_actual[i] ≠ q_init[i]`
- 导致插值器和安全控制器的状态不一致

**影响**:
- 锁定的关节可能出现小幅振荡
- 跟踪误差增大
- 安全控制器误判速度/加速度

**修复建议**:
```python
# 方案1：锁定到实际位置而不是初始位置
_, q_actual, _ = self.robot.driver.get_state()
for i in range(len(q_command)):
    if not self.joint_enabled[i]:
        q_command[i] = q_actual[i]  # 锁定到当前实际位置

# 方案2：在插值器和安全控制器中也锁定
self.interpolator.lock_joint(i, q_actual[i])
self.controller.safety_controller.lock_joint(i, q_actual[i])
```

---

### 问题 6: 安全限制参数可能过于保守

**当前配置**:
```yaml
max_joint_velocity: 0.3 rad/s      # 17°/s
max_joint_acceleration: 0.5 rad/s²  # 29°/s²
```

**观察**: 速度限制 542/542次，加速度限制 542/542次（100%触发率）

**分析**:
- 如果每帧都触发限制，说明参数可能过于保守
- 或者速度/加速度计算有问题（见问题1-3）

**建议**:
1. 先修复问题1-3，确保速度/加速度计算正确
2. 然后测试实际触发率
3. 如果仍然100%触发，适当放宽限制：
   ```yaml
   max_joint_velocity: 0.5 rad/s      # 29°/s
   max_joint_acceleration: 1.0 rad/s²  # 57°/s²
   ```

---

### 问题 7: 插值器dt与实际控制周期不匹配

**问题**: 插值器假设固定dt，但实际控制周期可能变化

**影响**:
- 速度/加速度限制不准确
- 轨迹规划偏差

**修复建议**:
```python
# 在每帧更新插值器的dt
actual_dt = time.time() - last_update_time
q_interpolated = self.interpolator.interpolate(q_target, dt=actual_dt)
```

---

### 问题 8: 数值微分噪声未滤波

**位置**: 当 `velocity_estimation_method: "numerical"` 时

**问题**: 数值微分 `(q[k] - q[k-1]) / dt` 对噪声敏感

**影响**:
- 速度估计噪声大
- 加速度估计噪声更大
- 频繁触发安全限制

**修复建议**:
```python
# 添加低通滤波器
class LowPassFilter:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value

# 在安全控制器中使用
self.velocity_filter = [LowPassFilter() for _ in range(7)]
q_dot_filtered = [f.update(v) for f, v in zip(self.velocity_filter, q_dot_raw)]
```

---

## 修复优先级

### 立即修复（本周内）:
1. ✅ **问题1**: 修复卡尔曼滤波速度估计被覆盖
2. ✅ **问题2**: 修复安全控制器状态一致性
3. ✅ **问题3**: 修复状态同步顺序

### 尽快修复（下周内）:
4. ⚠️ **问题4**: 优化控制频率稳定性
5. ⚠️ **问题5**: 修复关节锁定状态同步
6. ⚠️ **问题6**: 调整安全限制参数

### 后续优化:
7. 📝 **问题7**: 动态dt适配
8. 📝 **问题8**: 数值微分滤波

---

## 测试建议

### 1. 单元测试
```python
# 测试安全控制器状态一致性
def test_safety_controller_state_consistency():
    controller = SafeRobotController(config)

    # 设置初始状态
    q_init = np.zeros(7)
    controller.q_current = q_init

    # 发送命令
    q_target = np.array([0.1] * 7)
    q_dot_estimated = np.array([0.5] * 7)
    q_safe, _ = controller.process_command(q_target, q_dot_estimated)

    # 验证速度没有被覆盖
    assert np.allclose(controller.q_dot_current, q_dot_estimated)
```

### 2. 集成测试
```python
# 测试完整控制循环
def test_full_control_loop():
    # 固定目标位置测试
    q_target = q_init + [0.1, 0, 0, 0, 0, 0, 0]

    # 运行100帧
    for i in range(100):
        q_command = controller.process(q_target)
        robot.send_command(q_command)
        q_actual = robot.get_state()

        # 记录数据
        log_data(i, q_target, q_command, q_actual)

    # 分析结果
    analyze_tracking_error()
    analyze_velocity_profile()
    analyze_safety_triggers()
```

### 3. 消融实验
```yaml
# 实验1：卡尔曼 vs 数值微分
velocity_estimation_method: "kalman"  # 然后改为 "numerical"

# 实验2：有插值器 vs 无插值器
# 注释掉插值器代码，直接发送VIST输出

# 实验3：闭环 vs 开环
# 注释掉 get_state() 和状态同步代码
```

---

## 预期效果

修复这些问题后，预期：
1. ✅ 安全限制触发率从100%降低到<10%
2. ✅ 关节振荡幅度减小50%以上
3. ✅ "咣当"现象消失或显著减轻
4. ✅ 跟踪误差减小30%以上
5. ✅ 控制频率稳定在19-20Hz

---

## 附录：关键代码位置

| 问题 | 文件 | 行号 | 优先级 |
|------|------|------|--------|
| 速度估计被覆盖 | [safe_robot_controller.py](src/control/safe_robot_controller.py) | 209-266 | P0 |
| 状态计算错误 | [safe_robot_controller.py](src/control/safe_robot_controller.py) | 143-207 | P0 |
| 状态同步混乱 | [run_real_robot_vist_refactored.py](scripts/run_real_robot_vist_refactored.py) | 276-281 | P0 |
| 频率不稳定 | [run_real_robot_vist_refactored.py](scripts/run_real_robot_vist_refactored.py) | 207-218 | P1 |
| 关节锁定 | [run_real_robot_vist_refactored.py](scripts/run_real_robot_vist_refactored.py) | 256-260 | P1 |

---

**报告生成时间**: 2026-02-22
**检查工具**: Claude Code + Gemini Checklist
**下一步**: 按优先级修复问题，然后进行测试验证