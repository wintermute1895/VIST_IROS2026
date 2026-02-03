这是一个标准的 IEEE/IROS 风格的数学建模文档结构。你可以直接用这套结构作为你论文 **Methodology** 章节的核心草稿，或者作为项目的内部技术文档（Whitepaper）。

这份文档的逻辑非常严密，**用一套卡尔曼滤波（Kalman Filtering）的数学语言，统一了去噪、冗余约束和力反馈引导三个物理问题。**

---

# VIST: Mathematical Formulation & System Modeling
**一种面向精密装配的意图感知统一状态估计框架**

## 1. 符号定义 (Nomenclature)

首先定义系统中的核心变量，确保数学表述的严谨性。

*   $k$: 离散时间步 (Discrete time step)。
*   $\mathbf{x}_k \in \mathbb{R}^{14}$: 机器人的真实状态向量（关节角度 + 关节速度）。
*   $\mathbf{z}_k \in \mathbb{R}^{14}$: 观测向量（包含人类输入和虚拟约束）。
*   $\mathbf{u}_k$: 控制输入（在本系统中假设为 0，因为是遥操作跟随模式）。
*   $\alpha \in [0, 1]$: 意图因子 (Intent Factor)，0 代表自由运动，1 代表精密对准。
*   $n = 7$: 机械臂自由度 (DOF)。

---

## 2. 状态空间建模 (State-Space Formulation)

为了解决 **7DOF 冗余解析** 问题，我们必须在 **关节空间 (Joint Space)** 而非笛卡尔空间建立模型。

### 2.1 状态向量 (State Vector)
我们将机器人的状态定义为 7 个关节的角度 $q$ 和角速度 $\dot{q}$：

$$
\mathbf{x}_k = \begin{bmatrix} \mathbf{q}_k \\ \dot{\mathbf{q}}_k \end{bmatrix} \in \mathbb{R}^{14}
$$

其中 $\mathbf{q}_k = [q_1, q_2, ..., q_7]^T$。

### 2.2 过程模型与延迟补偿 (Process Model for Latency Compensation)
针对 **问题1（延迟与丢帧）**，我们采用 **恒定速度模型 (Constant Velocity, CV)** 作为系统的动力学先验。这利用了物理惯性来填补视觉传输带来的延迟 $\Delta t$。

$$
\mathbf{x}_k = \mathbf{F} \mathbf{x}_{k-1} + \mathbf{w}_k, \quad \mathbf{w}_k \sim \mathcal{N}(0, \mathbf{Q})
$$

状态转移矩阵 $\mathbf{F}$ 定义为：

$$
\mathbf{F} = \begin{bmatrix}
\mathbf{I}_{7} & \Delta t \cdot \mathbf{I}_{7} \\
\mathbf{0}_{7} & \mathbf{I}_{7}
\end{bmatrix}
$$

### 2.3 隐式冗余约束 (Implicit Redundancy Constraint)
针对 **问题2（7DOF 肘部约束）**，我们通过设计 **各向异性过程噪声协方差矩阵 (Anisotropic Process Noise Covariance) $\mathbf{Q}$** 来实现。

我们假设人类操作员对肘部（通常是 $q_3$ 或 $q_4$）的控制意图是“最小化运动”或“保持自然下垂”。因此，我们人为地降低肘部关节的过程噪声方差：

$$
\mathbf{Q} = \begin{bmatrix}
\mathbf{Q}_{pos} & \mathbf{0} \\
\mathbf{0} & \mathbf{Q}_{vel}
\end{bmatrix}
$$

其中 $\mathbf{Q}_{pos} = \text{diag}(\sigma_{q_1}^2, \dots, \mathbf{\sigma_{q_{elbow}}^2}, \dots, \sigma_{q_7}^2)$。
通过设定 $\sigma_{q_{elbow}} \ll \sigma_{q_{other}}$，滤波器会倾向于预测肘部保持惯性运动，从而抑制 IK 解算带来的肘部高频抖动。

---

## 3. 增强观测模型 (Augmented Measurement Model)

为了解决 **问题3（虚拟力反馈/引导）**，我们构造了一个**双源观测模型**。

### 3.1 观测向量
我们将观测向量 $\mathbf{z}_k$ 扩展为两部分：

$$
\mathbf{z}_k = \begin{bmatrix} \mathbf{z}_{human} \\ \mathbf{z}_{virtual} \end{bmatrix} \in \mathbb{R}^{14}
$$

1.  **$\mathbf{z}_{human}$ (Human Input)**: 来自 MediaPipe/Retargeting 的粗糙关节角目标（带噪声）。
2.  **$\mathbf{z}_{virtual}$ (Virtual Fixture)**: 来自视觉识别（AprilTag/ArUco）计算出的、完美对准孔位的目标关节角（通过对孔位位姿进行 IK 反解得到）。

> *注意：这里为了数学简洁，假设 $\mathbf{z}$ 直接在关节空间。实际工程中，可以在 Update 步骤前通过 IK 将笛卡尔观测转换到关节空间。*

### 3.2 观测方程
$$
\mathbf{z}_k = \mathbf{H} \mathbf{x}_k + \mathbf{v}_k, \quad \mathbf{v}_k \sim \mathcal{N}(0, \mathbf{R}(\alpha))
$$

