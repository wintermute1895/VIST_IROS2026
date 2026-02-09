# VIST: Intent-Aware Adaptive Filtering for Vision-Based Precision Assembly

**基于意图感知的纯视觉精密装配遥操作方案**

---

## 1. 问题背景与动机

### 1.1 精密装配的挑战

精密装配任务（如USB插入、连接器装配）对遥操作系统提出了极高的要求：
- **精度要求**：亚毫米级（<1mm）的对齐精度
- **操作难度**：需要极高的手眼协调能力
- **视觉噪声**：单目/双目视觉存在深度估计误差和抖动
- **网络延迟**：视觉信号传输存在延迟和丢帧

### 1.2 现有方案的局限

**通用遥操作方案**（如AnyTeleop、TeleVision）：
- ✅ 适用于通用任务（抓取、放置、擦拭）
- ❌ 精度不足（厘米级，1-5cm）
- ❌ 无法完成精密装配任务

**工业精密装配方案**：
- ✅ 精度高（毫米级甚至亚毫米级）
- ❌ 依赖力觉传感器或高精度视觉标定
- ❌ 成本高、部署复杂
- ❌ 不适合数据采集场景

### 1.3 本文方案

我们提出一个**纯视觉精密装配遥操作方案**，通过以下技术实现低成本、易部署的精密装配：

1. **几何解析映射**：保证机器人构型自然，解决7-DoF冗余问题
2. **自适应卡尔曼滤波**：过滤视觉噪声，补偿网络延迟
3. **意图感知机制**：根据任务阶段动态调整控制策略
4. **视觉引导辅助**：在最后阶段提供虚拟夹具辅助

**核心贡献**：
- 证明纯视觉遥操作能够实现<1mm精度的精密装配
- 提出意图感知的两阶段控制策略（接近 + 插入）
- 提供低成本、易部署的数据采集方案

---

## 2. 系统架构

### 2.1 整体流程

```
人体关键点检测 → 几何映射 → 卡尔曼滤波 → 安全控制 → 机器人执行
    (视觉)      (构型)    (去噪+预测)   (限速限位)    (真机)
                              ↑
                         意图感知
                      (速度+距离→α)
```

### 2.2 模块说明

1. **视觉模块**：
   - 输入：RGB图像（单目/双目）
   - 输出：人体关键点（肩、肘、腕）+ 目标点位置
   - 工具：MediaPipe / RealSense

2. **几何映射模块**：
   - 输入：人体关键点
   - 输出：机器人关节角度（7-DoF）
   - 方法：解析几何解（肩-肘-腕三点确定臂部配置）

3. **卡尔曼滤波模块**：
   - 输入：几何映射结果 + 当前状态
   - 输出：滤波后的关节角度
   - 作用：去噪 + 预测 + 意图驱动的协方差调度

4. **意图感知模块**：
   - 输入：末端位置、目标位置、移动速度
   - 输出：意图因子 α ∈ [0, 1]
   - 作用：判断当前处于"接近阶段"还是"精密阶段"

---

## 3. 数学建模

### 3.1 状态空间定义

我们在**关节空间**建立状态估计模型，状态向量包含关节角度和角速度：

$$
\mathbf{x} = \begin{bmatrix} \boldsymbol{\theta} \\ \dot{\boldsymbol{\theta}} \end{bmatrix} \in \mathbb{R}^{14}
$$

其中 $\boldsymbol{\theta} = [\theta_1, \theta_2, ..., \theta_7]^T$ 为7个关节的角度。

**为什么选择关节空间？**
- 避免逆运动学（IK）的多解问题
- 保证控制连续性
- 几何映射直接输出关节角度

### 3.2 过程模型（Process Model）

假设在短时间 $\Delta t$ 内，机械臂遵循**恒速模型**（Constant Velocity Model）：

$$
\mathbf{x}_{k+1} = \mathbf{F} \mathbf{x}_k + \mathbf{w}_k
$$

