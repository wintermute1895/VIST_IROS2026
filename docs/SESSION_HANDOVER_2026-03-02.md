# 会话交付总结 - 2026-03-02

## 📋 本次会话讨论内容

### 1. VIST 系统架构澄清

用户提出了关于 VIST 卡尔曼滤波器的四个核心问题：



**Q2: α 变化的频率是多少？**
- **80 Hz**（每 12.5ms 更新一次）
- 计算频率 = timer_callback 频率 = `output_freq_hz: 80.0`
- 显示频率 = 2 Hz（每 0.5 秒打印一次，仅用于调试）
- 记录频率 = 80 Hz（每次迭代都写入 CSV）

**Q3: 会不会和人类指令相冲突？**
- ❌ **不会冲突**
- α 是**协同融合权重**，不是覆盖机制
- 通过动态调整观测噪声协方差实现智能协同：
  - α → 0（自由移动）: 信任虚拟引导（平滑去噪）
  - α → 1（精密操作）: 信任人类指令（磁吸引导）

**Q4: 通过什么 topic 发布消息？**
- 输出话题: `/filtered_left_joint_control`
- 额外话题: `/vist_intent_factors`（发布 α 值及其分量）

---


**关键区别**: VIST 是纯关节空间的卡尔曼滤波器，不依赖真机反馈；FSM 需要真机反馈来判断空间位置。

---


**新增功能**：
- α 值实时显示（每 0.5 秒打印一次）
- CSV 数据记录（保存到 `data/alpha_logs/alpha_values_YYYYMMDD_HHMMSS.csv`）
- 分量追踪：α_geo, α_vel, α_dir, 误差距离, 速度大小


**显示格式**:
```
📊 [VIST α值] 迭代=xxx
   α = 0.xxxx | α_smoothed = 0.xxxx
   α_geo = 0.xxxx (误差距离=0.xxm)
   α_vel = 0.xxxx (速度=0.xxm/s)
   α_dir = 0.xxxx (方向对齐)
   state_prior = 0.xxxx | active_gating = 0.xxxx
```

#### 2. `config/system_config.yaml`

**参数调优**（5 处调整，Line 330-347）:
```yaml
# 🔧 调整 1: 降低任务流形权重（增加误差容忍度）
w_task: [5.0, 5.0, 5.0, 0.5, 0.5, 0.5]  # 原值: [10, 10, 10, 1, 1, 1]

# 🔧 调整 2: 降低速度敏感度（增加平滑性）
alpha_beta: 0.5  # 原值: 1.0

# 🔧 调整 3: 调整融合权重（更关注运动状态）
w_geo: 0.3  # 原值: 0.5（降低对位置误差的敏感度）
w_vel: 0.7  # 原值: 0.5（增加对速度的关注）

# 🔧 调整 4: 降低方向对齐指数（线性而非二次方）
alpha_alignment_power: 1.0  # 原值: 2.0

# 🔧 调整 5: 增加意图平滑（更平缓的 α 变化）
intent_smoothing: 0.95  # 原值: 0.9
```

**目的**: 让 VIST 在低成本硬件上表现更柔顺、更平滑，减少抖动。

---

## 📁 配置文件使用逻辑

### 两层配置架构

#### 1️⃣ **baseline_filters_config.yaml** - ROS2 节点参数（主配置）
**优先级**: ⭐⭐⭐ **最高优先级**

**用途**:
- 控制滤波器选择 (`filter_type: 'gello'/'oneeuro'/'vist'/'fsm'/'apf'`)
- ROS2 话题配置
- 控制频率 (`output_freq_hz: 80.0`)
- 各滤波器的简单参数（FSM, One Euro, APF）
- 指向 VIST 详细配置的路径 (`vist_config_path: 'config/system_config.yaml'`)

**加载位置**: `vist_filter_node.py:194-296`

#### 2️⃣ **system_config.yaml** - VIST 算法详细参数（辅助配置）
**优先级**: ⭐⭐ **仅当 `filter_type='vist'` 时使用**

**用途**:
- VIST 卡尔曼滤波器的详细算法参数
- 机器人模型配置（URDF, 关节限位）
- IK 求解器参数
- 意图检测参数（本次修改的部分）

**加载位置**: `vist_filter_node.py:296` → `config_loader.py:15-31`

