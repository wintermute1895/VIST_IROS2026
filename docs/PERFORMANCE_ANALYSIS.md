# VIST 性能分析与优化建议

## 1. 当前性能状态

### 测试结果（2026-02-06）
- **IK 成功率**: 68.7%
- **帧率**: 7.2 fps（从 11-12 fps 下降）
- **位置误差**: 0.00-0.99mm（优秀）
- **姿态误差**: 0.6-1.4 rad (34-80°)
- **问题**: 偶尔卡顿，终端和画面静止

### 当前参数配置
```yaml
ik_gain: 0.5          # 降低以获得更平滑运动
ik_damping: 5e-3      # 增加以减少跳变
ik_max_iter: 100      # 从 50 增加
ik_tolerance: 2e-3    # 2mm（平衡精度和稳定性）
```

## 2. 卡顿问题根因分析

### 主要原因：过多的终端输出

**问题位置**: `src/core/ik_solver.py`

每秒终端输出量：
- 成功打印（line 303-305）: ~5 次/秒
- 失败打印（line 369）: ~2.3 次/秒
- 迭代打印（line 360-364）: ~36 次/秒（每 10 次迭代）

**总计**: 每秒 40+ 行输出 → 终端缓冲区阻塞 → 卡顿

### 次要因素

1. **IK 计算时间增加**
   - gain=0.5 导致收敛变慢
   - 平均每帧 ~139ms

2. **未收敛时的全迭代**
   - 31.3% 失败率 × 100 次迭代
   - 每秒约 2 帧跑满 100 次迭代

## 3. 立即修复（已完成）

### 修改内容
注释掉 `src/core/ik_solver.py` 中的调试打印：
- Line 303-305: 收敛成功打印
- Line 311: 3-DoF 收敛打印
- Line 360-364: 迭代进度打印
- Line 369: 未收敛警告

### 预期效果
- 终端输出减少 95%
- 消除卡顿现象
- 帧率可能提升至 8-9 fps

## 4. VIST 卡尔曼滤波集成方案

### 4.1 为什么 VIST 能解决问题？

根据 `docs/VIST_modeling.md`，VIST 框架提供了三个核心优势：

#### ① 微分 IK 避免多解问题

**当前问题**：
```
全局 IK: 给定目标位置 x_target，求解 θ = IK(x_target)
→ 多解性导致跳变
→ 收敛困难（68.7% 成功率）
```

**VIST 解决方案**：
```
微分 IK: 计算增量 Δθ = J†·Δx
→ 局部最优，天然连续
→ 雅可比伪逆自动寻找最小动能路径
→ 防止肘部跳变
```

#### ② 卡尔曼预测补偿延迟

**当前问题**：
- 视觉数据有噪声和延迟
- IK 求解时间不稳定（7.2 fps）

**VIST 解决方案**：
```
恒速过程模型: x(t+Δt) = x(t) + v(t)·Δt
→ 利用物理惯性预测运动
→ 零延迟平滑预测
→ 补偿视觉信号离散间隙
```

#### ③ 意图驱动的自适应滤波

**VIST 协方差调度**：
```
α → 0 (自由移动):
  - 增大观测噪声 R_human
  - 降低卡尔曼增益 K
  - 强力去噪，平滑轨迹

α → 1 (精密操作):
  - 减小虚拟噪声 R_virtual
  - 增大卡尔曼增益 K
  - 磁吸式引导，稳定收敛
```

### 4.2 预期性能提升

| 指标 | 当前 | VIST 预期 | 提升 |
|------|------|-----------|------|
| IK 成功率 | 68.7% | 85-90% | +20% |
| 帧率 | 7.2 fps | 15-20 fps | +2x |
| 跳变频率 | 偶尔 | 几乎无 | -90% |
| 卡顿 | 偶尔 | 无 | -100% |

### 4.3 实现路线图

