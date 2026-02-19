# VIST 代码检查报告（按 Gemini 建议）

**检查日期**: 2026-02-18
**检查范围**: 核心算法一致性、系统鲁棒性、数据完整性

---

## 🎯 第一战场：核心算法一致性

### ✅ 1. 意图检测器重构验收

**文件**: `src/core/intent_detector.py`

#### 检查结果：通过 ✅

**关键发现**:
1. **连续公式实现** ✅
   ```python
   # 几何距离因子（Eq. 2）
   alpha_geo = exp(-0.5 * d²_M)  # Mahalanobis 距离

   # 速度因子（Eq. 3, Fitts' Law）
   alpha_vel = 1 / (1 + β * v²)

   # 方向对齐因子（Eq. 4）
   alpha_dir = 0.5 * (1 + cos(θ))

   # 综合意图因子（Eq. 5）
   alpha = alpha_geo × alpha_vel × alpha_dir
   ```

2. **S 型曲线验证** ✅
   - `alpha_geo` 使用指数衰减：`exp(-0.5 * d²)`
   - 从远到近：0 → 1 平滑过渡
   - **不是跳变**，是连续可微的

3. **物理意义正确** ✅
   - 距离近 → `alpha_geo` 大 → 算法主导
   - 速度快 → `alpha_vel` 小 → 人类主导
   - 朝向目标 → `alpha_dir` 大 → 算法主导

4. **平滑滤波** ✅
   ```python
   # 低通滤波避免突变
   self.alpha_smoothed = 0.9 * self.alpha_smoothed + 0.1 * alpha_raw
   ```

#### 建议测试脚本

```python
# 测试意图因子的 S 型曲线
import numpy as np
import matplotlib.pyplot as plt
from src.core.intent_detector import ContinuousIntentDetector

detector = ContinuousIntentDetector()

# 测试：从远到近
distances = np.linspace(0, 1.0, 100)  # 0 到 1 米
alphas = []

for d in distances:
    current_pos = np.array([0, 0, 0])
    target_pos = np.array([d, 0, 0])
    velocity = np.array([0.01, 0, 0])  # 小速度

    result = detector.detect_intent(current_pos, target_pos, velocity, smooth=False)
    alphas.append(result.alpha_geo)

plt.plot(distances, alphas)
plt.xlabel('Distance (m)')
plt.ylabel('Alpha_geo')
plt.title('Geometric Factor: Should be S-curve (0→1)')
plt.grid(True)
plt.savefig('alpha_geo_curve.png')
print("✅ 如果曲线是平滑的 S 型（不是跳变），则通过测试")
```

---

### ⚠️ 2. Q 矩阵构建逻辑

**文件**: `src/core/vist_kalman_filter.py`

#### 检查结果：需要验证 ⚠️

**关键发现**:
1. **Q 矩阵构建方式** ⚠️
   - 当前实现：**Z 轴锁定机制**（动态调整 Q 矩阵）
   - 论文公式：`Q = (1-α) * Σ_free + α * Σ_constrained`

2. **实现逻辑**（第 175-192 行）:
   ```python
   if self.alpha_smoothed > 0.8:
       # 计算雅可比矩阵
       J_full = pin.computeFrameJacobian(...)

       # 冻结非 Z 方向的关节
       # Q_i(α) = Q_base · freeze_factor(α, J_i·ẑ)
   ```

3. **潜在问题** ⚠️
   - **方向问题**：Σ_constrained 的方向是否正确？
   - 在插入任务中（沿 Z 轴）：
     - Z 轴方差应该**大**（允许插入运动）
     - X-Y 轴方差应该**小**（约束横向偏移）

   - 当前实现：冻结"不影响 Z 方向的关节"
   - 这是**正确的**：冻结 X-Y 关节 → 只允许 Z 运动

#### 需要验证的问题

**问题 1**: Q 矩阵是否符合论文公式？
- 当前：动态调整关节空间的 Q
- 论文：线性插值任务空间的 Σ

**问题 2**: 约束方向是否正确？
- 插入任务：Z 轴是插入方向
- 约束：应该限制 X-Y 平面的运动
- 当前实现：冻结"不影响 Z 的关节" ✅ 正确