### 配置加载流程

```
启动 ROS2 节点
    ↓
1. 读取 baseline_filters_config.yaml
   - 加载 filter_type, output_freq_hz, arm_side 等
   - 加载 vist_config_path = 'config/system_config.yaml'
    ↓
2. 如果 filter_type == 'vist'
   - 调用 get_config(vist_config_path)
   - 加载 system_config.yaml 中的 vist_kalman 部分
    ↓
3. 创建滤波器实例 (FilterFactory)
   - VIST 滤波器: 使用 system_config.yaml 的详细参数
   - 其他滤波器: 使用 baseline_filters_config.yaml 的简单参数
```

### 推荐配置策略

| 场景 | 修改文件 | 示例 |
|------|---------|------|
| 切换滤波器算法 | `baseline_filters_config.yaml` | `filter_type: 'vist'` |
| 调整 VIST 算法参数 | `system_config.yaml` | `w_task: [5, 5, 5, 0.5, 0.5, 0.5]` |
| 调整 FSM 结界参数 | `baseline_filters_config.yaml` | `cylinder_radius: 0.29` |
| 调整控制频率 | `baseline_filters_config.yaml` | `output_freq_hz: 80.0` |


---

### 🚨 核心问题剖析：为什么光调 $R$ 不够？

在你总结的第 5 步（噪声调度）中，你只调整了**观测噪声** $R_{human}(\alpha)$ 和 $R_{virtual}(\alpha)$。
*   这只决定了系统是“听人的指令多一点”还是“听虚拟引导力多一点”。
*   如果你只做这一步，当人手剧烈横向抖动时，系统为了抵抗抖动会增大虚拟引导的权重，这在低频硬件上依然会引发“人机对抗”和弹簧震荡。

**VIST 的真正魔法（消除手抖、产生粘滞感）发生在“过程噪声 $Q_k$”上（论文的 Eq. 9 和 Eq. 10）！**
VIST 通过 $\alpha$ 在任务空间（3D笛卡尔空间）构建了一个**“漏斗”**（横向方差极小，纵向方差大），然后通过雅可比伪逆（我们讨论的 DLS）把这个漏斗翻译成关节电机的运动约束 $\Sigma_{vel}$。**这才是“方差坍缩 / 粘滞感”的来源！**

---

### ✅ 修正后的 VIST 算法实现思路（发送给 Claude 的最终版大纲）

#### 核心理念：意图驱动的流形约束卡尔曼滤波
VIST 运作在关节空间，通过意图因子 $\alpha$ **不仅动态调整观测噪声 $R$ 进行控制权仲裁，更关键的是通过雅可比回拉调整过程噪声 $Q_k$ 进行物理防抖（子空间方差坍缩）。**

#### 四层架构（新增了最核心的流形约束层）

```text
┌─────────────────────────────────────┐
│ 1. 意图检测层 (detect_intent)        │
│  输入: 目标位姿、当前影子状态、速度  │
│  逻辑: 包含 Z轴高度阈值门控(2D距离)  │
│  输出: α ∈ [0, 1]                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. 噪声调度层 (Observation Shaping)  │
│  输入: α                             │
│  输出: R_human(α), R_virtual(α)     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. 流形约束层 (Covariance Pull-back) │ 🌟 VIST 的灵魂！
│  输入: α, J_dls (带固定阻尼的雅可比) │
│  逻辑: 构建带有"粘滞感"的 Σ_task(α)   │
│  输出: 过程噪声矩阵 Q_k(α)          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. 卡尔曼更新层 (KF Update)          │
│  输入: z_syn, R_eff, Q_k            │
│  输出: 最优关节角度 q_filtered      │
└─────────────────────────────────────┘
```

#### 核心公式补充（完整的 Eq. 1-10 映射）