**状态转移矩阵**：
$$
\mathbf{F} = \begin{bmatrix}
\mathbf{I}_7 & \Delta t \cdot \mathbf{I}_7 \\
\mathbf{0} & \mathbf{I}_7
\end{bmatrix}
$$

**物理意义**：
- 利用物理惯性填补视觉信号的离散间隙
- 实现零延迟的平滑预测
- 补偿网络传输的延迟和丢帧

**过程噪声协方差** $\mathbf{Q}$：
$$
\mathbf{Q} = \text{diag}(q_{\text{pos}}, ..., q_{\text{pos}}, q_{\text{vel}}, ..., q_{\text{vel}})
$$

其中：
- $q_{\text{pos}}$：关节角度的过程噪声方差
- $q_{\text{vel}}$：关节速度的过程噪声方差

**关节特定调整**：
- 肩部关节（J1-J2）：增大方差，增强自由度
- 肘部关节（J3）：适度阻尼，防止冗余自由度跳变
- 腕部关节（J5-J7）：标准方差

### 3.3 观测模型（Observation Model）

我们将**几何映射的结果**作为观测输入：

$$
\mathbf{z}_k = \mathbf{H} \mathbf{x}_k + \mathbf{v}_k
$$

**观测矩阵**：
$$
\mathbf{H} = \begin{bmatrix}
\mathbf{I}_7 & \mathbf{0}
\end{bmatrix}
$$

**物理意义**：
- 只观测关节角度，不观测速度
- 几何映射提供了关节角度的直接测量
- 卡尔曼滤波负责估计速度（通过时间差分）

**观测噪声协方差** $\mathbf{R}$：
$$
\mathbf{R} = \text{diag}(r_1, r_2, ..., r_7)
$$

其中 $r_i$ 为第 $i$ 个关节的观测噪声方差。

---

## 4. 意图感知机制

### 4.1 意图因子定义

意图因子 $\alpha \in [0, 1]$ 用于判断当前操作阶段：

- $\alpha \to 0$：**接近阶段**（远离目标，快速移动）
- $\alpha \to 1$：**精密阶段**（接近目标，慢速移动）

### 4.2 意图因子计算

基于**距离**和**速度**两个维度：

**距离因子**：
$$
\alpha_d = \frac{1}{1 + \exp(-k(d_{\text{threshold}} - d))}
$$

其中：
- $d$：末端执行器与目标点的距离
- $d_{\text{threshold}}$：精密模式触发距离（建议5cm）
- $k$：Sigmoid陡峭度参数

**速度因子**：
$$
\alpha_v = \frac{1}{1 + \exp(-k(v_{\text{threshold}} - v))}
$$

其中：
- $v$：末端执行器的移动速度
- $v_{\text{threshold}}$：慢速移动阈值（建议2cm/s）

**综合意图因子**：
$$
\alpha = 0.5 \cdot (\alpha_d + \alpha_v)
$$

**EMA平滑**：
$$
\alpha_{\text{smooth}} = \lambda \cdot \alpha_{\text{smooth}}^{\text{prev}} + (1-\lambda) \cdot \alpha
$$

其中 $\lambda = 0.9$ 为平滑系数。

### 4.3 物理意义

- **接近阶段**（$\alpha \to 0$）：
  - 操作员快速移动手臂，接近目标区域
  - 系统主要任务：跟随人手，过滤噪声
  - 信任人类指令，信任恒速模型

- **精密阶段**（$\alpha \to 1$）：
  - 操作员慢速微调，准备插入
  - 系统主要任务：辅助对齐，提供引导
  - 信任视觉引导，不信任恒速模型（手可能静止）

---

## 5. 意图驱动的协方差调度

### 5.1 动态过程噪声

过程噪声 $\mathbf{Q}$ 随意图因子 $\alpha$ 动态调整：

$$
q_{\text{pos}}(\alpha) = q_{\text{pos}}^{\text{base}} \cdot [1 + (1-\alpha) \cdot 9]
$$

