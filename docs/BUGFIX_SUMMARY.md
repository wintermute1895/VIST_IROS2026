# 真机控制系统 Bug 修复摘要

**修复日期**: 2026-02-22
**修复范围**: P0 严重问题（3个）
**预期效果**: 消除"咣当"现象，减少振荡，降低安全限制触发率

---

## 修复的问题

### ✅ 问题 1: 卡尔曼滤波速度估计被覆盖

**文件**: [src/control/safe_robot_controller.py](src/control/safe_robot_controller.py#L209-L281)

**问题描述**:
- `process_command()` 方法在结尾无条件地重新计算速度
- 即使传入了卡尔曼滤波的速度估计，也会被数值微分覆盖
- 导致配置的 `velocity_estimation_method: "kalman"` 完全无效

**修复内容**:
```python
# 修复前
def process_command(self, q_target, q_dot_estimated=None):
    if q_dot_estimated is not None:
        self.q_dot_current = np.array(q_dot_estimated).copy()
    # ... 处理 ...
    self.q_dot_current = (q_safe - self.q_previous) / self.dt  # 覆盖！

# 修复后
def process_command(self, q_target, q_dot_estimated=None):
    has_velocity_estimate = q_dot_estimated is not None
    if has_velocity_estimate:
        self.q_dot_current = np.array(q_dot_estimated).copy()
    # ... 处理 ...
    # 只有在没有提供速度估计时才使用数值微分
    if not has_velocity_estimate:
        self.q_dot_current = (q_safe - self.q_previous) / self.dt
```

**预期效果**:
- 卡尔曼滤波的速度估计被正确使用
- 速度估计噪声减小
- 加速度计算更准确
- 安全限制触发率降低

---

### ✅ 问题 2: 安全控制器状态计算错误

**文件**: [src/control/safe_robot_controller.py](src/control/safe_robot_controller.py#L324-L343)

**问题描述**:
- `update_actual_command()` 方法的状态更新顺序不当
- 没有正确更新 `q_previous` 和 `q_dot_previous`
- 导致下一帧的速度/加速度计算基于不一致的状态

**修复内容**:
```python
# 修复前
def update_actual_command(self, q_actual):
    self.q_current = np.array(q_actual).copy()
    self.q_dot_current = (self.q_current - self.q_previous) / self.dt

# 修复后
def update_actual_command(self, q_actual):
    # 先计算速度（基于旧的 q_current，确保状态一致性）
    q_dot_new = (np.array(q_actual) - self.q_current) / self.dt

    # 再更新位置和速度
    self.q_previous = self.q_current.copy()
    self.q_dot_previous = self.q_dot_current.copy()
    self.q_current = np.array(q_actual).copy()
    self.q_dot_current = q_dot_new
```

**预期效果**:
- 状态更新顺序正确
- 速度/加速度计算基于一致的状态
- 减少误触发安全限制

---

### ✅ 问题 3: 状态同步顺序混乱

**文件**: [scripts/run_real_robot_vist_refactored.py](scripts/run_real_robot_vist_refactored.py#L267-L288)

**问题描述**:
- 插值器和安全控制器的速度状态不一致
- 插值器使用梯形速度曲线，安全控制器使用数值微分
- 导致加速度估计错误，频繁触发限制

**修复内容**:
```python
# 修复前
self.controller.safety_controller.update_actual_command(q_actual)
self.interpolator.q_current = q_actual.copy()

# 修复后
# 先同步插值器
self.interpolator.q_current = q_actual.copy()

# 获取插值器的速度（基于梯形速度曲线）
q_dot_interpolator = self.interpolator.get_current_velocity()

# 更新安全控制器
self.controller.safety_controller.update_actual_command(q_actual)

# 同步安全控制器的速度为插值器的速度
self.controller.safety_controller.q_dot_current = q_dot_interpolator.copy()
```

**预期效果**:
- 插值器和安全控制器的速度状态一致
- 加速度计算准确
- 减少"咣当"现象

---

## 测试计划

### 1. 单元测试

创建测试脚本验证修复：

```python
# tests/test_safe_controller_fixes.py
import numpy as np
from src.control.safe_robot_controller import SafeRobotController
from src.config import get_config

def test_velocity_estimate_not_overwritten():
    """测试卡尔曼滤波速度估计不被覆盖"""
    config = get_config()
    controller = SafeRobotController(config, enable_logging=False)

    # 设置初始状态
    controller.q_current = np.zeros(7)
    controller.q_previous = np.zeros(7)

    # 提供速度估计
    q_target = np.array([0.1] * 7)
    q_dot_estimated = np.array([0.5] * 7)

    q_safe, _ = controller.process_command(q_target, q_dot_estimated)

    # 验证速度没有被覆盖
    assert np.allclose(controller.q_dot_current, q_dot_estimated), \
        f"速度被覆盖！期望 {q_dot_estimated}，实际 {controller.q_dot_current}"

    print("✅ 测试通过：速度估计没有被覆盖")

def test_state_consistency():
    """测试状态更新一致性"""
    config = get_config()
    controller = SafeRobotController(config, enable_logging=False)

    # 初始化
    controller.q_current = np.zeros(7)
    controller.q_previous = np.zeros(7)

    # 第一帧
    q_target1 = np.array([0.1] * 7)
    q_safe1, _ = controller.process_command(q_target1)
    controller.update_actual_command(q_safe1)

    # 记录状态
    q_prev_after_frame1 = controller.q_previous.copy()
    q_curr_after_frame1 = controller.q_current.copy()

    # 第二帧
    q_target2 = np.array([0.2] * 7)
    q_safe2, _ = controller.process_command(q_target2)

    # 验证 q_previous 是上一帧的 q_current
    assert np.allclose(controller.q_previous, q_curr_after_frame1), \
        "q_previous 不等于上一帧的 q_current"

    print("✅ 测试通过：状态更新一致")

if __name__ == "__main__":
    test_velocity_estimate_not_overwritten()
    test_state_consistency()
    print("\n✅ 所有测试通过！")
```

### 2. 集成测试

运行真机控制并观察：

```bash
# 运行真机控制（60秒测试）
python scripts/run_real_robot_vist_refactored.py --duration 60 --countdown 5

# 观察指标：
# 1. 安全限制触发率（应该从100%降低到<10%）
# 2. 控制频率（应该稳定在19-20Hz）
# 3. 跟踪误差（应该减小）
# 4. 是否还有"咣当"现象
```

### 3. 对比实验

```yaml
# 实验1：修复前 vs 修复后
# 记录：
# - 安全限制触发次数
# - 关节振荡幅度
# - 跟踪误差
# - 运动平滑度

# 实验2：卡尔曼 vs 数值微分
velocity_estimation_method: "kalman"  # 然后改为 "numerical"
# 对比速度估计质量
```

---

## 预期改进

根据代码分析，修复后预期：

| 指标 | 修复前 | 修复后（预期） | 改进幅度 |
|------|--------|----------------|----------|
| 安全限制触发率 | 100% (542/542) | <10% | 90%+ |
| 关节振荡幅度 | 高 | 减小50%+ | 50%+ |
| "咣当"现象 | 频繁 | 消失/显著减轻 | - |
| 跟踪误差 | 高 | 减小30%+ | 30%+ |
| 控制频率 | 16.9Hz | 19-20Hz | 稳定性提升 |

---

## 后续工作

### P1 中等问题（建议后续修复）:

1. **优化控制频率稳定性**
   - 测量 `get_state()` 耗时
   - 优化 VIST 求解性能
   - 考虑使用非阻塞状态读取

2. **修复关节锁定状态同步**
   - 锁定到实际位置而不是初始位置
   - 在插值器和安全控制器中也锁定

3. **调整安全限制参数**
   - 先验证修复效果
   - 如果仍然频繁触发，适当放宽限制

4. **动态 dt 适配**
   - 测量实际控制周期
   - 动态更新插值器和安全控制器的 dt

5. **数值微分滤波**
   - 添加低通滤波器
   - 减少噪声影响

---

## 验证清单

修复后，请验证以下内容：

- [ ] 卡尔曼滤波速度估计被正确使用（检查日志）
- [ ] 安全限制触发率显著降低（<10%）
- [ ] 关节振荡幅度减小
- [ ] "咣当"现象消失或显著减轻
- [ ] 跟踪误差减小
- [ ] 控制频率稳定在19-20Hz
- [ ] 运动平滑度提升
- [ ] 没有引入新的问题

---

## 回滚方案

如果修复后出现问题，可以回滚：

```bash
# 查看修改
git diff

# 回滚所有修改
git checkout src/control/safe_robot_controller.py
git checkout scripts/run_real_robot_vist_refactored.py

# 或者回滚到特定提交
git reset --hard <commit-hash>
```

---

**修复完成时间**: 2026-02-22
**下一步**: 运行测试验证修复效果
**负责人**: VIST Project Team