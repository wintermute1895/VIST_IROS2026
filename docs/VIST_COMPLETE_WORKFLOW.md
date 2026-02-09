# VIST 完整工作流程设计

## 📋 概述

本文档描述 VIST 系统的完整工作流程，包括人类主导接近、算法主导对齐、可选微调和自动插入。

---

## 🎯 四阶段工作流程

### 阶段 1: 人类主导的大范围接近（α → 0）

**特征**：
- 距离目标 > 5cm
- 人类操作员控制机器人移动
- 算法提供平滑跟随和去噪

**意图因子**：
```python
α ≈ 0  # 接近阶段
```

**系统行为**：
- **Q(α) 大**：信任恒速模型（人手快速移动）
- **R_human(α) 小**：信任人类指令（跟随人手）
- **R_virtual(α) 大**：不信任虚拟引导（忽略目标吸附）

**算法角色**：
- ✅ 平滑跟随人类指令
- ✅ 强力去噪（过滤视觉抖动）
- ❌ 不提供目标引导

---

### 阶段 2: 算法主导的精密对齐（α → 1）

**特征**：
- 距离目标 < 5cm
- 算法接管控制
- 提供导纳控制，"吸附"到目标插孔

**意图因子**：
```python
α ≈ 1  # 精密阶段
```

**系统行为**：
- **Q(α) 小**：不信任恒速模型（人手可能静止）
- **R_human(α) 大**：不信任人类指令（人手可能抖动）
- **R_virtual(α) 小**：信任虚拟引导（磁吸引导）

**算法角色**：
- ✅ 主导对齐（虚拟夹具）
- ✅ 计算朝向目标的微分 IK
- ✅ "吸附"到目标插孔附近

**虚拟夹具权重**：
```python
# 观测融合
z_total = (1 - α) * z_human + α * z_virtual

# 当 α = 1 时：
z_total ≈ z_virtual  # 完全由算法主导
```

---

### 阶段 2.5: 可选的人类微调（α_fine_tune）

**触发条件**：
- 距离目标 < 5cm（已进入精密阶段）
- 检测到人类"微调"意图
- 标定精度不够，需要人类干预

**微调意图检测**：
```python
def detect_fine_tuning_intent(velocity, acceleration, distance):
    """
    检测人类微调意图

    特征：
    - 小幅度移动（< 2cm）
    - 慢速度（< 1cm/s）
    - 低加速度（平稳移动）
    - 已经接近目标（< 5cm）
    """
    is_small_movement = distance < 0.02  # 2cm
    is_slow_speed = velocity < 0.01      # 1cm/s
    is_smooth = acceleration < 0.05      # 低加速度

    is_fine_tuning = (
        is_small_movement and
        is_slow_speed and
        is_smooth
    )

    return is_fine_tuning
```

**系统行为**：
- **降低虚拟夹具权重**：允许人类微调
- **保持平滑滤波**：避免抖动
- **实时监测**：完成微调后恢复算法主导

**动态权重调整**：
```python
# 检测微调意图
if detect_fine_tuning_intent(...):
    # 降低虚拟夹具权重
    α_effective = α * 0.3  # 降低到 30%
else:
    # 正常权重
    α_effective = α

# 观测融合
z_total = (1 - α_effective) * z_human + α_effective * z_virtual
```

---

### 阶段 3: 算法主导的自动插入

**触发条件**：
- 对齐完成（位置误差 < 2mm）
- 姿态正确（插头水平向下）
- 人类确认（或自动触发）

**插入控制**：
```python
def auto_insertion_control(current_depth, target_depth=0.015):
    """
    自动插入控制

    Args:
        current_depth: 当前插入深度（米）
        target_depth: 目标深度（USB 标准深度 15mm）

    Returns:
        插入速度指令
    """
    # USB Type-A 标准插入深度
    USB_INSERTION_DEPTH = 0.015  # 15mm

    # 计算剩余深度
    remaining_depth = target_depth - current_depth

    # 速度控制（越接近越慢）
    if remaining_depth > 0.010:  # > 10mm
        velocity = 0.01  # 1cm/s（快速）
    elif remaining_depth > 0.005:  # 5-10mm
        velocity = 0.005  # 0.5cm/s（中速）
    else:  # < 5mm
        velocity = 0.002  # 0.2cm/s（慢速）

    # 力控制（检测插入阻力）
    if detect_insertion_resistance():
        velocity *= 0.5  # 减速

    return velocity
```

**深度测量**：
```python
def measure_insertion_depth(initial_pos, current_pos):
    """
    测量插入深度

    方法 1: 基于位置变化
    """
    depth = np.linalg.norm(current_pos - initial_pos)
    return depth

def detect_insertion_complete(depth, force=None):
    """
    检测插入完成

    条件：
    - 深度达到标准值（15mm）
    - 或检测到插入阻力（力传感器）
    """
    USB_STANDARD_DEPTH = 0.015  # 15mm

    depth_reached = depth >= USB_STANDARD_DEPTH * 0.95  # 95% 深度

    if force is not None:
        force_detected = force > INSERTION_FORCE_THRESHOLD
        return depth_reached or force_detected
    else:
        return depth_reached
```