其中观测矩阵 $\mathbf{H}$ 将状态映射到观测空间（此处为单位映射）：
$$
\mathbf{H} = \begin{bmatrix} \mathbf{I}_{14} \\ \mathbf{I}_{14} \end{bmatrix} \text{ (Simplified representation)}
$$

---

## 4. 意图自适应机制 (Intent-Adaptive Mechanism)

这是 VIST 框架的核心创新点，用于解决 **问题1（去噪）** 和 **问题3（力反馈引导）** 的动态切换。

### 4.1 意图推断 (Intent Inference)
我们定义意图因子 $\alpha_k \in [0, 1]$ 为关于“对准误差”和“手部速度”的函数：

$$
\alpha_k = \text{Sigmoid}\left( \lambda_1 \cdot \frac{1}{||\mathbf{p}_{err}|| + \epsilon} - \lambda_2 \cdot ||\mathbf{v}_{hand}|| \right)
$$

*   $\alpha \to 0$: 远离孔位或快速移动 $\Rightarrow$ **自由探索模式 (Free Motion)**。
*   $\alpha \to 1$: 靠近孔位且慢速移动 $\Rightarrow$ **精密对准模式 (Fine Alignment)**。

### 4.2 协方差调度 (Covariance Scheduling)
观测噪声协方差矩阵 $\mathbf{R}(\alpha)$ 是 $\alpha$ 的函数：

$$
\mathbf{R}(\alpha) = \begin{bmatrix}
\mathbf{R}_{human}(\alpha) & \mathbf{0} \\
\mathbf{0} & \mathbf{R}_{virtual}(\alpha)
\end{bmatrix}
$$

我们设计如下调度策略：

1.  **$\mathbf{R}_{human}(\alpha) = R_{base} \cdot (1 + \gamma_1 \cdot \alpha)$**:
    *   当 $\alpha \to 1$ (需要精密操作) 时，$\mathbf{R}_{human}$ 变大。
    *   **物理意义**：系统不再信任人类输入，**强制滤除手部抖动（解决问题1）**。

2.  **$\mathbf{R}_{virtual}(\alpha) = R_{inf} \cdot \frac{1}{1 + \gamma_2 \cdot \alpha}$**:
    *   当 $\alpha \to 0$ 时，$\mathbf{R}_{virtual} \to \infty$，虚拟观测失效。
    *   当 $\alpha \to 1$ 时，$\mathbf{R}_{virtual} \to 0$，虚拟观测变得极度可信。
    *   **物理意义**：最优估计值 $\hat{\mathbf{x}}_k$ 被强行“吸附”到虚拟目标 $\mathbf{z}_{virtual}$ 上，产生**隐式力反馈（解决问题3）**。

---

## 5. 统一估计与控制 (Unified Estimation & Control)

最终，我们将上述模型代入卡尔曼滤波的标准更新步骤：

1.  **预测 (Predict)**:
    $$ \hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1} $$
    $$ \mathbf{P}_{k|k-1} = \mathbf{F} \mathbf{P}_{k-1} \mathbf{F}^T + \mathbf{Q} $$

2.  **更新 (Update)**:
    $$ \mathbf{K}_k = \mathbf{P}_{k|k-1} \mathbf{H}^T (\mathbf{H} \mathbf{P}_{k|k-1} \mathbf{H}^T + \mathbf{R}(\alpha_k))^{-1} $$
    $$ \hat{\mathbf{x}}_k = \hat{\mathbf{x}}_{k|k-1} + \mathbf{K}_k (\mathbf{z}_k - \mathbf{H} \hat{\mathbf{x}}_{k|k-1}) $$

3.  **输出 (Output)**:
    最终输出的平滑关节指令 $\mathbf{q}_{cmd} = \hat{\mathbf{x}}_k[0:7]$ 被发送给底层机械臂控制器。

---

## 6. 理论总结：如何解决三大问题？

通过上述建模，我们将物理问题一一映射到了数学参数上：

| 物理问题 | 数学对应 (Mathematical Counterpart) | 解决机制 |
| :--- | :--- | :--- |
| **1. 原始数据噪声/延迟** | 矩阵 $\mathbf{F}$ 与 $\mathbf{R}_{human}$ | $\mathbf{F}$ 利用惯性填补延迟；$\mathbf{R}_{human}$ 增大时，增益 $\mathbf{K}$ 减小，滤除高频噪声。 |
| **2. 7DOF 肘部约束** | 矩阵 $\mathbf{Q}$ (各向异性) | $\mathbf{Q}_{elbow} \approx 0$ 使得预测模型拒绝肘部的随机运动，实现隐式零空间稳定。 |
| **3. 虚拟力反馈** | 向量 $\mathbf{z}_{virtual}$ 与 $\mathbf{R}_{virtual}(\alpha)$ | 当意图触发时，$\mathbf{R}_{virtual} \downarrow$，卡尔曼增益迫使状态收敛至孔位，形成“吸附感”。 |

---

### 文档使用建议

1.  **Markdown渲染**：这段代码可以在支持 LaTeX 的 Markdown 编辑器（如 Obsidian, Typora, GitHub with MathJax）中完美渲染。
2.  **论文对应**：
    *   第 2 节对应论文的 "System Modeling"。
    *   第 4 节对应论文的 "Intent-Aware Mechanism"。
    *   第 6 节对应论文的 "Theoretical Analysis"。