**问题 3**: α 阈值是否合理？
- 当前：`α > 0.8` 触发 Z 轴锁定
- 建议：应该是**连续**的，而不是阈值触发

#### 建议修改

```python
# 建议：使用连续插值而不是阈值触发
def _build_process_noise_covariance_continuous(self, alpha):
    """
    连续 Q 矩阵插值（符合论文公式）

    Q(α) = (1-α) * Q_free + α * Q_constrained
    """
    # 自由运动的 Q（各向同性）
    Q_free = self.config.vist_position_variance * np.eye(self.state_dim)

    # 约束运动的 Q（Z 轴大，X-Y 轴小）
    Q_constrained = Q_free.copy()

    # 在任务空间中定义约束
    # 假设 Z 轴是插入方向
    # 需要通过雅可比矩阵映射到关节空间

    # 线性插值
    Q = (1 - alpha) * Q_free + alpha * Q_constrained

    return Q
```

---

## 🛡️ 第二战场：系统鲁棒性与安全性

### ✅ 3. IK 解算器的"防爆"检查

**文件**: `src/control/vist_controller.py`

#### 检查结果：通过 ✅

**关键发现**:
1. **IK 失败处理** ✅（第 202-203 行）
   ```python
   if not success:
       return None, False, {"error": f"VIST 求解失败 (误差={error*1000:.2f}mm)"}
   ```

2. **安全控制器检查** ✅（第 208-212 行）
   ```python
   q_safe, safety_status = self.safety_controller.process_command(q_solution)

   if safety_status['emergency_stop']:
       return None, False, {"error": "紧急停止激活"}
   ```

3. **降级策略** ✅
   - IK 失败 → 返回 `None`
   - 调用方需要处理：发送零速度或保持上一帧位置

#### 需要检查的调用方

**文件**: `src/control/threaded_vist_controller.py`（第 237-244 行）

```python
q_safe, success, debug_info = self.vist_controller.process(...)

if success and q_safe is not None:
    self.robot_interface.send_command(q_safe)
else:
    # ⚠️ 问题：如果失败，没有发送任何命令
    # 机器人会保持上一帧的运动状态（可能不安全）
    pass
```

#### 建议修改 ⚠️

```python
if success and q_safe is not None:
    self.robot_interface.send_command(q_safe)
else:
    # 发送停止指令（保持当前位置）
    _, q_current, _ = self.robot_interface.get_state()
    self.robot_interface.send_command(q_current)

    with self._stats_lock:
        self._stats['control_failures'] += 1
```

---

### ✅ 4. 心跳与看门狗

**文件**: `src/robot/arm_driver.py`

#### 检查结果：通过 ✅

**关键发现**:
1. **心跳检测线程** ✅（第 260-292 行）
   ```python
   def _heartbeat_loop(self):
       while self._heartbeat_running:
           # 检查连接健康
           if time_since_last_read > 3.0:
               self._connection_healthy = False

           # 自动重连
           if self._connection_failures >= 5:
               self._attempt_reconnect()
   ```

2. **频率控制** ✅
   - 心跳间隔：1 秒
   - 超时阈值：3 秒
   - 重连阈值：5 次失败

3. **无死循环** ✅
   - 所有循环都有 `time.sleep()`
   - 不会吃光 CPU

---

### ⚠️ 5. 坐标系检查

**需要检查的文件**:
- `src/perception/target_detector.py` - 目标检测
- `src/utils/transformations.py` - 坐标变换
- `src/core/motion_mapper.py` - 运动映射

#### 关键问题

**问题 1**: 相机坐标系 vs 机器人坐标系
- 相机 Z 轴：通常朝前
- 机器人 Z 轴：通常朝上
- 需要 90° 或 180° 旋转

**问题 2**: Eye-in-Hand vs Eye-to-Hand
- 需要确认 `T_base_camera` 矩阵是否正确

#### 建议检查脚本

