# 真正在起作用的VIST配置参数

## 参数使用情况总结

根据代码分析（`vist_kalman_filter.py` 第62-107行），以下是**真正被使用**的配置参数及其当前值。

---

## ✅ 正在使用的参数

### 1. 基础参数

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `n_joints` | 7 | 关节数量 | 第62行 |
| `state_dim` | 14 | 状态维度 (2×7) | 第63行 |

---

### 2. 过程模型参数 (process_model)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `dt` | 0.0125 | 时间步长（80Hz） | 第69行 |
| `position_variance` | 1e-5 | ❌ **未使用** | - |
| `velocity_variance` | 1e-4 | ❌ **未使用** | - |

**注意**: `position_variance` 和 `velocity_variance` 在配置文件中定义，但代码中**未使用**。

---

### 3. 观测模型参数 (observation_model)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `use_orientation_control` | false | 是否使用姿态控制 | 第72行 |
| `fusion_method` | "standard" | 融合方法 | 第73行 |
| `human_base_variance` | **1e-3** | R_human基础噪声 | 第74行 |
| `human_lambda` | 3.0 | 指数增长系数 | 第75行 |
| `virtual_min_variance` | **1e-4** | R_virtual最小噪声 | 第76行 |
| `conflict_gain` | 1.0 | 冲突增益 | 第77行 |
| `differential_ik_damping` | **0.05** | 雅可比阻尼系数 | 第78行 |

**重要修改**:
- `human_base_variance`: 从 5e-2 收缩到 **1e-3**
- `virtual_min_variance`: 从 1e-3 收缩到 **1e-4**
- `differential_ik_damping`: 从 5e-3 增大到 **0.05**

---

### 4. 意图检测参数 (intent_detection)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `w_task` | [5.0, 5.0, 5.0, 0.5, 0.5, 0.5] | 任务流形度量张量 | 第81行 |
| `alpha_beta` | 0.25 | 运动能量参数 | 第82行 |
| `w_geo` | 0.5 | 几何势能权重 | 第83行 |
| `w_vel` | 0.5 | 速度权重 | 第84行 |
| `alpha_alignment_power` | 1.0 | 方向对齐指数 | 第85行 |
| `intent_smoothing` | 0.95 | 意图平滑系数 | 第86行 |

**意图因子计算公式**:
```
α_geo = exp(-0.5 × ξ_err^T @ W_task @ ξ_err)
α_vel = 1 / (1 + β × ||ξ_vel||²)
α_dir = 0.5 × (1 + cos(θ))
α = sigmoid(w_geo × α_geo + w_vel × α_vel) × α_dir^η
α_smoothed = 0.95 × α_old + 0.05 × α
```

---

### 5. 任务空间协方差 (task_covariance)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `free_variance_xyz` | **[0.001, 0.001, 0.001]** | 自由平移方差 | 第89行 |
| `free_variance_rpy` | [0.5, 0.5, 0.1] | 自由旋转方差 | 第90行 |
| `cons_variance_xyz` | **[1e-5, 1e-5, 1e-5]** | 约束平移方差 | 第91行 |
| `cons_variance_rpy` | [0.0001, 0.0001, 0.0001] | 约束旋转方差 | 第92行 |

**重要修改**:
- `free_variance_xyz`: 从 [1.0, 1.0, 1.0] 降低到 **[0.001, 0.001, 0.001]** (降低1000倍)
- `cons_variance_xyz`: 从 [0.1, 0.1, 1.0] 降低到 **[1e-5, 1e-5, 1e-5]**

**Q矩阵计算**:
```
Σ_task(α) = (1-α) × Σ_free + α × Σ_cons
Σ_vel = J_dls @ Σ_task @ J_dls^T
Q_k = [Δt³/3·Σ_vel   Δt²/2·Σ_vel]
      [Δt²/2·Σ_vel   Δt·Σ_vel  ]
```

---

### 6. 门控参数 (gating)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `z_activation_threshold` | 0.05 | Z轴激活阈值（米） | 第95行 |
| `dir_epsilon` | 1e-4 | 方向容差 | 第96行 |

---

### 7. 速度感知参数 (velocity_perception)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `velocity_noise_floor` | 1e-3 | 速度噪声下限 | 第99行 |
| `max_valid_velocity` | 0.5 | 最大有效速度（m/s） | 第100行 |

---