---

### 阶段 4: 任务结束（松手检测）

**触发条件**：
- 插入完成
- 检测到人类松手

**松手检测**：
```python
def detect_hand_release(hand_velocity, hand_acceleration):
    """
    检测人类松手

    特征：
    - 手部突然停止移动
    - 或手部快速远离机器人
    """
    # 方法 1: 手部静止
    is_stationary = hand_velocity < 0.001  # < 1mm/s

    # 方法 2: 手部远离
    is_moving_away = hand_velocity > 0.05 and hand_acceleration > 0.1

    return is_stationary or is_moving_away
```

**机器人响应**：
```python
def on_hand_release():
    """
    松手后的机器人动作
    """
    # 1. 打开手指（释放 USB）
    robot.open_gripper()

    # 2. 后退一小段距离
    robot.move_relative([0, 0, -0.05])  # 后退 5cm

    # 3. 任务完成
    print("✅ USB 插入完成！")
```

---

## 🔧 意图感知的完整实现

### 核心创新：冲突检测（β term）

**关键公式**：
```python
α = f(v, d)           # 基础意图因子（基于速度和距离）
β = conflict(...)     # 冲突因子（人类-算法意图冲突）
α_effective = α × (1-β)  # 有效意图因子
```

**冲突因子 β**：
- **β = 0**：无冲突（人类和算法方向一致）
- **β = 1**：完全冲突（人类和算法方向相反）
- **0 < β < 1**：部分冲突（柔顺接管）

**效果**：
- 当人类"抵抗"算法时，β 增大，α_eff 降低
- 系统自动降低算法权重，允许人类接管
- 无需显式切换模式，实现**柔顺接管 (Compliant Takeover)**

详细说明请参考：[CONFLICT_DETECTION_AND_COMPLIANT_TAKEOVER.md](./CONFLICT_DETECTION_AND_COMPLIANT_TAKEOVER.md)

---

### 扩展的意图因子

```python
class IntentState(Enum):
    """意图状态枚举"""
    APPROACHING = "approaching"      # 接近阶段（人类主导）
    ALIGNING = "aligning"            # 对齐阶段（算法主导）
    FINE_TUNING = "fine_tuning"      # 微调阶段（人类微调）
    INSERTING = "inserting"          # 插入阶段（算法主导）
    COMPLETED = "completed"          # 任务完成


class EnhancedIntentDetector:
    """增强的意图检测器"""

    def __init__(self, config):
        self.config = config
        self.current_state = IntentState.APPROACHING

        # 阈值参数
        self.align_distance_threshold = 0.05  # 5cm
        self.fine_tune_velocity_threshold = 0.01  # 1cm/s
        self.insertion_alignment_threshold = 0.002  # 2mm

    def detect_intent(
        self,
        distance: float,
        velocity: float,
        acceleration: float,
        alignment_error: float
    ) -> Tuple[IntentState, float]:
        """
        检测当前意图状态

        Args:
            distance: 到目标的距离（米）
            velocity: 移动速度（米/秒）
            acceleration: 加速度（米/秒²）
            alignment_error: 对齐误差（米）

        Returns:
            intent_state: 意图状态
            alpha: 意图因子
        """
        # 状态转换逻辑
        if self.current_state == IntentState.APPROACHING:
            # 接近 → 对齐
            if distance < self.align_distance_threshold:
                self.current_state = IntentState.ALIGNING
                print("🎯 进入对齐阶段（算法主导）")

        elif self.current_state == IntentState.ALIGNING:
            # 对齐 → 微调
            if self._detect_fine_tuning(velocity, acceleration, distance):
                self.current_state = IntentState.FINE_TUNING
                print("🔧 检测到微调意图（人类微调）")

            # 对齐 → 插入
            elif alignment_error < self.insertion_alignment_threshold:
                self.current_state = IntentState.INSERTING
                print("📥 开始自动插入（算法主导）")

        elif self.current_state == IntentState.FINE_TUNING:
            # 微调 → 对齐
            if not self._detect_fine_tuning(velocity, acceleration, distance):
                self.current_state = IntentState.ALIGNING
                print("🎯 恢复对齐阶段（算法主导）")

        elif self.current_state == IntentState.INSERTING:
            # 插入 → 完成
            if self._detect_insertion_complete():
                self.current_state = IntentState.COMPLETED
                print("✅ 插入完成！")

        # 计算意图因子
        alpha = self._compute_alpha(self.current_state, distance, velocity)

        return self.current_state, alpha

    def _detect_fine_tuning(
        self,
        velocity: float,
        acceleration: float,
        distance: float
    ) -> bool:
        """检测微调意图"""
        is_small_movement = distance < 0.02  # 2cm
        is_slow_speed = velocity < self.fine_tune_velocity_threshold
        is_smooth = acceleration < 0.05

        return is_small_movement and is_slow_speed and is_smooth

    def _compute_alpha(
        self,
        state: IntentState,
        distance: float,
        velocity: float
    ) -> float:
        """计算意图因子"""
        if state == IntentState.APPROACHING:
            # 接近阶段：α → 0（人类主导）
            return 0.0

        elif state == IntentState.ALIGNING:
            # 对齐阶段：α → 1（算法主导）
            return 1.0

        elif state == IntentState.FINE_TUNING:
            # 微调阶段：α 降低（允许人类微调）
            return 0.3  # 降低虚拟夹具权重

        elif state == IntentState.INSERTING:
            # 插入阶段：α = 1（算法主导）
            return 1.0

        elif state == IntentState.COMPLETED:
            # 完成阶段
            return 0.0

        return 0.5  # 默认值
```