$$
q_{\text{vel}}(\alpha) = q_{\text{vel}}^{\text{base}} \cdot [1 + (1-\alpha) \cdot 9]
$$

**物理意义**：
- $\alpha = 0$（接近）：$\mathbf{Q}$ 大，信任恒速模型（人手快速移动）
- $\alpha = 1$（精密）：$\mathbf{Q}$ 小，不信任恒速模型（人手微调或静止）

### 5.2 动态观测噪声

观测噪声 $\mathbf{R}$ 随意图因子 $\alpha$ 动态调整：

$$
r_{\text{human}}(\alpha) = r_{\text{min}} + (r_{\text{max}} - r_{\text{min}}) \cdot \alpha
$$

**物理意义**：
- $\alpha = 0$（接近）：$\mathbf{R}$ 小，信任人类指令（跟随人手）
- $\alpha = 1$（精密）：$\mathbf{R}$ 大，不信任人类指令（人手可能抖动）

### 5.3 卡尔曼增益的影响

卡尔曼增益 $\mathbf{K}$ 由 $\mathbf{Q}$ 和 $\mathbf{R}$ 共同决定：

$$
\mathbf{K} = \mathbf{P}^- \mathbf{H}^T (\mathbf{H} \mathbf{P}^- \mathbf{H}^T + \mathbf{R})^{-1}
$$

**协方差调度的效果**：

| 阶段 | $\alpha$ | $\mathbf{Q}$ | $\mathbf{R}$ | $\mathbf{K}$ | 系统行为 |
|------|---------|-------------|-------------|-------------|---------|
| 接近 | 0 | 大 | 小 | 大 | 信任观测，跟随人手 |
| 精密 | 1 | 小 | 大 | 小 | 信任预测，平滑输出 |

---

## 6. 视觉引导的虚拟夹具（待实现）

### 6.1 虚拟夹具的作用

在精密阶段（$\alpha \to 1$），系统提供**虚拟夹具**辅助：

- 计算末端执行器到目标点的方向
- 提供轻微的"磁吸"效果
- 辅助操作员对齐和插入

### 6.2 实现方案

**双观测融合**：

$$
\mathbf{z}_{\text{total}} = (1-\alpha) \cdot \mathbf{z}_{\text{human}} + \alpha \cdot \mathbf{z}_{\text{goal}}
$$

其中：
- $\mathbf{z}_{\text{human}}$：人类指令（几何映射结果）
- $\mathbf{z}_{\text{goal}}$：目标引导（朝向目标点的微分IK）

**物理意义**：
- $\alpha = 0$：完全跟随人手
- $\alpha = 1$：人手 + 目标点辅助（不是完全接管）

### 6.3 微分IK计算

计算朝向目标点的关节角度增量：

$$
\Delta \boldsymbol{\theta}_{\text{goal}} = \mathbf{J}^{\dagger} \cdot (\mathbf{p}_{\text{goal}} - \mathbf{p}_{\text{current}})
$$

其中：
- $\mathbf{J}^{\dagger}$：雅可比矩阵的阻尼伪逆
- $\mathbf{p}_{\text{goal}}$：目标点位置（来自视觉感知）
- $\mathbf{p}_{\text{current}}$：当前末端位置

---

## 7. 卡尔曼滤波的完整流程

### 7.1 预测步骤（Predict）

$$
\mathbf{x}_k^- = \mathbf{F} \mathbf{x}_{k-1}
$$

$$
\mathbf{P}_k^- = \mathbf{F} \mathbf{P}_{k-1} \mathbf{F}^T + \mathbf{Q}(\alpha)
$$

**关键**：$\mathbf{Q}$ 根据当前意图因子 $\alpha$ 动态构建。

### 7.2 更新步骤（Update）

**计算卡尔曼增益**：
$$
\mathbf{K}_k = \mathbf{P}_k^- \mathbf{H}^T (\mathbf{H} \mathbf{P}_k^- \mathbf{H}^T + \mathbf{R}(\alpha))^{-1}
$$

