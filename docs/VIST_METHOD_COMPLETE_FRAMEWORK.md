# VIST方法论：修正版完整框架

## 摘要

本文档提供VIST（Vision-Integrated State Tracking）的完整方法论框架，整合了关节空间建模、李代数投影、信息融合和意图驱动控制。

**核心创新**：
1. **关节空间状态估计** + **任务空间意图感知**
2. **李代数投影**实现流形约束
3. **信息滤波器**融合多源观测
4. **意图因子**动态调制协方差

---

## Part 1: 问题定义

### 1.1 任务描述

**目标**：使用低成本硬件（$500）实现高精度（<1mm）的遥操作精密装配。

**典型任务**：USB插入（孔轴装配）
- 初始状态：USB被抓取，距离目标孔10-30cm
- 目标状态：USB插入孔内，深度15mm
- 约束：径向误差<0.5mm，倾斜角<5°

### 1.2 系统组成

**硬件**：
- 7自由度机械臂（LinkerArm）
- 深度相机A（MediaPipe手部跟踪）
- 深度相机B（目标检测）
- 灵巧手（3指，用作夹爪）

**软件**：
- 仿生运动学映射（4+3解析解）
- 视觉目标检测（YOLOv8 + PnP）
- VIST卡尔曼滤波器
- 意图因子计算

### 1.3 核心挑战

1. **多源信息冲突**：人类指令 vs 视觉引导
2. **TCP不确定性**：抓取随机性导致2-8mm偏差
3. **流形切换**：从自由运动到约束运动
4. **实时性**：500Hz控制频率

---

## Part 2: 状态空间建模

### 2.1 关节空间状态

**状态向量**：
$$\mathbf{x}_k = \begin{bmatrix} \mathbf{q}_k \\ \dot{\mathbf{q}}_k \end{bmatrix} \in \mathbb{R}^{14}$$

其中：
- $\mathbf{q}_k \in \mathbb{R}^7$：关节角度
- $\dot{\mathbf{q}}_k \in \mathbb{R}^7$：关节角速度

**状态转移**（恒速模型）：
$$\mathbf{x}_k = \mathbf{F} \mathbf{x}_{k-1} + \mathbf{w}_k$$

$$\mathbf{F} = \begin{bmatrix} \mathbf{I}_7 & \Delta t \cdot \mathbf{I}_7 \\ \mathbf{0}_7 & \mathbf{I}_7 \end{bmatrix}, \quad \mathbf{w}_k \sim \mathcal{N}(0, \mathbf{Q}_k(\alpha))$$

**过程噪声**：通过李代数投影计算（见2.4节）

### 2.2 任务空间观测

**观测向量**（任务空间）：
- 人类指令：$\mathbf{z}_{h,task} \in \mathbb{R}^3$（TCP位置）
- 视觉引导：$\mathbf{z}_{v,task} \in \mathbb{R}^3$（目标位置）

**观测方程**（非线性）：
$$\mathbf{z}_{task} = h(\mathbf{q}) + \mathbf{v} = \text{FK}(\mathbf{q}) + \mathbf{v}$$

其中 $\text{FK}(\cdot)$ 是正运动学函数。

**线性化**（EKF）：
$$\mathbf{H}_k = \frac{\partial \text{FK}}{\partial \mathbf{q}} \bigg|_{\mathbf{q}_{pred}} = \mathbf{J}(\mathbf{q}_{pred}) \in \mathbb{R}^{3 \times 7}$$

其中 $\mathbf{J}(\mathbf{q})$ 是雅可比矩阵。

### 2.3 为什么选择关节空间？

**优点**：
1. **线性动力学**：状态转移是线性的（恒速模型）
2. **直接控制**：机器人底层接受关节角度指令
3. **约束自然**：关节限位、奇异点在关节空间更容易处理
4. **计算效率**：避免李群上的复杂运算

**缺点**：
1. **观测非线性**：需要EKF处理FK的非线性
2. **意图不直观**：意图因子在任务空间定义，需要映射

**权衡**：优点远大于缺点，关节空间是正确选择。

---

## Part 3: 意图驱动的协方差调度

### 3.1 意图因子计算

**三组分设计**：

1. **距离组分**（几何意图）：
$$\alpha_{dist} = \exp\left(-\frac{\|\mathbf{p}_{tcp} - \mathbf{p}_{target}\|^2}{2\sigma_d^2}\right)$$

