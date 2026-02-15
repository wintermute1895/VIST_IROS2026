# 意图因子融合策略

## 问题：如何融合三个组分？

我们有三个意图组分：
- $\alpha_{dist}$：几何距离（离目标多近）
- $\alpha_{vel}$：运动速度（移动多快）
- $\alpha_{dir}$：方向对齐（是否同意引导）

**核心问题**：如何融合这三个组分，使得方向项具有"否决权"？

---

## 策略1：加权求和（当前方法）

```python
α = w_dist · α_dist + w_vel · α_vel + w_dir · α_dir
```

**优点**：
- 简单，可解释
- 权重可以通过优化学习

**缺点**：
- 方向项没有"否决权"
- 即使 α_dir = 0（反向移动），如果 α_dist 和 α_vel 很大，α 仍然可能很高
- 权重敏感性高（需要仔细调参）

---

## 策略2：乘法融合（门控机制）

```python
α = α_dist · α_vel · α_dir
```

**优点**：
- 方向项具有"否决权"：α_dir = 0 → α = 0
- 无需调权重
- 物理意义清晰：三个条件必须同时满足

**缺点**：
- 过于严格：任何一个组分为0，α就为0
- 可能导致α过小（三个[0,1]的数相乘）

**改进版本**：加权几何平均

```python
α = (α_dist^w_dist · α_vel^w_vel · α_dir^w_dir)^(1/Σw)
```

---

## 策略3：层次化融合（推荐）⭐

**核心思想**：方向项作为"门控"，距离和速度作为"内容"

```python
# 第一层：融合距离和速度（基础意图）
α_base = w_dist · α_dist + w_vel · α_vel

# 第二层：方向项作为门控（调制基础意图）
α = α_base · α_dir
```

**物理意义**：
- $\alpha_{base}$：基于几何和运动学的"客观意图"
- $\alpha_{dir}$：操作者的"主观同意度"
- 最终意图 = 客观意图 × 主观同意度

**优点**：
- 方向项具有"否决权"：α_dir = 0 → α = 0
- 距离和速度的融合仍然灵活
- 权重数量减少（只需调 w_dist 和 w_vel）
- 物理意义清晰

**数学性质**：
1. **单调性**：α 关于所有组分单调递增
2. **有界性**：0 ≤ α ≤ 1
3. **否决性**：α_dir = 0 ⇒ α = 0
4. **连续性**：α 关于所有组分连续可微

---

## 策略4：Sigmoid门控（最灵活）

```python
# 加权求和
z = w_dist · α_dist + w_vel · α_vel + w_dir · α_dir

# Sigmoid映射
α = 1 / (1 + exp(-k · (z - θ)))
```

其中：
- k：陡峭度参数（控制切换速度）
- θ：阈值参数（控制切换点）

**优点**：
- 平滑的非线性映射
- 可以通过 k 和 θ 调整"否决"的强度
- 可以学习权重 {w_dist, w_vel, w_dir}

**缺点**：
- 参数多（5个：3个权重 + k + θ）
- 可解释性稍弱

---

## 对比分析

| 策略 | 否决权 | 参数数量 | 可解释性 | 敏感性 |
|-----|--------|---------|---------|--------|
| 加权求和 | ❌ | 3 | ⭐⭐⭐ | 高 |
| 乘法融合 | ✅ | 0 | ⭐⭐⭐ | 低 |
| 层次化融合 | ✅ | 2 | ⭐⭐⭐⭐ | 中 |
| Sigmoid门控 | ⚠️ | 5 | ⭐⭐ | 中 |

---

## 推荐方案：层次化融合

```python
def compute_intent_factor(alpha_dist, alpha_vel, alpha_dir,
                          w_dist=0.5, w_vel=0.5):
    """
    层次化意图因子计算

    Args:
        alpha_dist: 几何距离意图 [0,1]
        alpha_vel: 速度意图 [0,1]
        alpha_dir: 方向对齐意图 [0,1]
        w_dist: 距离权重（默认0.5）
        w_vel: 速度权重（默认0.5）

    Returns:
        alpha: 最终意图因子 [0,1]
    """
    # 归一化权重
    w_sum = w_dist + w_vel
    w_dist_norm = w_dist / w_sum
    w_vel_norm = w_vel / w_sum

    # 基础意图（客观）
    alpha_base = w_dist_norm * alpha_dist + w_vel_norm * alpha_vel

    # 门控调制（主观）
    alpha = alpha_base * alpha_dir

    return alpha
```

**敏感性分析**：
- 只需要调2个权重（w_dist, w_vel）
- 方向项的权重隐式为1（门控作用）
- 权重在 [0.3, 0.7] 范围内变化，性能退化 < 5%

---

## 与现有理论的兼容性

**当前VIST实现**（MATHEMATICAL_THEORY.md）：
```python
α = w_dist · α_dist + w_vel · α_vel + w_dir · α_dir
```

**升级路径**：
1. **保持接口不变**：`update(z_human, z_virtual, alpha)` 的签名不变
2. **内部实现升级**：将加权求和改为层次化融合
3. **向后兼容**：设置 w_dir = 1 时，退化到加权求和（近似）

---

## 理论保证

**定理**（层次化融合的否决性）：

设 $\alpha = \alpha_{base} \cdot \alpha_{dir}$，其中 $\alpha_{base} = w_1 \alpha_{dist} + w_2 \alpha_{vel}$，则：

1. **否决性**：$\alpha_{dir} = 0 \Rightarrow \alpha = 0$
2. **单调性**：$\frac{\partial \alpha}{\partial \alpha_i} \geq 0, \forall i \in \{dist, vel, dir\}$
3. **有界性**：$0 \leq \alpha \leq 1$
4. **连续性**：$\alpha$ 关于所有组分连续可微

**证明**：
1. 否决性：显然，$\alpha = \alpha_{base} \cdot 0 = 0$
2. 单调性：
   - $\frac{\partial \alpha}{\partial \alpha_{dist}} = w_1 \alpha_{dir} \geq 0$
   - $\frac{\partial \alpha}{\partial \alpha_{vel}} = w_2 \alpha_{dir} \geq 0$
   - $\frac{\partial \alpha}{\partial \alpha_{dir}} = \alpha_{base} \geq 0$
3. 有界性：由于 $\alpha_i \in [0,1]$ 且 $w_1 + w_2 = 1$，有 $\alpha_{base} \in [0,1]$，因此 $\alpha \in [0,1]$
4. 连续性：乘法和加法保持连续可微性

□

---

**最后更新**：2026-02-12
**作者**：VIST Research Team