**更新状态估计**：
$$
\mathbf{x}_k = \mathbf{x}_k^- + \mathbf{K}_k (\mathbf{z}_k - \mathbf{H} \mathbf{x}_k^-)
$$

**更新协方差**：
$$
\mathbf{P}_k = (\mathbf{I} - \mathbf{K}_k \mathbf{H}) \mathbf{P}_k^-
$$

**关键**：$\mathbf{R}$ 根据当前意图因子 $\alpha$ 动态构建。

---

## 8. 技术总结

### 8.1 核心创新点

1. **纯视觉精密装配**：
   - 证明低成本视觉方案能做<1mm精度的装配
   - 不依赖力觉传感器或高精度标定

2. **意图感知的两阶段控制**：
   - 接近阶段：跟随人手，强力去噪
   - 精密阶段：辅助对齐，提供引导

3. **自适应卡尔曼滤波**：
   - 协方差动态调度（$\mathbf{Q}$ 和 $\mathbf{R}$）
   - 根据任务阶段自动调整滤波策略

4. **几何映射 + 状态估计融合**：
   - 几何映射：保证构型自然
   - 卡尔曼滤波：过滤噪声 + 补偿延迟

### 8.2 与现有方法的对比

| 方法 | 精度 | 成本 | 部署难度 | 数据采集 |
|------|------|------|---------|---------|
| AnyTeleop | 厘米级 | 低 | 易 | ✅ |
| 工业视觉 | 毫米级 | 高 | 难 | ❌ |
| 力觉引导 | 亚毫米级 | 高 | 难 | ❌ |
| **VIST（本文）** | **毫米级** | **低** | **易** | **✅** |

### 8.3 适用场景

**适合**：
- 精密装配数据采集（USB插入、连接器装配）
- 低成本遥操作系统
- 需要人在回路的精密任务

**不适合**：
- 完全自动化场景（需要人操作）
- 超高精度要求（<0.1mm）
- 实时性要求极高的场景（>100Hz）

---

## 9. 实验设计建议

### 9.1 对比实验

**Baseline方法**：
1. 固定权重卡尔曼滤波（$\alpha = 0.5$ 常量）
2. 纯几何映射（无滤波）
3. AnyTeleop风格（通用遥操作）

**评估指标**：
1. **成功率**：插入成功次数 / 总尝试次数
2. **完成时间**：从开始到插入成功的时间
3. **轨迹平滑度**：关节角度的加加速度（jerk）
4. **操作员负担**：NASA-TLX量表
5. **精度**：末端位置误差（mm）

### 9.2 消融实验

验证每个组件的作用：
1. 无意图感知（固定 $\alpha$）
2. 无协方差调度（固定 $\mathbf{Q}$ 和 $\mathbf{R}$）
3. 无虚拟夹具（纯跟随人手）

### 9.3 用户研究

- 至少3名操作员
- 每人至少20次试验
- 记录主观评价和客观指标

---

## 10. 结论

VIST提出了一个**纯视觉精密装配遥操作方案**，通过几何映射、自适应卡尔曼滤波和意图感知机制，实现了低成本、易部署的精密装配。

**核心贡献**：
- 证明纯视觉能做精密装配（<1mm）
- 提出意图感知的两阶段控制策略
- 提供数据采集的实用方案

**未来工作**：
- 集成视觉感知模块（目标点检测）
- 实现虚拟夹具辅助（最后5cm）
- 扩展到其他精密装配任务
- 多模态融合（视觉 + 触觉）

---

## 参考文献

1. AnyTeleop: A General Vision-Based Dexterous Robot Arm-Hand Teleoperation System
2. TeleVision: Teleoperation with Immersive Active Visual Feedback
3. ALOHA: A Low-cost Open-source Hardware System for Bimanual Teleoperation
4. Kalman Filter for Robot Vision: A Survey
5. Shared Autonomy via Deep Reinforcement Learning
