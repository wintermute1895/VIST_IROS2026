# VIST监控指标说明

## 新增卡尔曼滤波核心指标

### 1. prediction_displacement_norm (预测位移范数)

**定义**:
```
prediction_displacement = x̂_{k|k-1} - x̂_{k-1}
```

**物理意义**:
- 卡尔曼滤波器**预测步骤**产生的关节角度变化
- 基于系统动力学模型 `F` 的纯预测，不包含观测信息
- 反映系统的"惯性"或"自然演化"

**计算公式**:
```python
x_pred = F @ self.state  # 状态预测
prediction_displacement = x_pred[:n_joints] - self.state[:n_joints]
prediction_displacement_norm = ||prediction_displacement||₂
```

**正常范围**:
- 取决于运动速度和时间步长 dt
- 静止时应接近 0
- 快速运动时可能达到 0.01-0.1 rad

**异常情况**:
- 突然增大：系统模型预测出现跳变
- 持续很大：速度估计可能不准确

---

### 2. innovation_norm (创新/残差范数)

**定义**:
```
innovation = z - H @ x̂_{k|k-1}
```

**物理意义**:
- **观测值与预测值的差异**
- 卡尔曼滤波器的"惊讶程度"
- 反映模型预测与实际观测的不一致性

**计算公式**:
```python
innovation = z_syn - H_eff @ x_pred
innovation_norm = ||innovation[:n_joints]||₂  # 只取关节部分
```

**正常范围**:
- 理想情况下应该很小（< 0.01 rad）
- 如果观测噪声大，innovation 也会大
- 如果模型不准确，innovation 会持续偏大

**异常情况**:
- **突然增大**:
  - 观测跳变（传感器故障、通信丢包）
  - 模型预测失败（奇异点、动力学突变）
- **持续偏大**:
  - 系统模型 F 不准确
  - 观测噪声 R 设置过小
  - 过程噪声 Q 设置过大

**与其他指标的关系**:
- `innovation_norm` 大 → 卡尔曼增益 K 会增大（如果 R 小）
- `innovation_norm` 大 + `K_norm` 大 → `correction_norm` 会很大

---

### 3. correction_norm (修正位移范数)

**定义**:
```
correction = K @ innovation
```

**物理意义**:
- 卡尔曼滤波器对预测的**修正量**
- 最终状态更新：`x̂_k = x̂_{k|k-1} + correction`
- 反映滤波器对观测的"信任程度"

**计算公式**:
```python
kalman_correction = K @ innovation
correction_norm = ||kalman_correction[:n_joints]||₂
```

**正常范围**:
- 取决于 K 和 innovation 的大小
- 理想情况下应该平滑变化
- 典型值：0.001-0.01 rad

**异常情况**:
- **突然增大**:
  - K 突变（Q 或 P 突变）
  - innovation 突变（观测跳变）
  - 两者同时发生（最危险）
- **持续很大**:
  - 滤波器过度信任观测（K 过大）
  - 观测与模型持续不一致

**与其他指标的关系**:
```
correction_norm ≈ K_norm × innovation_norm
```

---

## 三者的关系与卡尔曼滤波逻辑

### 卡尔曼滤波的两步更新

**预测步骤**:
```
x̂_{k|k-1} = F @ x̂_{k-1}
prediction_displacement = x̂_{k|k-1} - x̂_{k-1}
```

**更新步骤**:
```
innovation = z - H @ x̂_{k|k-1}
K = P_{k|k-1} @ H^T @ inv(S)
correction = K @ innovation
x̂_k = x̂_{k|k-1} + correction
```

### 物理解释

1. **prediction_displacement**: "我认为系统会这样运动"
2. **innovation**: "实际观测与我的预测差了这么多"
3. **correction**: "我决定修正这么多"

### 理想情况

```
prediction_displacement: 小且平滑（模型准确）
innovation: 小且随机（观测准确，模型准确）
correction: 小且平滑（滤波器稳定）
```

### 异常模式

#### 模式1: 观测跳变
```
prediction_displacement: 正常
innovation: 突然增大 ⬆️
correction: 突然增大 ⬆️
```
**原因**: 传感器故障、通信丢包

#### 模式2: 模型失效（奇异点）
```
prediction_displacement: 可能正常或异常
innovation: 增大 ⬆️
K_norm: 突然增大 ⬆️⬆️
correction: 爆炸性增大 ⬆️⬆️⬆️
```
**原因**: Q_norm 突变 → P 膨胀 → K 增大

#### 模式3: 系统不稳定
```
prediction_displacement: 振荡
innovation: 振荡
correction: 振荡且增大
```
**原因**: K 过大，滤波器过度反应

---

## 使用这些指标诊断问题

### 诊断流程

1. **检查 innovation_norm**:
   - 如果持续很大 → 模型或观测有问题
   - 如果突然跳变 → 观测跳变或模型失效

2. **检查 K_norm 和 K_delta_norm**:
   - 如果 K 突变 → 检查 Q_norm 和 P
   - 如果 K 持续很大 → 检查 R 是否过小

3. **检查 correction_norm**:
   - 如果 correction 很大 → 系统在大幅修正预测
   - 如果 correction 振荡 → 系统不稳定

4. **检查三者的比例关系**:
   ```
   correction_norm / innovation_norm ≈ K_norm
   ```
   如果这个比例异常，说明 K 的计算有问题

### 典型问题诊断

#### 问题: 机器人抖动

**检查顺序**:
1. `correction_norm` 是否振荡？
   - 是 → K 过大或 innovation 振荡
2. `innovation_norm` 是否振荡？
   - 是 → 观测噪声大或模型不准
3. `K_norm` 是否过大？
   - 是 → Q 过大或 R 过小

#### 问题: 响应迟钝

**检查顺序**:
1. `correction_norm` 是否很小？
   - 是 → K 过小
2. `K_norm` 是否很小？
   - 是 → R 过大或 Q 过小
3. `innovation_norm` 是否正常？
   - 如果 innovation 大但 correction 小 → K 过小

---

## CSV数据分析示例

```python
import pandas as pd
import numpy as np

df = pd.read_csv('vist_monitor_YYYYMMDD_HHMMSS.csv')

# 1. 检查修正量是否合理
df['correction_innovation_ratio'] = df['correction_norm'] / (df['innovation_norm'] + 1e-10)
print("修正/创新比例统计:")
print(df['correction_innovation_ratio'].describe())

# 2. 检查是否有异常的修正
correction_anomaly = df[df['correction_norm'] > 0.1]
print(f"\n修正量异常(>0.1)的帧数: {len(correction_anomaly)}")

# 3. 检查预测-创新-修正的一致性
df['total_displacement'] = df['prediction_displacement_norm'] + df['correction_norm']
print("\n总位移统计:")
print(df['total_displacement'].describe())

# 4. 检查创新与Q_norm的相关性
correlation = df['innovation_norm'].corr(df['Q_norm'])
print(f"\n创新与Q_norm的相关性: {correlation:.4f}")
```

---

## 总结

这三个新增指标提供了卡尔曼滤波器内部工作机制的完整视图：

- **prediction_displacement**: 模型的预测能力
- **innovation**: 模型与观测的一致性
- **correction**: 滤波器的修正行为

通过分析这三者的关系，可以精确定位VIST算法的问题根源，无论是模型问题、观测问题还是增益调节问题。