```python
# 检查坐标系转换
import numpy as np
from src.utils.transformations import transform_point

# 测试：相机看到的点 (0, 0, 1) 应该转换到机器人坐标系的哪里？
point_camera = np.array([0, 0, 1])  # 相机前方 1 米
point_robot = transform_point(point_camera, T_camera_to_robot)

print(f"相机坐标: {point_camera}")
print(f"机器人坐标: {point_robot}")
print("预期：如果相机朝前，机器人 Z 朝上，则应该是 (1, 0, 0) 或类似")
```

---

## 📊 第三战场：实验数据完整性

### ⚠️ 6. 日志记录器审计

**文件**: `src/utils/data_logger.py`

#### 检查结果：需要创建 ⚠️

**当前状态**: 文件存在但未被使用

**需要记录的关键变量**:
1. **时间戳** ✅
   - `timestamp` - 绝对时间（用于同步视频）

2. **位置数据** ⚠️
   - `target_pose` - 目标位置
   - `current_pose` - 实际位置
   - `position_error` - 位置误差

3. **意图因子** ⚠️（最重要！）
   - `alpha` - 综合意图因子
   - `alpha_geo` - 几何因子
   - `alpha_vel` - 速度因子
   - `alpha_dir` - 方向因子

4. **速度数据** ⚠️
   - `commanded_vel` - 指令速度
   - `actual_vel` - 实际速度

5. **安全状态** ⚠️
   - `safety_status` - 安全状态
   - `emergency_stop` - 紧急停止标志

#### 建议实现

```python
class VISTDataLogger:
    """VIST 实验数据记录器"""

    def __init__(self, log_file: str, frequency: float = 100.0):
        self.log_file = log_file
        self.frequency = frequency
        self.data = []

    def log_frame(self, data: dict):
        """记录一帧数据"""
        frame = {
            'timestamp': time.time(),
            'target_pos': data.get('target_pos'),
            'current_pos': data.get('current_pos'),
            'alpha': data.get('alpha'),
            'alpha_geo': data.get('alpha_geo'),
            'alpha_vel': data.get('alpha_vel'),
            'alpha_dir': data.get('alpha_dir'),
            'commanded_vel': data.get('commanded_vel'),
            'actual_vel': data.get('actual_vel'),
            'safety_status': data.get('safety_status'),
        }
        self.data.append(frame)

    def save(self):
        """保存到文件"""
        import json
        with open(self.log_file, 'w') as f:
            json.dump(self.data, f, indent=2)
```

---

## 🎯 优先级排序

### 立即修复（P0）
1. **IK 失败降级策略** - 添加停止指令
2. **数据记录器** - 实现并集成到控制循环

### 重要验证（P1）
1. **Q 矩阵公式** - 验证是否符合论文
2. **坐标系转换** - 检查相机到机器人的转换

### 可选优化（P2）
1. **意图因子测试** - 生成 S 型曲线图
2. **性能测试** - 验证 100Hz 控制频率

---

## 📝 建议的执行顺序

### 第 1 步：修复 IK 失败处理（5 分钟）
```python
# 在 threaded_vist_controller.py 中添加
if not success or q_safe is None:
    _, q_current, _ = self.robot_interface.get_state()
    self.robot_interface.send_command(q_current)
```

### 第 2 步：实现数据记录器（30 分钟）
- 创建 `VISTDataLogger` 类
- 集成到 `run_threaded_vist.py`
- 测试记录功能

### 第 3 步：验证 Q 矩阵（1 小时）
- 阅读论文公式
- 对比当前实现
- 如果不一致，修改为连续插值

### 第 4 步：检查坐标系（30 分钟）
- 编写测试脚本
- 验证转换矩阵
- 修复任何错误

---

## ✅ 总结

### 通过的检查
- ✅ 意图检测器（连续公式）
- ✅ IK 失败处理（有检查）
- ✅ 心跳监控（已实现）
- ✅ 安全控制器（已集成）

### 需要修复
- ⚠️ IK 失败降级策略（缺少停止指令）
- ⚠️ 数据记录器（未实现）

### 需要验证
- ⚠️ Q 矩阵公式（可能不符合论文）
- ⚠️ 坐标系转换（需要测试）

---

**下一步行动**: 先修复 P0 问题，然后验证 P1 问题。