2. **速度组分**（运动学意图）：
$$\alpha_{vel} = \frac{1}{1 + \beta_v \|\mathbf{v}_{tcp}\|}$$

3. **方向组分**（对齐意图）：
$$\alpha_{dir} = \frac{1}{2}\left(1 + \frac{\mathbf{v}_{tcp} \cdot (\mathbf{p}_{target} - \mathbf{p}_{tcp})}{\|\mathbf{v}_{tcp}\| \cdot \|\mathbf{p}_{target} - \mathbf{p}_{tcp}\|}\right)$$

**层次化融合**（方向项作为门控）：
$$\alpha_{base} = w_{dist} \cdot \alpha_{dist} + w_{vel} \cdot \alpha_{vel}$$
$$\alpha = \alpha_{base} \cdot \alpha_{dir}$$

**参数**：
- $\sigma_d = 0.15$ m（距离衰减尺度）
- $\beta_v = 2.0$（速度衰减系数）
- $w_{dist} = 0.5, w_{vel} = 0.5$（基础权重）

### 3.2 观测噪声调度

**人类指令协方差**（指数增长）：
$$\mathbf{R}_h(\alpha) = R_{base} \cdot e^{\lambda_h \alpha} \cdot \mathbf{I}_3$$

**物理意义**：当 $\alpha \to 1$（精密阶段），人类手部颤抖被视为高频噪声，方差增大，系统强力平滑。

**参数**：
- $R_{base} = 0.001$ m²（基础方差）
- $\lambda_h = 3.0$（增长率）

**视觉引导协方差**（冲突驱动 + 置信度调制）：
$$\mathbf{R}_v(\alpha, \boldsymbol{\delta}, c) = \left[\frac{R_{min}}{(\alpha + \epsilon)(c + \epsilon)} + \lambda_{escape} \cdot \|\boldsymbol{\delta}\|^2\right] \cdot \mathbf{I}_3$$

其中：
- $\boldsymbol{\delta} = \mathbf{z}_{h,task} - \mathbf{z}_{v,task}$：人机冲突向量
- $c(t) \in [0,1]$：置信度状态变量

**物理意义**：
1. **吸附项**：$\frac{R_{min}}{(\alpha + \epsilon)(c + \epsilon)}$
   - $\alpha \to 1, c = 1$：强吸附（方差小）
   - $c \to 0$：失去信任（方差大）

2. **挣脱项**：$\lambda_{escape} \cdot \|\boldsymbol{\delta}\|^2$
   - $\boldsymbol{\delta}$ 大：冲突强，方差增大，系统"变软"

**参数**：
- $R_{min} = 0.0001$ m²（最小方差）
- $\lambda_{escape} = 100$（挣脱增益）
- $\epsilon = 0.01$（数值稳定项）

### 3.3 置信度动态

**微分方程**：
$$\frac{dc}{dt} = \begin{cases}
-\lambda_{decay} \cdot \|\boldsymbol{\delta}\| \cdot c & \text{if } \|\boldsymbol{\delta}\| > \delta_{threshold} \\
\lambda_{recover} \cdot (1 - c) & \text{otherwise}
\end{cases}$$

**物理意义**：
- **衰减**：检测到冲突，快速降低信任
- **恢复**：无冲突时，缓慢恢复信任
- **记忆效应**：$\lambda_{decay} \gg \lambda_{recover}$，防止反复吸附

**参数**：
- $\lambda_{decay} = 5.0$（快速衰减）
- $\lambda_{recover} = 0.5$（缓慢恢复）
- $\delta_{threshold} = 0.005$ m（冲突阈值）

### 3.4 信息融合

**信息滤波器形式**（任务空间）：
$$\mathbf{R}_{eff}^{-1} = \mathbf{R}_h^{-1} + \mathbf{R}_v^{-1}$$
$$\mathbf{z}_{syn,task} = \mathbf{R}_{eff} \left(\mathbf{R}_h^{-1} \mathbf{z}_{h,task} + \mathbf{R}_v^{-1} \mathbf{z}_{v,task}\right)$$

**物理意义**：
- 信息（精度）相加：$I_{eff} = I_h + I_v$
- 高精度观测（小方差）获得更高权重
- 数学上等价于最小方差估计

