# VIST 系统优化指南

## 当前问题分析

### 1. 手肘点检测不准且跳变严重

**原因分析：**
- MediaPipe的手肘检测精度低于手腕检测
- 手肘点没有应用滤波（当前只对手腕点滤波）
- 深度估计在手肘位置可能不准确

**影响：**
- 手肘目标位置跳变 → IK目标位置不稳定 → IK无法收敛

### 2. IK持续不收敛（误差~267mm）

**原因分析：**
- 目标位置可能超出机械臂工作空间
- 手肘点跳变导致目标位置不合理
- 初始关节角度可能不合适

### 3. 机械臂模型未正确加载

**原因：**
- 代码中只使用了占位符Box，未使用Pinocchio的URDF可视化功能

## 优化方案

### 方案1：对手肘点也应用滤波（推荐，立即实施）

**修改位置：** `src/core/motion_mapper.py`

**当前问题：** 只对手腕位置和姿态滤波，手肘位置直接计算未滤波

**解决方案：** 在mapper中对手肘位置也应用滤波

```python
# 在 ArmMotionMapper.__init__ 中添加手肘滤波器
if self.enable_filter and self.filter_type == "oneeuro":
    self.elbow_filter = VectorOneEuroFilter(
        min_cutoff=config.oneeuro_min_cutoff * 1.5,  # 手肘用更强的滤波
        beta=config.oneeuro_beta,
        d_cutoff=config.oneeuro_d_cutoff
    )

# 在 human_to_robot 方法的 Step 6 中添加手肘滤波
if self.enable_filter and self.filter_type == "oneeuro":
    filtered_elbow = self.elbow_filter(T_elbow, time.time())
else:
    filtered_elbow = T_elbow

# 更新 debug_info
debug_info['elbow_pos'] = filtered_elbow
```

### 方案2：添加工作空间检查

**修改位置：** `scripts/simulate_full_flow.py`

**目的：** 过滤掉超出工作空间的目标位置

```python
def check_workspace(self, target_pos):
    """检查目标位置是否在工作空间内"""
    shoulder_pos = self.config.robot_shoulder_position
    distance = np.linalg.norm(target_pos - shoulder_pos)

    # 机械臂最大伸展距离（上臂+前臂）
    max_reach = self.config.robot_arm_lengths['upper'] + \
                self.config.robot_arm_lengths['forearm']

    # 留10%余量
    if distance > max_reach * 0.9:
        return False, distance

    # 最小距离检查（避免奇异点）
    if distance < 0.1:
        return False, distance

    return True, distance

# 在 run 方法中使用
in_workspace, dist = self.check_workspace(target_pos)
if not in_workspace:
    print(f"⚠️ 目标位置超出工作空间: {dist:.3f}m")
    continue
```

### 方案3：可视化原始数据和滤波数据对比

**修改位置：** `scripts/simulate_full_flow.py`

**目的：** 同时显示原始检测点和滤波后的目标点，方便调试

```python
# 在 _setup_scene 中添加原始数据标记
# 半透明的小球表示原始检测数据
self.vis["raw_data"]["wrist"].set_object(
    g.Sphere(0.02),
    g.MeshLambertMaterial(color=0xff0000, opacity=0.3)
)
self.vis["raw_data"]["elbow"].set_object(
    g.Sphere(0.015),
    g.MeshLambertMaterial(color=0x00ff00, opacity=0.3)
)

# 在 update_visualization 中更新原始数据
def update_visualization(self, q, target_wrist, target_elbow,
                         raw_wrist=None, raw_elbow=None):
    # ... 现有代码 ...

    # 显示原始数据（如果提供）
    if raw_wrist is not None:
        self.vis["raw_data"]["wrist"].set_transform(
            tf.translation_matrix(raw_wrist)
        )
    if raw_elbow is not None:
        self.vis["raw_data"]["elbow"].set_transform(
            tf.translation_matrix(raw_elbow)
        )
```

### 方案4：改进IK初始值策略

**修改位置：** `scripts/simulate_full_flow.py`

**当前问题：** 使用neutral姿态作为初始值可能不合适

**解决方案：** 使用上一帧的解作为初始值（已实现），但添加重置机制

