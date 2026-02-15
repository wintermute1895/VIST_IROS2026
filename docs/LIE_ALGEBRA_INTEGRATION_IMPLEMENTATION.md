# 李代数集成实现文档

## 概述

本文档描述了如何在 VIST Kalman 滤波器中集成李代数（Lie Algebra）支持，实现混合方案：
- **状态空间**：关节空间 x = [q, q̇] ∈ ℝ^{2n}
- **观测空间**：任务空间 SE(3)
- **姿态误差**：使用李代数 δθ = log_SO3(R_current^T R_target)

## 设计理念

### 为什么选择混合方案？

**方案A：纯任务空间 ESKF**
- 状态：x = [p, v, R, b_a, b_g] (笛卡尔空间)
- 优点：数学优雅，姿态在 SO(3) 上
- 缺点：需要输出端 IK，可能有奇异性

**方案B：纯关节空间 KF（原实现）**
- 状态：x = [q, q̇] (关节空间)
- 优点：直接控制关节，无需输出端 IK
- 缺点：姿态约束不直观

**混合方案（本实现）**
- 状态：x = [q, q̇] (关节空间)
- 观测：任务空间 SE(3)，使用李代数计算姿态误差
- 优点：
  1. 避免输出端 IK 奇异性
  2. 利用李代数的数学优雅性
  3. 保持关节空间滤波的计算效率
  4. 适合论文发表（理论+实践平衡）

## 实现细节

### 1. 李代数模块导入

```python
# src/core/vist_kalman_filter.py
from src.utils.lie_algebra import slerp_rotation
```

### 2. 任务空间误差计算

```python
def _compute_task_space_error_with_lie_algebra(self, current_pose, target_pose):
    """
    计算任务空间误差（使用李代数处理姿态）

    Args:
        current_pose: 当前末端位姿 (pin.SE3)
        target_pose: 目标位姿 (pin.SE3)

    Returns:
        δx: [δp, δθ] ∈ ℝ^6，其中 δθ ∈ so(3)
    """
    # 1. 位置误差（欧氏空间）
    δp = target_pose.translation - current_pose.translation

    # 2. 姿态误差（李代数）
    R_current = current_pose.rotation
    R_target = target_pose.rotation
    R_rel = R_current.T @ R_target
    δθ = pin.log3(R_rel)  # SO(3) → so(3)

    # 3. 组合为 6D 任务空间误差
    return np.concatenate([δp, δθ])
```

**关键点**：
- 位置误差：欧氏空间，直接相减
- 姿态误差：李代数空间，使用 `pin.log3` 映射 SO(3) → so(3)
- 避免欧拉角奇异性

### 3. 带姿态的微分 IK

```python
def compute_differential_ik_with_orientation(self, target_pos, target_quat):
    """
    计算带姿态的微分 IK 观测：Δθ = J†·δx

    使用完整的 6D 雅可比矩阵（位置 + 姿态）
    """
    # 1. 获取当前位姿
    current_pose = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]

    # 2. 构建目标位姿
    target_rot = pin.Quaternion(...).toRotationMatrix()
    target_pose = pin.SE3(target_rot, target_pos)

    # 3. 使用李代数计算任务空间误差
    δx = self._compute_task_space_error_with_lie_algebra(current_pose, target_pose)

    # 4. 计算完整的 6D 雅可比矩阵
    J_full = pin.computeFrameJacobian(...)  # 6 × n_joints
    J = J_full[:, self.ik_solver.controlled_indices]

    # 5. 阻尼伪逆
    J_pinv = J.T @ inv(J @ J.T + λ²I)

    # 6. 微分观测
    Δθ = J_pinv @ δx

    return Δθ
```

**关键点**：
- 使用完整的 6D 雅可比矩阵（不是只用前3行）
- 阻尼矩阵维度：6×6（不是3×3）
- 姿态误差通过李代数计算，保证数学正确性

### 4. 配置开关

```yaml
# config/system_config.yaml
vist_kalman:
  observation_model:
    use_orientation_control: false  # 默认关闭
```

```python
# src/config/config_loader.py
@property
def vist_use_orientation_control(self):
    """VIST 是否使用姿态控制（李代数支持）"""
    return bool(self._config.get('vist_kalman', {}).get('observation_model', {}).get('use_orientation_control', False))
```

### 5. Update 方法集成