**数值稳定性**：
$$\mathbf{R}_v^{reg} = \mathbf{R}_v + \epsilon_{reg} \cdot \mathbf{I}, \quad \epsilon_{reg} = 10^{-6}$$

---

## Part 4: 李代数投影与流形约束

### 4.1 任务空间约束定义

**李代数空间** $\mathfrak{se}(3)$：
$$\boldsymbol{\xi} = \begin{bmatrix} \mathbf{v} \\ \boldsymbol{\omega} \end{bmatrix} \in \mathbb{R}^6$$

其中：
- $\mathbf{v} \in \mathbb{R}^3$：平移速度
- $\boldsymbol{\omega} \in \mathbb{R}^3$：旋转速度

**约束协方差矩阵**（孔轴装配）：
$$\mathbf{\Sigma}_{\mathfrak{se}(3)}(\alpha) = \text{diag}(\sigma_x^2, \sigma_y^2, \sigma_z^2, \sigma_{rx}^2, \sigma_{ry}^2, \sigma_{rz}^2)$$

**锁定机制**（当 $\alpha \to 1$）：
$$\sigma_{xy,rot}^2(\alpha) = \frac{\epsilon_{lock}}{1 + \beta_{lock} \cdot \alpha} \to 0$$
$$\sigma_z^2(\alpha) = \sigma_{z,const}$$
$$\sigma_{rz}^2(\alpha) = \sigma_{rz,const}$$

**物理意义**：
- X-Y（径向）：锁定，不允许移动
- Z（轴向）：自由，允许插入
- Rx-Ry（倾斜）：锁定，保持对齐
- Rz（旋转）：自由，允许绕轴旋转

**参数**：
- $\epsilon_{lock} = 10^{-6}$ m²（锁定方差）
- $\beta_{lock} = 10.0$（锁定强度）
- $\sigma_{z,const} = 0.01$ m²（轴向自由度）
- $\sigma_{rz,const} = 0.1$ rad²（旋转自由度）

### 4.2 雅可比投影

**从任务空间到关节空间**：
$$\mathbf{Q}_{constraint}(\alpha) = \mathbf{J}^\dagger(\mathbf{q}) \cdot \mathbf{\Sigma}_{\mathfrak{se}(3)}(\alpha) \cdot (\mathbf{J}^\dagger(\mathbf{q}))^T$$

其中 $\mathbf{J}^\dagger$ 是雅可比伪逆（阻尼最小二乘）：
$$\mathbf{J}^\dagger = \mathbf{J}^T (\mathbf{J}\mathbf{J}^T + \lambda_{damp} \mathbf{I})^{-1}$$

**参数**：
- $\lambda_{damp} = 0.01$（阻尼系数，避免奇异）

**物理意义**：
- 将任务空间的约束（"不能在X-Y移动"）映射到关节空间
- 告诉卡尔曼滤波器："某些关节运动模式是不可能的"

### 4.3 最终过程噪声

$$\mathbf{Q}_k(\alpha) = \mathbf{Q}_{constraint}(\alpha) + \mathbf{Q}_{base}$$

其中 $\mathbf{Q}_{base}$ 是基础过程噪声（考虑模型误差）：
$$\mathbf{Q}_{base} = \text{diag}(q_{pos}^2 \mathbf{I}_7, q_{vel}^2 \mathbf{I}_7)$$

**参数**：
- $q_{pos} = 0.001$ rad²（位置噪声）
- $q_{vel} = 0.01$ rad²/s²（速度噪声）

---

## Part 5: 扩展卡尔曼滤波器

### 5.1 预测步骤

**状态预测**（线性）：
$$\hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1|k-1}$$

**协方差预测**：
$$\mathbf{P}_{k|k-1} = \mathbf{F} \mathbf{P}_{k-1|k-1} \mathbf{F}^T + \mathbf{Q}_k(\alpha)$$

### 5.2 更新步骤

**预测观测**（非线性）：
$$\hat{\mathbf{z}}_{k|k-1} = \text{FK}(\hat{\mathbf{q}}_{k|k-1})$$

**雅可比矩阵**：
$$\mathbf{H}_k = \mathbf{J}(\hat{\mathbf{q}}_{k|k-1}) \in \mathbb{R}^{3 \times 7}$$

