# 流形切换的数学形式化

## 问题定义

在精密装配任务中，机器人TCP的运动可以分为两个阶段：

1. **自由运动阶段**：TCP在 $M_{free}$ 上运动（六自由度）
2. **约束运动阶段**：TCP在 $M_{target}$ 上运动（低维子流形）

**核心问题**：如何检测从 $M_{free}$ 到 $M_{target}$ 的切换时刻？

---

## 数学定义

### 流形定义

**自由流形** $M_{free}$：
```
M_free = SE(3)  # 六自由度刚体运动
```

**目标流形** $M_{target}$（孔轴装配）：
```
M_target = {T ∈ SE(3) | T = T_hole · exp([0, 0, z, 0, 0, 0]^T), z ∈ R}
           ↑
        一维子流形（沿轴线平移）
```

### 流形距离

定义TCP到目标流形的距离：

```python
d(T_tcp, M_target) = min_{T ∈ M_target} ||ln(T_tcp^{-1} · T)||_W
```

其中 $||\cdot||_W$ 是加权范数（见LIE_ALGEBRA_WEIGHT_MATRIX.md）。

---

## 切换检测方法

### 方法1：基于距离阈值（简单）

**判据**：
```python
if d(T_tcp, M_target) < d_threshold:
    state = "constrained"  # 在M_target上
else:
    state = "free"  # 在M_free上
```

**优点**：
- 简单，易于实现
- 计算高效

**缺点**：
- 硬切换，可能导致抖动
- 阈值难以选择

### 方法2：基于意图因子（软切换）⭐

**核心思想**：意图因子 $\alpha$ 本身就是一个软切换信号

```python
# α接近1：操作者意图进入约束流形
# α接近0：操作者意图自由运动

# 控制律的流形插值
x_cmd = (1 - α) · x_free + α · project(x_cmd, M_target)
        ↑                   ↑
    自由运动            约束到目标流形
```

**物理意义**：
- 当 $\alpha \to 1$（靠近目标，慢速，对齐），系统自动将控制投影到 $M_{target}$
- 当 $\alpha \to 0$（远离目标，快速，或反向），系统允许自由运动

**优点**：
- 平滑切换，无抖动
- 无需额外的切换逻辑
- 与意图检测统一

**缺点**：
- 需要定义投影算子 $\text{project}(\cdot, M_{target})$

### 方法3：基于接触力（物理切换）

**判据**：
```python
if ||F_contact|| > F_threshold:
    state = "constrained"  # 检测到接触
else:
    state = "free"
```

**优点**：
- 物理直观
- 适用于有力传感器的系统

**缺点**：
- 需要力传感器（增加成本）
- 接触检测可能滞后

---

## 投影算子的定义

### 孔轴装配的投影

给定当前TCP状态 $T_{tcp}$ 和目标孔的位姿 $T_{hole}$，投影到 $M_{target}$：

```python
def project_to_insertion_manifold(T_tcp, T_hole):
    """
    将TCP投影到插入流形（沿轴线）

    Args:
        T_tcp: 当前TCP位姿 (4×4)
        T_hole: 目标孔位姿 (4×4)

    Returns:
        T_proj: 投影后的位姿 (4×4)
    """
    # 1. 计算TCP在孔坐标系下的位置
    T_rel = T_hole^{-1} · T_tcp

    # 2. 提取相对位置和姿态
    p_rel = T_rel[0:3, 3]  # 相对位置
    R_rel = T_rel[0:3, 0:3]  # 相对姿态

    # 3. 投影位置（只保留Z轴分量）
    p_proj = [0, 0, p_rel[2]]

    # 4. 投影姿态（对齐到孔的姿态）
    R_proj = I  # 或者保留绕Z轴的旋转

    # 5. 构造投影后的相对位姿
    T_proj_rel = [R_proj, p_proj; 0, 1]

    # 6. 转换回世界坐标系
    T_proj = T_hole · T_proj_rel

    return T_proj
```

### 一般化的投影

对于任意目标流形 $M_{target}$，投影算子可以定义为：

```python
project(T, M_target) = argmin_{T' ∈ M_target} ||ln(T^{-1} · T')||_W
```

这是一个优化问题，可以用梯度下降或闭式解（如果流形简单）。

---

## 控制律的流形插值

### 完整的控制流程