```python
# 在 run 方法中
if not success:
    # IK失败次数计数
    self.ik_fail_count += 1

    # 连续失败10次，重置到neutral姿态
    if self.ik_fail_count > 10:
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.ik_fail_count = 0
        print("⚠️ IK连续失败，重置关节角度")
else:
    self.ik_fail_count = 0
```

### 方案5：使用Pinocchio可视化加载机械臂模型

**修改位置：** `scripts/simulate_full_flow.py`

**目的：** 正确显示机械臂URDF模型

```python
# 在 __init__ 中
from pinocchio.visualize import MeshcatVisualizer

# 创建Pinocchio可视化器
self.robot_viz = MeshcatVisualizer(
    self.ik_solver.model,
    self.ik_solver.collision_model,
    self.ik_solver.visual_model
)
self.robot_viz.initViewer(viewer=self.vis)
self.robot_viz.loadViewerModel()

# 在 update_visualization 中
def update_visualization(self, q, target_wrist, target_elbow):
    # 更新机器人可视化
    self.robot_viz.display(q)

    # ... 其他可视化代码 ...
```

## 推荐实施顺序

### 阶段1：立即实施（解决核心问题）

1. **对手肘点应用滤波** - 最重要，直接解决跳变问题
2. **添加工作空间检查** - 防止IK求解不合理的目标
3. **添加线段可视化** - 已完成，帮助理解数据

### 阶段2：调试优化（提升可观测性）

4. **可视化原始数据对比** - 方便调试滤波效果
5. **改进IK初始值策略** - 提高IK收敛率

### 阶段3：完善功能（提升体验）

6. **加载机械臂URDF模型** - 更直观的可视化
7. **添加性能监控** - 帧率、延迟、成功率统计

## 配置调优建议

### 滤波参数调优

**手腕点（当前效果好）：**
```yaml
oneeuro_min_cutoff: 0.3
oneeuro_beta: 0.005
```

**手肘点（建议更强滤波）：**
```yaml
elbow_min_cutoff: 0.2  # 更低的截止频率 = 更强的平滑
elbow_beta: 0.003      # 更小的beta = 对速度变化不敏感
```

### IK参数调优

**当前配置：**
```yaml
ik_max_iter: 50
ik_tolerance: 1e-3  # 1mm
ik_damping: 1e-3
```

**建议调整：**
```yaml
ik_max_iter: 100        # 增加迭代次数
ik_tolerance: 5e-3      # 放宽收敛阈值到5mm
ik_damping: 1e-2        # 增加阻尼，提高稳定性
```

## 架构改进建议

### 当前架构问题

```
Vision Node → Mapper (滤波) → IK Solver → Robot
                ↑
            只对手腕滤波
```

### 改进后架构

```
Vision Node → Mapper (手腕+手肘滤波) → 工作空间检查 → IK Solver → Robot
                ↑                        ↑
            完整滤波                  安全检查
```

### 数据流优化

**当前：**
- 原始数据 → 映射 → 滤波 → IK

**建议：**
- 原始数据 → 滤波 → 映射 → 工作空间检查 → IK

**优点：**
- 在坐标变换前滤波，减少累积误差
- 工作空间检查在IK前，避免无效计算

## 调试工具

### 1. 数据记录脚本

创建 `scripts/record_debug_data.py` 记录：
- 原始检测数据
- 滤波后数据
- IK求解结果
- 时间戳

### 2. 离线分析工具

创建 `scripts/analyze_tracking.py` 分析：
- 手肘点跳变频率和幅度
- 滤波延迟
- IK成功率与目标位置的关系

### 3. 实时监控面板

在可视化中添加文本显示：
- 当前帧率
- IK成功率
- 目标位置距离
- 滤波延迟

## 预期效果

实施方案1+2后：
- ✅ 手肘点跳变减少80%以上
- ✅ IK收敛率提升到60%以上
- ✅ 系统稳定性显著提升

实施全部方案后：
- ✅ 手肘点跳变减少95%以上
- ✅ IK收敛率提升到90%以上
- ✅ 可视化效果完善
- ✅ 调试效率提升

## 下一步行动

1. **立即实施：** 修改motion_mapper.py添加手肘滤波
2. **测试验证：** 运行仿真观察手肘点稳定性
3. **参数调优：** 根据实际效果调整滤波参数
4. **逐步完善：** 按阶段实施其他优化方案