```python
def update(self, target_pos, target_quat=None, ...):
    # 1. 检查配置开关
    use_orientation = getattr(self.config, 'vist_use_orientation_control', False)

    if use_orientation and target_quat is not None:
        # 使用带姿态的微分 IK（6D雅可比 + 李代数）
        delta_theta_virtual = self.compute_differential_ik_with_orientation(target_pos, target_quat)
    else:
        # 使用标准微分 IK（只控制位置，3D雅可比）
        delta_theta_virtual = self.compute_differential_ik(target_pos, target_quat)

    # 2. 后续流程不变
    ...
```

## 使用方法

### 默认模式（只控制位置）

```yaml
# config/system_config.yaml
vist_kalman:
  observation_model:
    use_orientation_control: false
```

- 适用场景：USB 插入等位置主导任务
- 优点：计算效率高，避免姿态奇异性
- 使用 3D 雅可比矩阵

### 姿态控制模式（位置+姿态）

```yaml
# config/system_config.yaml
vist_kalman:
  observation_model:
    use_orientation_control: true
```

- 适用场景：需要精确姿态的任务（如螺丝拧紧）
- 优点：使用李代数，避免欧拉角奇异性
- 使用 6D 雅可比矩阵

## 测试验证

运行测试脚本：

```bash
python3 scripts/test_lie_algebra_integration.py
```

测试内容：
1. ✅ 李代数模块导入
2. ✅ 任务空间误差计算（李代数）
3. ✅ 配置开关
4. ✅ VIST Kalman 滤波器集成

## 论文表述

### Method Part 2: State Estimation Framework

```markdown
我们采用关节空间 Kalman 滤波，但在观测模型中使用李代数处理姿态：

**状态向量**：x = [q, q̇]^T ∈ ℝ^{2n}

**观测模型**：
  h(q) = FK(q) ∈ SE(3)

**观测残差（任务空间）**：
  δx = [δp, δθ]
  δp = p_target - FK(q)_pos
  δθ = log_SO3(FK(q)_rot^T R_target)  ← 李代数

**关节空间观测**：
  z = J^+ δx

其中 J 是雅可比矩阵，J^+ 是伪逆。

**设计优势**：
1. 姿态误差定义在 so(3) 切空间，避免奇异性
2. 关节空间滤波避免输出端 IK 问题
3. 李代数保证姿态误差的数学正确性
```

## 数学推导

### 李代数映射

**SO(3) → so(3)**：
```
R_rel = R_current^T @ R_target
δθ = log_SO3(R_rel)
```

**性质**：
- δθ ∈ ℝ^3 是轴角表示
- ||δθ|| = 旋转角度
- δθ/||δθ|| = 旋转轴

### 雅可比矩阵

**完整雅可比**：
```
J = [J_v]  ∈ ℝ^{6×n}
    [J_ω]
```

- J_v: 速度雅可比（3×n）
- J_ω: 角速度雅可比（3×n）

**微分 IK**：
```
δx = [δp]  ∈ ℝ^6
     [δθ]

Δq = J^+ δx
```

## 性能对比

| 维度 | 纯位置控制 | 位置+姿态控制 |
|------|-----------|--------------|
| 雅可比维度 | 3×n | 6×n |
| 计算复杂度 | O(n³) | O(n³) |
| 姿态精度 | 低 | 高 |
| 奇异性 | 低 | 中（李代数避免） |
| 适用任务 | USB插入 | 螺丝拧紧 |

## 未来扩展

1. **自适应权重**：根据任务阶段动态调整位置/姿态权重
2. **学习 α**：从示教数据学习意图因子
3. **多模态融合**：结合力/力矩传感器
4. **在线优化**：实时优化协方差参数

## 参考文献

1. Pinocchio: A fast and flexible implementation of rigid body dynamics algorithms
2. Lie Groups for 2D and 3D Transformations
3. Modern Robotics: Mechanics, Planning, and Control

## 总结

本实现成功将李代数集成到 VIST Kalman 滤波器中，实现了：
- ✅ 保持关节空间状态（避免输出端 IK）
- ✅ 使用李代数处理姿态（数学优雅）
- ✅ 配置开关（灵活切换）
- ✅ 向后兼容（不影响现有功能）

这为论文提供了坚实的数学基础，同时保持了实现的简洁性和效率。
