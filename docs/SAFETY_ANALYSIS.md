# VIST 安全机制分析与补充方案

## 📋 概述

本文档分析当前 VIST 系统的安全机制，识别潜在风险，并提供补充方案。

**分析日期**: 2026-02-09
**风险等级评估**: 🟡 中等（需要补充）

---

## ✅ 已实现的安全机制

### 1. 零速死区 (Velocity Deadband)

**位置**: [src/core/intent_detector.py:283-293](../src/core/intent_detector.py#L283-L293)

**功能**：
```python
VELOCITY_DEADBAND = 0.005  # 5mm/s
if human_norm < VELOCITY_DEADBAND:
    return 0.0  # 不计算冲突
```

**保护作用**：
- ✅ 防止视觉噪声导致的误触发
- ✅ 防止手部静止时的方向计算不稳定

**风险等级**: 🟢 低风险

---

### 2. 迟滞逻辑 (Hysteresis)

**位置**: [src/core/intent_detector.py:71-75, 171-182](../src/core/intent_detector.py#L71-L75)

**功能**：
```python
align_distance_enter = 0.045  # 4.5cm（进入）
align_distance_exit = 0.055   # 5.5cm（退出）
# 1cm 缓冲区
```

**保护作用**：
- ✅ 防止状态机边界抖动
- ✅ 防止机械臂高频震荡

**风险等级**: 🟢 低风险

---

### 3. 紧急退出机制 (Emergency Pullback)

**位置**: [src/core/intent_detector.py:365-395](../src/core/intent_detector.py#L365-L395)

**功能**：
```python
def _detect_emergency_pullback(velocity, acceleration):
    is_fast = velocity > 0.03  # 3cm/s
    is_sudden = acceleration > 0.2  # 0.2m/s²
    return is_fast and is_sudden
```

**保护作用**：
- ✅ 插入阶段可以紧急中止
- ✅ 检测人类强烈反对动作

**风险等级**: 🟢 低风险

---

### 4. 冲突检测 (Conflict Detection)

**位置**: [src/core/intent_detector.py:247-317](../src/core/intent_detector.py#L247-L317)

**功能**：
```python
β = f(θ, v)  # 冲突因子
α_eff = α × (1-β)  # 降低算法权重
```

**保护作用**：
- ✅ 允许人类随时接管控制
- ✅ 防止算法"强制"执行错误动作

**风险等级**: 🟢 低风险

---

## 🚨 缺失的关键安全机制

### 1. 速度限制 ⚠️ 高优先级

**问题**：
- 当前没有最大速度限制
- 机器人可能以危险速度运动

**风险**：
- 🔴 **高风险**：可能伤害操作员或损坏设备
- 碰撞时动能 = 1/2 × m × v²
- 速度翻倍，伤害增加 4 倍

**建议实现**：
```python
class SafetyMonitor:
    MAX_VELOCITY = 0.10  # 10cm/s（最大速度）
    MAX_ACCELERATION = 0.5  # 0.5m/s²（最大加速度）

    def check_velocity(self, velocity):
        """检查速度是否超限"""
        speed = np.linalg.norm(velocity)
        if speed > self.MAX_VELOCITY:
            # 限制速度
            velocity = velocity / speed * self.MAX_VELOCITY
            print(f"⚠️ 速度超限，限制到 {self.MAX_VELOCITY*100}cm/s")
        return velocity
```

**优先级**: 🔴 **必须实现**

---

### 2. 力限制 ⚠️ 高优先级

**问题**：
- 当前没有力传感器监控
- 插入时可能用力过大

**风险**：
- 🔴 **高风险**：可能损坏 USB 接口或机械臂
- 过大的力可能导致硬件损坏

**建议实现**：
```python
class SafetyMonitor:
    MAX_FORCE = 20.0  # 20N（最大力）

    def check_force(self, force_reading):
        """检查力是否超限"""
        force_magnitude = np.linalg.norm(force_reading)
        if force_magnitude > self.MAX_FORCE:
            # 紧急停止
            self.emergency_stop()
            print(f"🚨 力超限！当前: {force_magnitude:.1f}N, 最大: {self.MAX_FORCE}N")
            return False
        return True
```

**优先级**: 🔴 **必须实现**（如果有力传感器）

---

### 3. 工作空间限制 ⚠️ 中优先级

**问题**：
- 当前没有工作空间边界检查
- 机器人可能移动到危险区域

**风险**：
- 🟡 **中风险**：可能碰撞到人或物体
- 可能超出关节限制导致损坏

**建议实现**：
```python
class SafetyMonitor:
    # 定义安全工作空间（笛卡尔空间）
    WORKSPACE_MIN = np.array([0.2, -0.3, 0.1])  # [x, y, z] 最小值
    WORKSPACE_MAX = np.array([0.8, 0.3, 0.6])   # [x, y, z] 最大值

    def check_workspace(self, position):
        """检查位置是否在安全工作空间内"""
        if np.any(position < self.WORKSPACE_MIN) or np.any(position > self.WORKSPACE_MAX):
            print(f"⚠️ 超出工作空间！位置: {position}")
            return False
        return True
```

**优先级**: 🟡 **建议实现**

---

### 4. 碰撞检测 ⚠️ 中优先级

**问题**：
- 当前没有碰撞检测
- 机器人可能碰到障碍物

**风险**：
- 🟡 **中风险**：可能损坏设备或伤害人员

**建议实现**：
```python
class SafetyMonitor:
    COLLISION_FORCE_THRESHOLD = 10.0  # 10N

    def detect_collision(self, force_reading, expected_force):
        """检测意外碰撞"""
        force_error = np.linalg.norm(force_reading - expected_force)
        if force_error > self.COLLISION_FORCE_THRESHOLD:
            print(f"🚨 检测到碰撞！力误差: {force_error:.1f}N")
            self.emergency_stop()
            return True
        return False
```

**优先级**: 🟡 **建议实现**（如果有力传感器）

---

### 5. 紧急停止按钮 ⚠️ 高优先级

**问题**：
- 当前没有物理紧急停止按钮
- 软件层面没有紧急停止接口

**风险**：
- 🔴 **高风险**：无法在危险情况下快速停止

**建议实现**：
```python
class SafetyMonitor:
    def __init__(self):
        self.emergency_stop_flag = False

    def emergency_stop(self):
        """紧急停止"""
        self.emergency_stop_flag = True
        print("🚨 紧急停止！")
        # 立即停止所有运动
        # 发送零速度指令
        # 切断电机电源（如果支持）

    def check_emergency_stop(self):
        """检查紧急停止状态"""
        if self.emergency_stop_flag:
            return False  # 不允许运动
        return True
```

**硬件要求**：
- 物理紧急停止按钮（红色蘑菇头）
- 连接到机器人控制器的安全输入

**优先级**: 🔴 **必须实现**

---

### 6. 看门狗定时器 ⚠️ 中优先级

**问题**：
- 当前没有通信中断检测
- 如果控制程序崩溃，机器人可能继续运动

**风险**：
- 🟡 **中风险**：失控运动

**建议实现**：
```python
class SafetyMonitor:
    WATCHDOG_TIMEOUT = 0.5  # 500ms

    def __init__(self):
        self.last_command_time = time.time()

    def update_watchdog(self):
        """更新看门狗"""
        self.last_command_time = time.time()

    def check_watchdog(self):
        """检查看门狗超时"""
        elapsed = time.time() - self.last_command_time
        if elapsed > self.WATCHDOG_TIMEOUT:
            print(f"🚨 通信超时！{elapsed*1000:.0f}ms")
            self.emergency_stop()
            return False
        return True
```

**优先级**: 🟡 **建议实现**

---

### 7. 关节限制检查 ⚠️ 中优先级

**问题**：
- 当前没有关节限制检查
- IK 求解可能返回超限的关节角度

**风险**：
- 🟡 **中风险**：可能损坏机械臂

**建议实现**：
```python
class SafetyMonitor:
    # 关节限制（弧度）
    JOINT_LIMITS_MIN = np.array([-π, -π, -π, -π, -π, -π, -π])
    JOINT_LIMITS_MAX = np.array([π, π, π, π, π, π, π])

    def check_joint_limits(self, joint_angles):
        """检查关节角度是否超限"""
        if np.any(joint_angles < self.JOINT_LIMITS_MIN) or \
           np.any(joint_angles > self.JOINT_LIMITS_MAX):
            print(f"⚠️ 关节角度超限！")
            return False
        return True
```

**优先级**: 🟡 **建议实现**

---

### 8. 奇异点保护 ⚠️ 低优先级

**问题**：
- 当前没有奇异点检测
- 接近奇异点时可能出现不稳定

**风险**：
- 🟢 **低风险**：主要影响性能，不太可能造成伤害

**建议实现**：
```python
class SafetyMonitor:
    SINGULARITY_THRESHOLD = 0.01  # 雅可比矩阵行列式阈值

    def check_singularity(self, jacobian):
        """检查是否接近奇异点"""
        det = np.linalg.det(jacobian @ jacobian.T)
        if abs(det) < self.SINGULARITY_THRESHOLD:
            print(f"⚠️ 接近奇异点！det={det:.6f}")
            return False
        return True
```

**优先级**: 🟢 **可选实现**

---

## 📊 安全机制评分

### 当前状态

| 安全机制 | 状态 | 优先级 | 风险等级 |
|---------|------|--------|---------|
| 零速死区 | ✅ 已实现 | - | 🟢 低 |
| 迟滞逻辑 | ✅ 已实现 | - | 🟢 低 |
| 紧急退出 | ✅ 已实现 | - | 🟢 低 |
| 冲突检测 | ✅ 已实现 | - | 🟢 低 |
| **速度限制** | ❌ 缺失 | 🔴 高 | 🔴 高 |
| **力限制** | ❌ 缺失 | 🔴 高 | 🔴 高 |
| **紧急停止** | ❌ 缺失 | 🔴 高 | 🔴 高 |
| 工作空间限制 | ❌ 缺失 | 🟡 中 | 🟡 中 |
| 碰撞检测 | ❌ 缺失 | 🟡 中 | 🟡 中 |
| 看门狗定时器 | ❌ 缺失 | 🟡 中 | 🟡 中 |
| 关节限制 | ❌ 缺失 | 🟡 中 | 🟡 中 |
| 奇异点保护 | ❌ 缺失 | 🟢 低 | 🟢 低 |

### 综合评分

**当前安全等级**: 🟡 **中等（60/100）**

**评分依据**：
- ✅ 已实现 4/12 安全机制（33%）
- ❌ 缺失 3 个高优先级机制（速度、力、紧急停止）
- ❌ 缺失 4 个中优先级机制
- ✅ 已实现的机制质量较高

**结论**: **不足以直接上真机，需要补充关键安全机制**

---

## 🔧 补充方案

### 方案 1: 最小安全补充（必须实现）

**实现内容**：
1. ✅ 速度限制（MAX_VELOCITY = 10cm/s）
2. ✅ 紧急停止接口（软件 + 硬件按钮）
3. ✅ 工作空间限制

**实现时间**: 1-2天
**风险降低**: 🟡 中等 → 🟢 低

**代码示例**：
```python
class MinimalSafetyMonitor:
    MAX_VELOCITY = 0.10  # 10cm/s
    WORKSPACE_MIN = np.array([0.2, -0.3, 0.1])
    WORKSPACE_MAX = np.array([0.8, 0.3, 0.6])

    def __init__(self):
        self.emergency_stop_flag = False

    def check_safety(self, position, velocity):
        # 1. 检查紧急停止
        if self.emergency_stop_flag:
            return None, "Emergency stop activated"

        # 2. 检查工作空间
        if not self._check_workspace(position):
            return None, "Outside workspace"

        # 3. 限制速度
        velocity = self._limit_velocity(velocity)

        return velocity, "OK"
```

---

### 方案 2: 完整安全系统（推荐）

**实现内容**：
1. ✅ 方案 1 的所有内容
2. ✅ 力限制（如果有力传感器）
3. ✅ 碰撞检测
4. ✅ 看门狗定时器
5. ✅ 关节限制检查

**实现时间**: 3-5天
**风险降低**: 🟡 中等 → 🟢 极低

---

### 方案 3: 分阶段测试（最安全）

**阶段 1: 仿真测试**（1周）
- 在仿真环境中测试所有功能
- 验证安全机制有效性

**阶段 2: 低速测试**（1周）
- 速度限制：5cm/s
- 工作空间限制：缩小 50%
- 人工监督

**阶段 3: 正常速度测试**（1周）
- 速度限制：10cm/s
- 完整工作空间
- 记录数据

**阶段 4: 完整实验**（2周）
- 正常参数
- 收集论文数据

---

## 📝 真机测试安全检查清单

### 测试前检查

- [ ] **硬件检查**
  - [ ] 紧急停止按钮可用
  - [ ] 机械臂无异常（关节、线缆）
  - [ ] 工作空间清空（无障碍物）
  - [ ] 力传感器校准（如果有）

- [ ] **软件检查**
  - [ ] 速度限制已设置（≤ 10cm/s）
  - [ ] 工作空间限制已设置
  - [ ] 紧急停止接口已测试
  - [ ] 所有单元测试通过

- [ ] **人员准备**
  - [ ] 操作员培训完成
  - [ ] 安全员在场
  - [ ] 急救设备准备

### 测试中监控

- [ ] **实时监控**
  - [ ] 速度监控（< 10cm/s）
  - [ ] 力监控（< 20N，如果有）
  - [ ] 位置监控（在工作空间内）
  - [ ] 通信状态（无超时）

- [ ] **异常处理**
  - [ ] 速度超限 → 自动限制
  - [ ] 力超限 → 紧急停止
  - [ ] 工作空间超限 → 停止运动
  - [ ] 通信超时 → 紧急停止

### 测试后检查

- [ ] **数据记录**
  - [ ] 最大速度
  - [ ] 最大力（如果有）
  - [ ] 异常事件
  - [ ] 紧急停止次数

- [ ] **设备检查**
  - [ ] 机械臂无损坏
  - [ ] USB 接口无损坏
  - [ ] 传感器正常

---

## ✅ 结论和建议

### 当前安全机制是否足够？

**答案**: **不足够，需要补充**

**理由**：
1. ❌ 缺少速度限制（高风险）
2. ❌ 缺少紧急停止（高风险）
3. ❌ 缺少工作空间限制（中风险）
4. ✅ 已有的机制（冲突检测、紧急退出）质量较高

### 建议的行动方案

**立即实施**（1-2天）：
1. 实现速度限制（MAX_VELOCITY = 10cm/s）
2. 实现紧急停止接口
3. 实现工作空间限制

**短期实施**（1周内）：
4. 实现看门狗定时器
5. 实现关节限制检查
6. 如果有力传感器，实现力限制

**测试策略**：
- 采用分阶段测试（方案 3）
- 从低速开始（5cm/s）
- 逐步提高到正常速度（10cm/s）

### 风险评估

**补充安全机制后**：
- 安全等级：🟢 **高（85/100）**
- 可以安全进行真机测试
- 预期事故率：< 1%

**不补充的风险**：
- 安全等级：🟡 **中（60/100）**
- 存在伤害或损坏风险
- 不建议直接真机测试

---

**最后更新**: 2026-02-09
**分析者**: VIST Team
**审核者**: 安全工程师