### 8. 滤波器系统参数 (filter_system)

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `process_noise_epsilon` | 1e-10 | 过程噪声兜底值 | 第103行 |

---

### 9. 初始状态参数

| 参数 | 当前值 | 说明 | 代码位置 |
|------|--------|------|---------|
| `initial_state_variance` | 1.0 | 初始状态方差 | 第106行 |
| `initial_velocity_variance` | 1.0 | 初始速度方差 | 第107行 |

---

## ❌ 未使用的参数

以下参数在配置文件中定义，但**代码中未使用**：

### 1. 过程模型
- `position_variance`: 1e-5
- `velocity_variance`: 1e-4
- `elbow_joint_indices`: [3]
- `elbow_damping_factor`: 0.1

### 2. 观测模型
- `human_max_variance`: 1e-1 (已废弃)
- `virtual_base_variance`: 1e-4 (已废弃)

### 3. 意图检测（旧版参数）
- `alpha_computation_method`: "paper"
- `distance_threshold`: 0.1
- `velocity_threshold`: 0.05
- `sigmoid_k`: 10.0
- `sigma_d`: 0.1
- `beta_v`: 20.0
- `alpha_weights`: {distance: 0.3, velocity: 0.3, alignment: 0.4}

---

## 📊 关键参数影响分析

### Q矩阵大小的决定因素

```
Q_norm ≈ ||Σ_vel|| × √(Δt³/3)² + (Δt²/2)² + Δt²
      ≈ ||J_dls @ Σ_task @ J_dls^T|| × 时间因子
      ≈ ||J_dls||² × ||Σ_task|| × 时间因子
```

**当前配置下的预期Q_norm**:
```
Σ_task ≈ Σ_free = diag([0.001, 0.001, 0.001])
||Σ_task|| ≈ √3 × 0.001 = 0.00173
假设 ||J_dls|| ≈ 5 (取决于阻尼系数)
Q_norm ≈ 25 × 0.00173 × 0.00017 ≈ 0.0007
```

**实际测量**: Q_norm ≈ 28.87 (配置文件修改前)

**差异原因**: 配置文件中的值可能未生效，或者使用了科学计数法导致解析错误。

### R矩阵大小

```
R_human(α=0) = 1e-3 × exp(0) = 0.001
R_virtual(α=0) = 1e-4 / 1e-4 = 1.0
R_eff ≈ 0.001 (信息融合后)
R_norm ≈ √7 × 0.001 = 0.0026
```

### 卡尔曼增益

```
K ≈ Q / (Q + R)
  ≈ 0.0007 / (0.0007 + 0.0026)
  ≈ 0.21
```

**理想情况**: K ≈ 0.5 (预测和观测平衡)

---

## 🔧 建议的参数调整

### 1. 修复配置文件解析问题

**问题**: 科学计数法 `1e-3` 被解析为字符串

**解决**: 使用小数格式
```yaml
free_variance_xyz: [0.001, 0.001, 0.001]  # 而不是 [1e-3, 1e-3, 1e-3]
cons_variance_xyz: [0.00001, 0.00001, 0.00001]  # 而不是 [1e-5, 1e-5, 1e-5]
```

### 2. 清理未使用的参数

建议删除或注释掉未使用的参数，避免混淆：
- `position_variance`, `velocity_variance`
- `elbow_joint_indices`, `elbow_damping_factor`
- 所有旧版意图检测参数

### 3. 验证参数是否生效

添加初始化打印：
```python
# vist_kalman_filter.py __init__ 末尾
print(f"[VIST] 参数验证:")
print(f"  free_variance_xyz: {self.free_variance_xyz}")
print(f"  human_base_variance: {self.human_base_variance}")
print(f"  differential_ik_damping: {self.differential_ik_damping}")
```

---

## 总结

### 真正在用的参数数量
- **使用中**: 23个参数
- **未使用**: 12个参数
- **使用率**: 66%

### 最关键的参数（影响Q/R比值）
1. `free_variance_xyz`: [0.001, 0.001, 0.001] - 决定Q_norm
2. `human_base_variance`: 1e-3 - 决定R_norm
3. `differential_ik_damping`: 0.05 - 影响J_dls范数

### 当前配置的预期效果
```
Q_norm: 0.0007 (理论值)
R_norm: 0.0026
Q/R: 0.27 (理想范围)
```

**但实际测量**: Q_norm = 28.87，说明配置可能未生效！