**卡尔曼增益**：
$$\mathbf{K}_k = \mathbf{P}_{k|k-1} \mathbf{H}_k^T (\mathbf{H}_k \mathbf{P}_{k|k-1} \mathbf{H}_k^T + \mathbf{R}_{eff})^{-1}$$

**状态更新**：
$$\hat{\mathbf{x}}_{k|k} = \hat{\mathbf{x}}_{k|k-1} + \mathbf{K}_k (\mathbf{z}_{syn,task} - \hat{\mathbf{z}}_{k|k-1})$$

**协方差更新**：
$$\mathbf{P}_{k|k} = (\mathbf{I} - \mathbf{K}_k \mathbf{H}_k) \mathbf{P}_{k|k-1}$$

### 5.3 控制指令生成

**关节空间指令**：
$$\mathbf{q}_{cmd} = \hat{\mathbf{q}}_{k|k}$$

**任务空间验证**（可选）：
$$\mathbf{p}_{cmd} = \text{FK}(\mathbf{q}_{cmd})$$

---

## Part 6: 完整任务流程

### 6.1 阶段1：抓取USB

**输入**：
- MediaPipe检测手部姿态
- 预设抓取序列（3阶段）

**流程**：
1. 检测手部接近USB
2. 触发预抓取姿态
3. 闭合手指（夹爪模式）
4. 提升USB

**输出**：
- USB被抓取
- 默认姿态：垂直向下

**验证**：
```python
tcp_orientation = get_tcp_orientation()
if abs(tcp_orientation.z_axis - [0, 0, -1]) > 0.1:
    trigger_orientation_correction()
```

### 6.2 阶段2：快速移动

**特征**：
- 距离远（>10cm）
- 速度快（>0.2 m/s）
- $\alpha \approx 0.2$

**系统行为**：
- 人类主导（$\mathbf{R}_h$ 小，$\mathbf{R}_v$ 大）
- 无流形约束（$\mathbf{Q}_{constraint}$ 大）
- 跟随人手运动

### 6.3 阶段3：接近与对齐

**特征**：
- 距离中等（1-10cm）
- 速度放慢（<0.1 m/s）
- $\alpha$ 从0.2增加到0.8

**系统行为**：
- 逐渐吸附到目标
- 开始施加流形约束
- 允许挣脱（通过 $\alpha_{dir}$ 或置信度 $c$）

**冲突检测**：
```python
δ = ||z_human - z_virtual||
if δ > δ_threshold:
    c = c · exp(-λ_decay · δ · Δt)  # 降低置信度
    R_virtual ↑  # 方差增大，系统"变软"
```

### 6.4 阶段4：插入（Z轴约束）

**特征**：
- 距离近（<1cm）
- 速度很慢（<0.05 m/s）
- $\alpha \approx 1.0$

**系统行为**：
- 强吸附（$\mathbf{R}_v \to R_{min}$）
- Z轴约束激活（$\sigma_{xy,rot}^2 \to 0$）
- 只能沿Z轴移动

**插入深度控制**：
```python
# 方法1：预设深度
if insertion_depth > target_depth:
    stop_insertion()

# 方法2：虚拟接触力
if ||v_cmd|| > v_threshold and ||v_actual|| < v_threshold:
    contact_detected = True
    stop_insertion()
```

### 6.5 阶段5：松手

**触发条件**：
- 接触检测 AND 手部张开
- OR 插入深度达标
- OR 超时

**流程**：
1. 检测手部张开（MediaPipe）
2. 触发灵巧手松开
3. 任务完成

---

## Part 7: 理论保证

### 7.1 收敛性

**定理1**（状态估计收敛性）：

在以下条件下，EKF估计误差有界：
1. 观测噪声有界：$\|\mathbf{v}_k\| \leq v_{max}$
2. 过程噪声有界：$\|\mathbf{w}_k\| \leq w_{max}$
3. 雅可比矩阵有界：$\|\mathbf{J}(\mathbf{q})\| \leq J_{max}$

则存在常数 $\epsilon_{ss}$，使得：
$$\lim_{k \to \infty} \mathbb{E}[\|\mathbf{x}_k - \hat{\mathbf{x}}_k\|] \leq \epsilon_{ss}$$

### 7.2 防死循环保证

**定理2**（置信度机制的防死循环性）：

设置信度动态如3.3节定义，且 $\lambda_{decay} > 10 \lambda_{recover}$，则：

