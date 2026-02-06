# VIST 人类指令观测集成指南

## 问题背景

### 原始问题
用户提问："我们这个目前的观测到底是在观测什么？目前还没有引入视觉感知模块呢，是视觉感知模块和虚拟夹具怎么和我的操作控制模块集成呢？"

### 核心问题
VIST Kalman Filter 的双观测模型中：
- **虚拟引导观测 (delta_theta_virtual)**：✅ 已实现（基于目标位置的微分IK）
- **人类指令观测 (human_delta_theta)**：❌ 缺失（之前一直是零向量）

## 解决方案

### 1. 双观测模型的物理意义

```
观测向量 z = [human_delta_theta,      # 人类意图的直接表达
              delta_theta_virtual]     # 虚拟夹具的引导
```

| 观测类型 | 物理意义 | 数据来源 | 作用 |
|---------|---------|---------|------|
| **human_delta_theta** | 人手运动的直接映射 | 视觉系统检测的人手位置变化 | 跟随人类意图 |
| **delta_theta_virtual** | 目标导向的引导 | 微分IK计算（基于目标位置） | 保证末端到达目标 |

### 2. 人类指令观测的计算方法

**核心思路**：将人手位置变化 (Δx_human) 通过微分IK转换为关节角度增量

```python
# 计算人手位置变化
Δx_human = current_hand_pos - previous_hand_pos

# 通过雅可比伪逆转换为关节角度增量
human_delta_theta = J† @ Δx_human
```

**实现代码**（已添加到 `src/core/vist_kalman_filter.py`）：

```python
def compute_human_delta_theta(self, target_pos, previous_target_pos):
    """
    从人手位置变化计算人类指令增量

    Args:
        target_pos: 当前人手目标位置 (3D)
        previous_target_pos: 上一帧人手目标位置 (3D)

    Returns:
        human_delta_theta: 人类指令关节角度增量 (n_joints,)
    """
    # 1. 计算人手位置变化
    delta_x_human = target_pos - previous_target_pos

    # 2. 获取当前关节角度
    q_controlled = self.state[:self.n_joints]
    q_full = self._get_full_q_from_controlled(q_controlled)

    # 3. 计算雅可比矩阵
    pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
    pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

    J_full = pin.computeFrameJacobian(
        self.ik_solver.model,
        self.ik_solver.data,
        q_full,
        self.ik_solver.ee_frame_id,
        pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
    )

    # 4. 只使用位置部分和受控关节
    J = J_full[:3, self.ik_solver.controlled_indices]

    # 5. 阻尼伪逆
    damping = self.config.vist_differential_ik_damping
    JJT = J @ J.T
    damping_matrix = damping**2 * np.eye(3)
    J_pinv = J.T @ inv(JJT + damping_matrix)

    # 6. 人类指令增量
    human_delta_theta = J_pinv @ delta_x_human

    return human_delta_theta
```

### 3. 完整数据流

```
┌─────────────────────┐
│  Vision Node        │ RealSense + MediaPipe
│  (深度相机)         │ 检测人手关键点
└──────────┬──────────┘
           │ UDP: {wrist_pos, elbow_pos, ...}
           ↓
┌─────────────────────┐
│  Motion Mapper      │ 坐标系转换
│  (映射器)           │ 人手坐标 → 机器人坐标
└──────────┬──────────┘
           │ target_pos (当前帧)
           │ previous_target_pos (上一帧)
           ↓
┌─────────────────────┐
│  VIST Filter        │
│  ┌─────────────────┐│
│  │ 人类指令观测    ││ ← Δx_human = target_pos - previous_target_pos
│  │ human_delta_θ   ││   human_delta_θ = J† @ Δx_human
│  └─────────────────┘│
│  ┌─────────────────┐│
│  │ 虚拟引导观测    ││ ← Δx_virtual = target_pos - current_ee_pos
│  │ delta_theta_vir ││   delta_theta_virtual = J† @ Δx_virtual
│  └─────────────────┘│
│  ┌─────────────────┐│
│  │ Kalman 融合     ││ ← 融合两种观测，输出最优估计
│  │ q_solution      ││
│  └─────────────────┘│
└──────────┬──────────┘
           │ q_solution (关节角度)
           ↓
┌─────────────────────┐
│  Arm Driver         │ 发送到真实硬件
│  (驱动器)           │
└─────────────────────┘
```

### 4. 两种观测的区别

**示例场景**：你快速移动手，然后突然停止

| 时刻 | 人手状态 | human_delta_theta | delta_theta_virtual | VIST 输出 |
|------|---------|-------------------|---------------------|-----------|
| t=0 | 静止 | 0 | 小（接近目标） | 小幅调整 |
| t=1 | 快速移动 | **大**（跟随手的速度） | 大（追赶目标） | 快速响应 |
| t=2 | 突然停止 | **0**（手不动了） | 中（还在追赶） | 平滑减速 |
| t=3 | 保持静止 | 0 | 小（接近目标） | 精确定位 |

**关键差异**：
- `human_delta_theta`：反映**人手的运动意图**（速度、方向）
- `delta_theta_virtual`：反映**目标导向的引导**（误差、收敛）

## 使用方法