```python
def vist_control_with_manifold_switching(z_human, z_virtual, alpha):
    """
    带流形切换的VIST控制

    Args:
        z_human: 人类意图观测（SE(3)）
        z_virtual: 视觉引导观测（SE(3)）
        alpha: 意图因子 [0,1]

    Returns:
        x_cmd: 控制指令（SE(3)）
    """
    # 1. 卡尔曼滤波融合
    x_fused = kalman_filter.update(z_human, z_virtual, alpha)

    # 2. 流形投影（软切换）
    x_proj = project(x_fused, M_target)

    # 3. 意图调制的插值
    x_cmd = exp(ln(x_fused) · (1 - alpha) + ln(x_proj) · alpha)
            ↑                                ↑
        自由运动                        约束运动

    return x_cmd
```

**物理意义**：
- $\alpha = 0$：完全自由运动（$x_{cmd} = x_{fused}$）
- $\alpha = 1$：完全约束到流形（$x_{cmd} = x_{proj}$）
- $0 < \alpha < 1$：在李群上的测地线插值

### 李群上的插值

在 $SE(3)$ 上，两个位姿之间的插值使用测地线：

```python
def interpolate_SE3(T1, T2, alpha):
    """
    SE(3)上的测地线插值

    Args:
        T1, T2: 两个位姿 (4×4)
        alpha: 插值参数 [0,1]

    Returns:
        T_interp: 插值后的位姿 (4×4)
    """
    # 计算相对变换
    T_rel = T1^{-1} · T2

    # 在李代数上线性插值
    xi_rel = ln(T_rel)
    xi_interp = alpha · xi_rel

    # 映射回李群
    T_interp = T1 · exp(xi_interp)

    return T_interp
```

---

## 理论保证

**定理**（流形切换的平滑性）：

设意图因子 $\alpha(t)$ 连续可微，投影算子 $\text{project}(\cdot, M_{target})$ 连续，则控制指令 $x_{cmd}(t)$ 连续可微。

**证明**：
1. 李群上的指数映射 $\exp: \mathfrak{se}(3) \to SE(3)$ 连续可微
2. 李群上的对数映射 $\ln: SE(3) \to \mathfrak{se}(3)$ 连续可微
3. 线性插值 $(1-\alpha) \xi_1 + \alpha \xi_2$ 连续可微
4. 复合函数 $x_{cmd} = \exp((1-\alpha) \ln(x_{fused}) + \alpha \ln(x_{proj}))$ 连续可微

□

**推论**（无抖动切换）：

由于 $x_{cmd}(t)$ 连续可微，机器人的加速度有界，因此不会出现硬切换导致的抖动。

---

## 实验验证设计

### 验证流形切换的有效性

**实验1：自由运动阶段**
- 设置：TCP距离孔 > 10cm
- 预期：$\alpha \approx 0$，系统允许自由运动
- 验证：$||x_{cmd} - x_{fused}|| < \epsilon$

**实验2：接近阶段**
- 设置：TCP距离孔 1-10cm
- 预期：$\alpha$ 从0平滑增加到1
- 验证：$x_{cmd}$ 逐渐向 $M_{target}$ 收敛

**实验3：约束阶段**
- 设置：TCP在孔内（距离 < 1cm）
- 预期：$\alpha \approx 1$，运动约束到 $M_{target}$
- 验证：$d(x_{cmd}, M_{target}) < 1$ mm

**实验4：挣脱测试**
- 设置：TCP在孔内，操作者反向拉动
- 预期：$\alpha_{dir} \to 0$，系统"放手"
- 验证：操作者能够自由移动，无阻力

---

## 与当前VIST的关系

### 当前实现（隐式流形切换）

当前VIST在 $\mathbb{R}^3$ 上工作，没有显式的流形切换，但意图因子 $\alpha$ 已经起到了软切换的作用：

```python
# 当前控制律（简化）
x_cmd = (1 - α) · z_human + α · z_virtual
```

这可以理解为：
- $z_{human}$：自由运动的目标
- $z_{virtual}$：约束到目标点（零维流形）

### 扩展到SE(3)（显式流形切换）

```python
# 扩展控制律
x_cmd = exp((1 - α) · ln(x_fused) + α · ln(project(x_fused, M_target)))
```

这是当前方法的自然推广。

---

## 推荐实现策略

### 短期（当前项目）

**保持隐式切换**：
- 继续使用 $\mathbb{R}^3$ 建模
- 意图因子 $\alpha$ 已经提供了软切换
- 无需显式定义流形

### 中期（理论论文）

**形式化流形切换**：
- 在论文中定义 $M_{free}$ 和 $M_{target}$
- 证明意图因子实现了软切换
- 讨论扩展到其他任务（拧螺丝、平面滑动）

### 长期（通用框架）

**实现显式流形切换**：
- 扩展到 $SE(3)$
- 实现投影算子
- 支持多种任务流形

---

**最后更新**：2026-02-12
**作者**：VIST Research Team