1. **挣脱保证**：当 $\|\boldsymbol{\delta}\| > \delta_{threshold}$ 持续时间 $t > \tau_{escape}$，有 $c(t) < 0.2$
2. **防重吸附**：即使 $\boldsymbol{\delta} \to 0$，如果 $c < 0.2$，系统不会重新吸附（$\mathbf{R}_v > 5 R_{min}$）
3. **长期稳定**：如果 $\|\boldsymbol{\delta}\| < \delta_{threshold}$ 持续时间 $t > \tau_{recover}$，$c$ 恢复到稳定值

**时间常数**：
- $\tau_{escape} \approx 0.2$ s（快速挣脱）
- $\tau_{recover} \approx 2.0$ s（缓慢恢复）

### 7.3 流形约束的有效性

**定理3**（李代数投影的约束性）：

当 $\alpha \to 1$ 时，李代数投影确保：
$$\|\mathbf{v}_{xy}\| \leq \epsilon_{constraint}$$

其中 $\mathbf{v}_{xy}$ 是TCP在X-Y平面的速度，$\epsilon_{constraint} \approx 0.001$ m/s。

---

## Part 8: 实现细节

### 8.1 计算优化

**雅可比矩阵缓存**：
```python
if ||q_k - q_cached|| < threshold:
    J_k = J_cached  # 重用
else:
    J_k = compute_jacobian(q_k)
    J_cached = J_k
```

**伪逆计算**（阻尼最小二乘）：
```python
J_dagger = J.T @ np.linalg.inv(J @ J.T + λ_damp * I)
```

### 8.2 数值稳定性

**协方差正则化**：
```python
R_v_reg = R_v + ε_reg * I  # ε_reg = 1e-6
P_k = (P_k + P_k.T) / 2  # 保持对称性
P_k = P_k + ε_reg * I  # 保持正定性
```

### 8.3 实时性

**控制频率**：500Hz（2ms周期）

**计算时间预算**：
- 意图因子计算：0.1ms
- 信息融合：0.1ms
- EKF预测：0.2ms
- EKF更新：0.5ms
- 李代数投影：0.3ms
- 总计：1.2ms（留有余量）

---

## Part 9: 与现有理论的联系

### 9.1 与任务空间VIST的关系

**当前VIST**（任务空间）：
- 状态：$\mathbf{x} = [\mathbf{p}, \mathbf{v}]^T \in \mathbb{R}^6$
- 滤波器：线性KF

**新框架**（关节空间）：
- 状态：$\mathbf{x} = [\mathbf{q}, \dot{\mathbf{q}}]^T \in \mathbb{R}^{14}$
- 滤波器：EKF

**关系**：
- 核心思想相同（意图驱动协方差调度）
- 新框架是自然扩展（增加了流形约束）
- 接口兼容（任务空间输入/输出）

### 9.2 与共享自主理论的联系

**贝叶斯冲突检测**：
$$C_{Bayes} = D_{KL}(p(\mathbf{x}|\mathbf{z}_h) \parallel p(\mathbf{x}|\mathbf{z}_v)) \approx \frac{1}{2} \boldsymbol{\delta}^T \mathbf{R}_{eff}^{-1} \boldsymbol{\delta}$$

**控制权分配**：
$$w_v = \frac{R_h}{R_h + R_v}$$

当 $\mathbf{R}_v \to \infty$（冲突或低置信度），$w_v \to 0$（人类主导）。

---

## Part 10: 总结

### 10.1 核心贡献

1. **关节空间 + 任务空间混合建模**：状态在关节空间，意图在任务空间
2. **李代数投影**：优雅地实现流形约束
3. **信息滤波器**：数学严谨的多源融合
4. **置信度机制**：防止死循环，允许挣脱

### 10.2 理论优势

- ✅ 数学严谨（EKF + 信息滤波器）
- ✅ 物理直观（每个组件都有清晰意义）
- ✅ 计算高效（实时性满足）
- ✅ 鲁棒性强（置信度机制）

### 10.3 实施路径

**短期**（2周）：
- 完成任务空间版本的真实机器人实验
- 撰写论文初稿

**中期**（1个月）：
- 形式化关节空间理论
- 在论文中讨论扩展

**长期**（3-6个月）：
- 实现关节空间版本
- 仿真和真实机器人验证

---

**最后更新**：2026-02-12
**作者**：VIST Research Team
**版本**：v3.0（修正版）