```text
【意图计算】
1. 几何势能 (Z轴门控 + 2D加权距离): 
   if Z > threshold: α_geo = 0 
   else: α_geo = exp(-1/2 ξ_err^T W_task ξ_err)
2. 运动能量: α_vel = 1/(1 + β||ξ_vel||²)
3. 方向对齐: α_dir = 1/2(1 + cos(θ))
4. 意图融合: α = σ(w_g·α_geo + w_v·α_vel) · (α_dir)^η

【观测噪声融合 - 软仲裁】
5. R_human(α) = R_base × exp(λα)
6. R_virtual(α) = R_min/(α + ε) + γ_c × conflict

【过程噪声重塑 - 物理防抖与粘滞感】(🌟 必须加给 Claude)
7. 任务空间方差: 
   Σ_task(α) = (1-α)*Σ_free + α*Σ_cons  (注：Σ_cons不能全0，保留横向微小正数实现粘滞感)
8. 阻尼雅可比伪逆: 
   J_dls = J^T (J J^T + λ^2 I)^(-1)
9. 协方差回拉 (Eq. 9): 
   Σ_vel(α) = J_dls * Σ_task(α) * J_dls^T
10. 离散化过程噪声 (Eq. 10): 
    Q_k(α) = 运动学积分(Σ_vel) + ε*I_2n

【卡尔曼更新】
11. x̂_{k|k-1} = F * x̂_{k-1} + w_k
12. K_k = P_k * H^T * (H * P_k * H^T + R_eff)^(-1)
13. x̂_k = x̂_{k|k-1} + K_k * (z_syn - H * x̂_{k|k-1})
```

```

### 物理意义

- **α → 0**（自由移动）：远离目标、快速运动 → 信任虚拟引导（平滑去噪）
- **α → 1**（精密操作）：接近目标、缓慢运动 → 信任人类指令（磁吸引导）

---

## 📊 项目当前状态

### Git 状态

```bash
位于分支: feature/exo-hand-integration
未提交的修改:
  - config/system_config.yaml (VIST 参数调优)
  - ros2_ws/src/core/vist_kalman_filter.py (α 值显示和记录)
```

### 最近的 Commit

```
d79a26b 提交修改vist前的代码
115343c 加入FSM
1c633b1 流程跑通
```

### 数据输出

- α 值 CSV 日志: `data/alpha_logs/alpha_values_YYYYMMDD_HHMMSS.csv`
- 包含字段: timestamp, iteration, alpha, alpha_smoothed, alpha_geo, alpha_vel, alpha_dir, error_distance, velocity_magnitude, state_prior, active_gating

---

## ✅ 已完成的任务

1. ✅ 澄清 VIST 和 FSM 的区别
2. ✅ 回答用户关于 VIST 的四个核心问题
3. ✅ 实现 α 值实时显示和 CSV 记录
4. ✅ 调优 VIST 参数以获得更平滑的行为
5. ✅ 确认配置文件使用逻辑（两层架构）
6. ✅ 确认没有破坏 FSM 相关代码

---



## 📚 关键文件索引

### 核心算法
- `ros2_ws/src/core/vist_kalman_filter.py` - VIST 卡尔曼滤波器
- `ros2_ws/src/core/vitual_fixture_fsm.py` - FSM 虚拟夹具
- `ros2_ws/src/filters.py` - 滤波器策略模式（5 种算法）

### 配置文件
- `config/baseline_filters_config.yaml` - ROS2 节点参数（主配置）
- `config/system_config.yaml` - VIST 详细参数（辅助配置）

### ROS2 节点
- `ros2_ws/src/nodes/vist_filter_node.py` - 滤波器节点
- `ros2_ws/src/config/config_loader.py` - 配置加载器

### 文档
- `docs/WORKFLOW_ANALYSIS.md` - 工作流分析
- `ros2_ws/src/bringup/README.md` - 启动说明

---

## 🎯 总结

本次会话主要完成了：
1. **概念澄清**: 明确了 VIST 和 FSM 的区别，避免混淆
2. **功能增强**: 为 VIST 添加了 α 值实时监控和数据记录
3. **参数调优**: 调整了 VIST 参数以获得更平滑的行为
4. **架构理解**: 确认了两层配置文件的使用逻辑

**关键结论**:
- VIST 和 FSM 是两个独立的滤波器，通过 `filter_type` 参数选择
- 配置文件分为两层：ROS2 节点参数（baseline_filters_config.yaml）和 VIST 详细参数（system_config.yaml）
- 所有修改都是 VIST 相关的，没有破坏 FSM 逻辑

---

**生成时间**: 2026-03-02
**会话 ID**: [当前会话]
**分支**: feature/exo-hand-integration
**最后修改**: config/system_config.yaml, ros2_ws/src/core/vist_kalman_filter.py