---

## 📊 参数配置

```yaml
# config/vist_intent_detection.yaml

intent_detection:
  # 阶段转换阈值
  align_distance_threshold: 0.05  # 5cm，进入对齐阶段
  fine_tune_velocity_threshold: 0.01  # 1cm/s，检测微调
  insertion_alignment_threshold: 0.002  # 2mm，开始插入

  # 微调检测参数
  fine_tune:
    max_distance: 0.02  # 2cm
    max_velocity: 0.01  # 1cm/s
    max_acceleration: 0.05  # 低加速度

  # 插入控制参数
  insertion:
    target_depth: 0.015  # 15mm（USB 标准）
    fast_velocity: 0.01  # 1cm/s
    medium_velocity: 0.005  # 0.5cm/s
    slow_velocity: 0.002  # 0.2cm/s

  # 松手检测参数
  hand_release:
    stationary_threshold: 0.001  # 1mm/s
    moving_away_velocity: 0.05  # 5cm/s
```

---

## 🎮 完整工作流程示例

```python
def vist_complete_workflow():
    """VIST 完整工作流程"""

    # 初始化
    intent_detector = EnhancedIntentDetector(config)
    target_detector = create_target_detector('apriltag')
    vist_filter = VISTKalmanFilter(...)

    # 主循环
    while True:
        # 1. 获取数据
        human_kps = get_human_keypoints()
        target_pos = target_detector.detect().position
        current_pos = robot.get_end_effector_position()

        # 2. 计算距离和速度
        distance = np.linalg.norm(target_pos - current_pos)
        velocity = np.linalg.norm(robot.get_velocity())
        acceleration = compute_acceleration()
        alignment_error = compute_alignment_error(current_pos, target_pos)

        # 3. 意图检测
        intent_state, alpha = intent_detector.detect_intent(
            distance, velocity, acceleration, alignment_error
        )

        # 4. 根据状态执行不同逻辑
        if intent_state == IntentState.APPROACHING:
            # 阶段 1: 人类主导接近
            # α = 0，跟随人类指令
            joint_angles = vist_filter.solve(
                target_pos=human_target_pos,  # 人类指令
                alpha=alpha
            )

        elif intent_state == IntentState.ALIGNING:
            # 阶段 2: 算法主导对齐
            # α = 1，虚拟夹具引导
            joint_angles = vist_filter.solve(
                target_pos=target_pos,  # 目标位置
                alpha=alpha
            )

        elif intent_state == IntentState.FINE_TUNING:
            # 阶段 2.5: 人类微调
            # α = 0.3，降低虚拟夹具权重
            joint_angles = vist_filter.solve(
                target_pos=target_pos,
                alpha=alpha  # 降低的 α
            )

        elif intent_state == IntentState.INSERTING:
            # 阶段 3: 自动插入
            insertion_velocity = auto_insertion_control(current_depth)
            robot.move_with_velocity(insertion_velocity)

            # 检测插入完成
            if detect_insertion_complete(current_depth):
                intent_detector.current_state = IntentState.COMPLETED

        elif intent_state == IntentState.COMPLETED:
            # 阶段 4: 任务完成
            if detect_hand_release(hand_velocity):
                robot.open_gripper()
                robot.move_relative([0, 0, -0.05])
                break

        # 5. 发送指令
        robot.move_to(joint_angles)
```

---

## 🔑 关键优势

### 1. 人类主导接近
- ✅ 充分利用人类的空间感知能力
- ✅ 避免自动导航的复杂性
- ✅ 算法只需提供平滑跟随

### 2. 算法主导对齐
- ✅ 利用视觉精确定位
- ✅ 虚拟夹具提供"磁吸"效果
- ✅ 补偿人类手部抖动

### 3. 可选的人类微调
- ✅ 应对标定精度不足
- ✅ 检测微调意图，动态调整权重
- ✅ 保持人类的控制感

### 4. 自动插入
- ✅ 标准化的插入深度控制
- ✅ 速度自适应（越接近越慢）
- ✅ 力控制（检测阻力）

---

## 📝 总结

这个设计充分发挥了遥操作的优势：
- **人类**：提供高层决策和空间感知
- **算法**：提供精密对齐和标准化执行
- **协同**：动态权重调整，无缝切换

**最后更新**: 2026-02-09
