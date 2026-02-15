# 李群上的状态估计：从EKF到IEKF

## 问题：标准卡尔曼滤波不适用于SE(3)

### 为什么标准KF失效？

标准卡尔曼滤波假设状态空间是欧几里得空间 $\mathbb{R}^n$，依赖于：
1. **向量加法**：$\mathbf{x}_1 + \mathbf{x}_2 \in \mathbb{R}^n$
2. **线性插值**：$\mathbf{x} = \alpha \mathbf{x}_1 + (1-\alpha) \mathbf{x}_2$
3. **协方差加法**：$\mathbf{P} = \mathbf{P}_1 + \mathbf{P}_2$

但在 $SE(3)$ 上：
- ❌ 两个变换矩阵不能直接相加：$\mathbf{T}_1 + \mathbf{T}_2 \notin SE(3)$
- ❌ 线性插值没有意义：$\alpha \mathbf{T}_1 + (1-\alpha) \mathbf{T}_2$ 不是刚体变换
- ❌ 协方差矩阵的更新需要在切空间（李代数）上进行

---

## 解决方案1：扩展卡尔曼滤波（EKF）

### 基本思想

在李代数 $\mathfrak{se}(3)$ 上进行线性化，然后映射回李群 $SE(3)$。

### 状态表示

```python
# 李群状态（非线性）
T_k ∈ SE(3)  # 4×4 变换矩阵

# 李代数误差（线性化）
ξ_k ∈ se(3)  # 6×1 Twist向量
```

### 预测步骤

```python
# 1. 李群上的预测
T_k^- = T_{k-1} · exp(ξ_cmd · Δt)

# 2. 协方差预测（在李代数上）
P_k^- = F · P_{k-1} · F^T + Q
```

### 更新步骤

```python
# 1. 观测残差（在李群上计算，映射到李代数）
ξ_err = ln(T_k^- ^{-1} · T_obs)

# 2. 卡尔曼增益（在李代数上）
K = P^- · H^T · (H · P^- · H^T + R)^{-1}

# 3. 状态更新（在李代数上计算，映射回李群）
ξ_update = K · ξ_err
T_k = T_k^- · exp(ξ_update)

# 4. 协方差更新（在李代数上）
P_k = (I - K · H) · P^-
```

### 优点与缺点

**优点**：
- 相对简单，易于实现
- 可以处理非线性系统

**缺点**：
- 线性化误差累积
- 协方差一致性问题（在大角度旋转时）
- 需要手动选择线性化点

---

## 解决方案2：不变扩展卡尔曼滤波（IEKF）⭐

### 核心思想

利用 $SE(3)$ 的李群结构，设计一个对群作用不变的滤波器。

**关键洞察**：机器人的运动具有**左不变性**或**右不变性**
- 左不变：$T_{world} \cdot T_{robot}$（世界坐标系视角）
- 右不变：$T_{robot} \cdot T_{body}$（机器人坐标系视角）

### 右不变IEKF（推荐用于机器人）

#### 状态定义

```python
# 李群状态
X = (T, v, b) ∈ SE(3) × R^3 × R^6
    ↑   ↑   ↑
  位姿 速度 偏差
```

其中：
- $T \in SE(3)$：机器人TCP的位姿
- $v \in \mathbb{R}^3$：机器人坐标系下的速度
- $b \in \mathbb{R}^6$：传感器偏差（可选）

#### 预测步骤（右不变）

```python
# 1. 李群上的预测（右乘）
T_k^- = T_{k-1} · exp(ξ_cmd · Δt)
v_k^- = v_{k-1} + a_cmd · Δt

# 2. 协方差预测（在右不变误差上）
P_k^- = Φ · P_{k-1} · Φ^T + Q
```

其中状态转移矩阵 $\Phi$ 具有特殊结构（利用李群性质）。

#### 更新步骤（右不变）

```python
# 1. 观测残差（在机器人坐标系下）
ξ_err = Ad(T_k^-^{-1}) · ln(T_k^-^{-1} · T_obs)
       ↑
    伴随作用（保持右不变性）

# 2. 卡尔曼增益
K = P^- · H^T · (H · P^- · H^T + R)^{-1}

# 3. 状态更新（右乘）
ξ_update = K · ξ_err
T_k = T_k^- · exp(ξ_update)

# 4. 协方差更新
P_k = (I - K · H) · P^-
```

### IEKF的优势

1. **协方差一致性**：协方差矩阵在群作用下保持一致
2. **减少线性化误差**：利用李群结构，线性化更准确
3. **理论保证**：在特定条件下，IEKF的误差有界

---

## 解决方案3：简化方案（当前VIST可用）

如果暂时不考虑姿态，可以在 $\mathbb{R}^3$ 上使用标准KF，未来再扩展到 $SE(3)$。

### 当前状态空间

```python
# 只考虑位置和速度
x_k = [p_x, p_y, p_z, v_x, v_y, v_z]^T ∈ R^6
```

### 未来扩展路径

**阶段1**（当前）：$\mathbb{R}^3$ 位置 + 速度
```python
x_k ∈ R^6
```

**阶段2**（短期）：$\mathbb{R}^3 \times SO(3)$ 位置 + 姿态（用四元数）
```python
x_k = [p, v, q, ω] ∈ R^{13}
      (位置, 速度, 四元数, 角速度)
```
使用Multiplicative EKF (MEKF) 处理四元数

**阶段3**（长期）：$SE(3)$ 完整李群
```python
x_k = (T, v) ∈ SE(3) × R^6
```
使用IEKF

---

## 实现建议

### 对于当前VIST项目

**推荐**：保持 $\mathbb{R}^3$ 建模，但在理论论文中讨论 $SE(3)$ 扩展

**理由**：
1. 当前任务（USB插入）主要是位置约束，姿态约束较弱
2. 标准KF已经工作良好（100%成功率）
3. 扩展到 $SE(3)$ 需要大量工程工作，但性能提升可能有限

**论文策略**：
- **主体**：基于 $\mathbb{R}^3$ 的VIST框架（已验证）
- **讨论部分**：提出 $SE(3)$ 扩展的理论框架（未来工作）
- **贡献**：证明意图因子的概念可以扩展到李群

### 对于理论扩展

如果要发表理论论文，可以：
1. 在 $SE(3)$ 上形式化问题定义
2. 推导IEKF版本的VIST
3. 在仿真中验证（不需要真实硬件）

---

## 参考文献

1. **Invariant EKF**:
   - Barrau & Bonnabel (2017). "The Invariant Extended Kalman Filter as a Stable Observer"
   - Hartley et al. (2020). "Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation"

2. **李群上的状态估计**:
   - Sola et al. (2018). "A Micro Lie Theory for State Estimation in Robotics"
   - Bloesch et al. (2016). "Iterated Extended Kalman Filter Based Visual-Inertial Odometry"

3. **四元数EKF**:
   - Markley (2003). "Attitude Error Representations for Kalman Filtering"

---

**最后更新**：2026-02-12
**作者**：VIST Research Team