### 自动模式（推荐）

VIST Filter 现在会自动跟踪历史位置并计算人类指令：

```python
# 初始化
vist_filter = VISTKalmanFilter(ik_solver, config)

# 循环中使用（自动计算 human_delta_theta）
for frame in video_stream:
    target_pos = get_hand_position(frame)  # 从视觉系统获取

    # solve 方法会自动使用历史位置计算人类指令
    q_solution, success, error = vist_filter.solve(
        target_pos=target_pos,
        q_init=q_current
    )

    # VIST 内部自动完成：
    # 1. 计算 Δx_human = target_pos - previous_target_pos
    # 2. 计算 human_delta_theta = J† @ Δx_human
    # 3. 融合 human_delta_theta 和 delta_theta_virtual
    # 4. 保存 target_pos 作为下一帧的 previous_target_pos
```

### 手动模式（高级用户）

如果需要自定义人类指令计算：

```python
# 手动计算人类指令
human_delta_theta = custom_compute_human_command(...)

# 传入 update 方法
q_solution, success = vist_filter.update(
    target_pos=target_pos,
    human_delta_theta=human_delta_theta  # 手动指定
)
```

## 集成到真实系统

### 步骤1：确保 Vision Node 正常运行

```bash
# 启动视觉节点
python src/nodes/vision_node_depth.py
```

输出应包含：
- 人手关键点检测成功
- UDP 数据发送成功

### 步骤2：修改 Arm Node 使用 VIST

编辑 `src/nodes/arm_node.py`：

```python
# 替换原有的 IK 求解器
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.config import get_config

# 初始化
config = get_config()
vist_filter = VISTKalmanFilter(ik_solver, config)

# 在控制循环中
while True:
    # 接收视觉数据
    data = receive_udp_data()
    target_pos = data['wrist_pos']

    # VIST 求解（自动使用人类指令观测）
    q_solution, success, error = vist_filter.solve(
        target_pos=target_pos,
        q_init=q_current
    )

    # 发送到硬件
    if success:
        driver.send_command(q_solution)
```

### 步骤3：配置参数

编辑 `config/system_config.yaml`：

```yaml
control:
  ik_strategy: "vist"  # 启用 VIST

vist_kalman:
  observation_model:
    # 人类指令观测噪声（调整以平衡响应速度和平滑度）
    human_base_variance: 1e-2  # 基础噪声
    human_max_variance: 1e-1   # 最大噪声（自由移动时）

    # 虚拟引导观测噪声
    virtual_base_variance: 1e-4
    virtual_min_variance: 1e-5
```

## 参数调优

### 人类指令观测的权重调整

**增大 `human_base_variance`**（降低人类指令权重）：
- ✅ 更平滑，减少抖动
- ❌ 响应变慢，延迟增加

**减小 `human_base_variance`**（增大人类指令权重）：
- ✅ 响应更快，跟随性好
- ❌ 可能出现抖动

### 推荐调优流程

1. **初始值**：`human_base_variance = 1e-2`
2. **如果响应慢**：降低到 `5e-3`
3. **如果抖动**：增大到 `2e-2`
4. **精细调整**：在 `5e-3` 到 `2e-2` 之间微调

## 验证方法

### 测试1：静止测试
```python
# 手保持静止，机器人应该也静止
# 预期：human_delta_theta ≈ 0
```

### 测试2：匀速运动测试
```python
# 手匀速移动，机器人应该平滑跟随
# 预期：human_delta_theta 稳定非零
```

### 测试3：突然停止测试
```python
# 手快速移动后突然停止
# 预期：机器人平滑减速（不会突然停止）
```

### 测试4：对比测试
```python
# 对比有/无人类指令观测的性能
# 预期：有人类指令观测时响应更快
```

## 常见问题

### Q1：为什么之前 human_delta_theta 是零向量？
**A**：因为没有实现从视觉数据到人类指令的转换逻辑。现在已经添加了 `compute_human_delta_theta` 方法。

### Q2：人类指令和虚拟引导有什么区别？
**A**：
- 人类指令：反映**人手的运动速度和方向**
- 虚拟引导：反映**机器人末端与目标的误差**

### Q3：如果视觉数据有噪声怎么办？
**A**：通过调整 `human_base_variance` 来降低人类指令的权重，让系统更依赖虚拟引导。

### Q4：可以只使用虚拟引导吗？
**A**：可以，设置 `human_base_variance = 1e10`（极大值）即可忽略人类指令观测。

## 总结

### 修改内容
1. ✅ 添加 `compute_human_delta_theta` 方法
2. ✅ 修改 `update` 方法支持自动计算人类指令
3. ✅ 添加 `previous_target_pos` 历史跟踪
4. ✅ 修改 `solve` 方法自动使用历史位置
5. ✅ 修改 `reset` 方法重置历史数据

### 核心优势
- **自动化**：无需手动计算人类指令，VIST 自动处理
- **透明化**：对外接口不变，内部自动融合双观测
- **可配置**：通过参数调整人类指令和虚拟引导的权重

### 下一步
1. 运行测试验证人类指令观测是否正常工作
2. 调整参数优化响应速度和平滑度
3. 集成到真实 Arm Node 进行实际测试