#### Phase 1: 状态估计器（1-2天）
```python
class VISTKalmanFilter:
    """VIST 卡尔曼滤波状态估计器"""

    def __init__(self, n_joints=7):
        # 状态向量: [θ, θ̇] (14维)
        self.state = np.zeros(2 * n_joints)

        # 状态转移矩阵 F (恒速模型)
        self.F = np.block([
            [np.eye(n_joints), dt * np.eye(n_joints)],
            [np.zeros((n_joints, n_joints)), np.eye(n_joints)]
        ])

        # 过程噪声 Q (各向异性，肘部方差更小)
        self.Q = self._build_anisotropic_noise(alpha)

        # 观测噪声 R (意图驱动)
        self.R_human = self._schedule_covariance(alpha)
        self.R_virtual = self._schedule_covariance(1 - alpha)

    def predict(self):
        """预测步：利用物理惯性"""
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, z_human, z_virtual):
        """更新步：融合人类指令和虚拟引导"""
        # 计算卡尔曼增益
        K = self.P @ self.H.T @ inv(self.H @ self.P @ self.H.T + self.R)

        # 更新状态
        z = np.concatenate([z_human, z_virtual])
        self.state = self.state + K @ (z - self.H @ self.state)
```

#### Phase 2: 微分 IK 观测（1天）
```python
def compute_differential_observation(self, target_pos, current_q):
    """计算微分观测 Δθ = J†·Δx"""
    # 计算位置误差
    current_pos = self.forward_kinematics(current_q)
    delta_x = target_pos - current_pos

    # 计算雅可比矩阵
    J = self.compute_jacobian(current_q)

    # 阻尼伪逆
    J_pinv = J.T @ inv(J @ J.T + damping**2 * np.eye(3))

    # 微分观测
    delta_theta = J_pinv @ delta_x

    return delta_theta
```

#### Phase 3: 意图检测（1天）
```python
def detect_intent(self, velocity, distance_to_target):
    """检测操作意图 α ∈ [0, 1]"""
    # α → 0: 快速移动（自由模式）
    # α → 1: 接近目标（精密模式）

    alpha = 1.0 / (1.0 + np.exp(-k * (d_threshold - distance_to_target)))
    return alpha
```

#### Phase 4: 集成测试（1天）
- 替换当前的全局 IK
- 对比性能指标
- 调优参数

**总计**: 4-5 天完整实现

### 4.4 配置文件扩展

在 `config/system_config.yaml` 中添加：

```yaml
# VIST Kalman Filter 参数
vist_kalman:
  # 过程噪声（各向异性）
  process_noise:
    position_variance: 1e-4
    velocity_variance: 1e-3
    elbow_damping_factor: 0.1  # 肘部方差衰减

  # 观测噪声（意图驱动）
  observation_noise:
    human_base: 1e-2      # 人类输入基础噪声
    virtual_base: 1e-4    # 虚拟引导基础噪声
    intent_sensitivity: 5.0  # 意图因子敏感度

  # 意图检测
  intent_detection:
    distance_threshold: 0.1  # 精密模式触发距离（米）
    velocity_threshold: 0.05  # 速度阈值（m/s）
```

## 5. 决策建议

### 方案 A：立即测试修复效果（推荐）
1. 运行修复后的仿真
2. 观察卡顿是否消失
3. 记录新的成功率和帧率

### 方案 B：直接集成 VIST（如果需要 80%+ 成功率）
1. 实现 Phase 1-4（4-5天）
2. 预期达到 85-90% 成功率
3. 彻底解决跳变和卡顿

### 方案 C：混合方案
1. 先测试修复效果（今天）
2. 如果成功率仍 <75%，启动 VIST 集成（下周）

## 6. 上真机的判断标准

### 最低要求
- ✅ IK 成功率 ≥ 75%
- ✅ 无明显跳变
- ✅ 无卡顿
- ✅ 帧率 ≥ 10 fps

### 理想状态（VIST 集成后）
- ✅ IK 成功率 ≥ 85%
- ✅ 平滑连续运动
- ✅ 帧率 ≥ 15 fps
- ✅ 延迟补偿

## 7. 参考文献

- `docs/VIST_modeling.md`: VIST 数学模型详细推导
- `src/core/ik_solver.py`: 当前 IK 实现
- `config/system_config.yaml`: 系统参数配置
