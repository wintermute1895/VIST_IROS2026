# VIST 系统数据流与架构文档

## 📊 概述

本文档详细描述 VIST 系统的数据流、模块间接口和信息传递机制。

**作者**: VIST Research Team
**日期**: 2026-02-10
**版本**: v2.0

---

## 🏗️ 系统架构

### 层次化架构

```
┌─────────────────────────────────────────────────────────────┐
│                        应用层 (Application)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  RealRobotVIST / SimulationVIST                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        控制层 (Control)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  VISTController                                      │   │
│  │  ├─ 基础模式 (_process_basic)                        │   │
│  │  └─ 增强模式 (_process_enhanced)                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        算法层 (Algorithm)                     │
│  ┌──────────────┬──────────────┬──────────────────────┐   │
│  │MotionMapper  │IntentDetector│ VISTKalmanFilter     │   │
│  │              │              │ ├─ GeometricSolver   │   │
│  │              │              │ └─ IKSolver          │   │
│  └──────────────┴──────────────┴──────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        感知层 (Perception)                    │
│  ┌──────────────┬──────────────┬──────────────────────┐   │
│  │ MediaPipe    │TargetDetector│ OneEuroFilter        │   │
│  │ (Hand Track) │ (AprilTag)   │ (Signal Processing)  │   │
│  └──────────────┴──────────────┴──────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        硬件层 (Hardware)                      │
│  ┌──────────────┬──────────────┬──────────────────────┐   │
│  │ Camera       │ Robot        │ Safety Monitor       │   │
│  └──────────────┴──────────────┴──────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 完整数据流

### 主数据流 (基础模式)

```
[相机] → 图像 (H×W×3)
   ↓
[MediaPipe] → 人体关键点 {shoulder, elbow, wrist, index, pinky}
   ↓
[OneEuroFilter] → 滤波后关键点 (降噪)
   ↓
[MotionMapper] → (target_pos, target_quat, elbow_pos)
   ↓
[VISTKalmanFilter] → Δθ (关节角度增量)
   ↓
[IKSolver] → θ_solution (关节角度)
   ↓
[SafetyController] → θ_safe (安全关节角度)
   ↓
[机器人] → 执行运动
```

### 增强数据流 (增强模式)

```
[相机] → 图像 (H×W×3)
   ↓
   ├─→ [MediaPipe] → 人体关键点
   │      ↓
   │   [OneEuroFilter] → 滤波后关键点
   │      ↓
   │   [MotionMapper] → (human_target_pos, human_target_quat)
   │      ↓
   │   [compute_human_command] → v_human (人类指令向量)
   │
   └─→ [TargetDetector] → target_socket_pos (目标位置)
          ↓
       [compute_algorithm_expectation] → v_algo (算法期望向量)
          ↓
       [IntentDetector] → (state, α, β, α_eff)
          ↓
       [_generate_target_from_intent] → (target_pos, target_quat)
          ↓
       [VISTKalmanFilter] → Δθ (使用 α_eff 调制)
          ↓
       [IKSolver] → θ_solution
          ↓
       [SafetyController] → θ_safe
          ↓
       [SimplifiedSafetyMonitor] → θ_final (兜底检查)
          ↓
       [机器人] → 执行运动
```

---

## 📦 数据结构定义

### 1. 人体关键点 (Human Keypoints)

```python
human_keypoints = {
    'shoulder': np.ndarray,  # shape: (3,), 肩部位置 [x, y, z]
    'elbow': np.ndarray,     # shape: (3,), 肘部位置
    'wrist': np.ndarray,     # shape: (3,), 腕部位置
    'index_mcp': np.ndarray, # shape: (3,), 食指掌指关节
    'pinky_mcp': np.ndarray  # shape: (3,), 小指掌指关节
}
```

**坐标系**: 相机坐标系 (右手系，Z 轴向前)

**单位**: 米 (m)

---

### 2. 运动映射输出 (Motion Mapping Output)

```python
result = (target_pos, target_quat, mapper_debug)

target_pos: np.ndarray    # shape: (3,), 目标位置 [x, y, z]
target_quat: np.ndarray   # shape: (4,), 目标姿态四元数 [qw, qx, qy, qz]
mapper_debug: dict = {
    'elbow_pos': np.ndarray,      # shape: (3,), 肘部位置
    'shoulder_pos': np.ndarray,   # shape: (3,), 肩部位置
    'rotation_matrix': np.ndarray # shape: (3, 3), 旋转矩阵
}
```

**坐标系**: 机器人基座坐标系

---

### 3. 意图检测结果 (Intent Detection Result)

```python
@dataclass
class IntentDetectionResult:
    state: IntentState           # 当前状态 (枚举)
    alpha: float                 # 基础意图因子 [0, 1]
    beta: float                  # 冲突因子 [0, 1]
    alpha_effective: float       # 有效意图因子 [0, 1]
    distance: float              # 距离目标的距离 (m)
    velocity: float              # 当前速度 (m/s)
    alignment_error: float       # 对齐误差 (m)
    confidence: float            # 置信度 [0, 1]
```

**状态枚举**:
```python
class IntentState(Enum):
    APPROACHING = "approaching"              # 接近
    VISUAL_ADMITTANCE = "visual_admittance"  # 视觉导纳
    CORRECTION_OVERRIDE = "correction_override"  # 修正接管
    CONSTRAINED_INSERTION = "constrained_insertion"  # 约束插入
    RELEASE = "release"                      # 释放
```

---

### 4. VIST 卡尔曼滤波器状态 (VIST Kalman State)

```python
state = {
    'x': np.ndarray,      # shape: (14,), 状态向量 [θ, θ̇]
    'P': np.ndarray,      # shape: (14, 14), 协方差矩阵
    'Q': np.ndarray,      # shape: (14, 14), 过程噪声
    'R': np.ndarray,      # shape: (14, 14), 观测噪声
    'alpha': float,       # 当前意图因子
    'iteration': int      # 迭代次数
}
```

---

### 5. 安全控制器输出 (Safety Controller Output)

```python
q_safe, safety_status = safety_controller.process_command(q_solution)

q_safe: np.ndarray  # shape: (7,), 安全的关节角度
safety_status: dict = {
    'emergency_stop': bool,           # 是否紧急停止
    'velocity_limited': bool,         # 是否速度受限
    'acceleration_limited': bool,     # 是否加速度受限
    'joint_limit_violated': bool,     # 是否关节限位违规
    'max_velocity': float,            # 最大速度 (rad/s)
    'max_acceleration': float         # 最大加速度 (rad/s²)
}
```

---

## 🔌 模块接口定义

### 1. MotionMapper

**输入**:
```python
human_keypoints: dict  # 人体关键点
```

**输出**:
```python
(target_pos, target_quat, mapper_debug): tuple
```

**方法**:
```python
def human_to_robot(self, human_keypoints: dict) -> Optional[tuple]:
    """
    将人体关键点映射到机器人目标位姿

    Returns:
        (target_pos, target_quat, debug_info) 或 None (失败)
    """
```

---

### 2. IntentDetector

**输入**:
```python
distance: float              # 距离目标的距离
velocity: float              # 当前速度
human_command: np.ndarray    # 人类指令向量 (3,)
algorithm_expectation: np.ndarray  # 算法期望向量 (3,)
alignment_error: float       # 对齐误差
current_depth: float         # 当前插入深度
```

**输出**:
```python
IntentDetectionResult  # 意图检测结果
```

**方法**:
```python
def detect_intent(
    self,
    distance: float,
    velocity: float,
    human_command: np.ndarray,
    algorithm_expectation: np.ndarray,
    alignment_error: float,
    current_depth: float
) -> IntentDetectionResult:
    """检测当前意图状态和冲突程度"""
```

---

### 3. VISTKalmanFilter

**输入**:
```python
target_pos: np.ndarray       # 目标位置 (3,)
target_quat: np.ndarray      # 目标姿态 (4,)
q_init: np.ndarray           # 初始关节角度 (7,)
elbow_pos: np.ndarray        # 肘部位置 (3,)
shoulder_pos: np.ndarray     # 肩部位置 (3,)
alpha: float                 # 意图因子 [0, 1]
```

**输出**:
```python
(q_solution, success, error): tuple
q_solution: np.ndarray  # shape: (7,), 求解的关节角度
success: bool           # 是否成功
error: float            # 末端误差 (m)
```

**方法**:
```python
def solve(
    self,
    target_pos: np.ndarray,
    target_quat: np.ndarray,
    q_init: np.ndarray,
    elbow_pos: Optional[np.ndarray] = None,
    shoulder_pos: Optional[np.ndarray] = None,
    alpha: float = 0.5
) -> Tuple[np.ndarray, bool, float]:
    """VIST 卡尔曼滤波求解"""
```

---

### 4. GeometricArmSolver

**输入**:
```python
target_pos: np.ndarray       # 目标位置 (3,)
target_quat: np.ndarray      # 目标姿态 (4,)
elbow_pos: np.ndarray        # 肘部位置 (3,)
shoulder_pos: np.ndarray     # 肩部位置 (3,)
```

**输出**:
```python
(q_solution, success): tuple
q_solution: np.ndarray  # shape: (7,), 关节角度
success: bool           # 是否成功
```

**方法**:
```python
def solve(
    self,
    target_pos: np.ndarray,
    target_quat: np.ndarray,
    elbow_pos: np.ndarray,
    shoulder_pos: np.ndarray
) -> Tuple[np.ndarray, bool]:
    """几何解析求解 IK"""
```

---

## 📈 数据流时序图

### 基础模式时序

```
时间 →

t0: [相机采集] → 图像
t1: [MediaPipe] → 关键点提取 (30ms)
t2: [OneEuro] → 滤波 (1ms)
t3: [MotionMapper] → 运动映射 (2ms)
t4: [VISTKalman] → IK 求解 (5ms)
t5: [Safety] → 安全检查 (1ms)
t6: [机器人] → 执行 (10ms)

总延迟: ~50ms (20Hz)
```

### 增强模式时序

```
时间 →

t0: [相机采集] → 图像
t1: [MediaPipe] → 关键点提取 (30ms)
    [AprilTag] → 目标检测 (10ms, 并行)
t2: [OneEuro] → 滤波 (1ms)
t3: [MotionMapper] → 运动映射 (2ms)
t4: [IntentDetector] → 意图检测 (2ms)
t5: [VISTKalman] → IK 求解 (5ms)
t6: [Safety] → 安全检查 (2ms)
t7: [机器人] → 执行 (10ms)

总延迟: ~60ms (16Hz)
```

---

## 🔀 控制流程图

### 基础模式控制流

```
┌─────────────┐
│  获取图像    │
└──────┬──────┘
       ↓
┌─────────────┐
│ 关键点提取   │
└──────┬──────┘
       ↓
┌─────────────┐
│  信号滤波    │
└──────┬──────┘
       ↓
┌─────────────┐
│  运动映射    │
└──────┬──────┘
       ↓
┌─────────────┐
│ VIST 求解   │
└──────┬──────┘
       ↓
┌─────────────┐
│  安全检查    │
└──────┬──────┘
       ↓
┌─────────────┐
│  执行运动    │
└─────────────┘
```

### 增强模式控制流

```
┌─────────────┐
│  获取图像    │
└──────┬──────┘
       ↓
   ┌───┴───┐
   ↓       ↓
┌──────┐ ┌──────┐
│关键点│ │目标  │
│提取  │ │检测  │
└───┬──┘ └──┬───┘
    ↓       ↓
┌───┴───────┴───┐
│  信号滤波      │
└────────┬───────┘
         ↓
┌────────────────┐
│  运动映射      │
└────────┬───────┘
         ↓
┌────────────────┐
│ 计算人类指令   │
│ 计算算法期望   │
└────────┬───────┘
         ↓
┌────────────────┐
│  意图检测      │
│  冲突检测      │
└────────┬───────┘
         ↓
┌────────────────┐
│ 生成目标位姿   │
│ (状态机)       │
└────────┬───────┘
         ↓
┌────────────────┐
│ VIST 求解      │
│ (使用 α_eff)   │
└────────┬───────┘
         ↓
┌────────────────┐
│  安全检查      │
│  (双层保护)    │
└────────┬───────┘
         ↓
┌────────────────┐
│  执行运动      │
└────────────────┘
```

---

## 🔧 配置数据流

### 配置加载流程

```
system_config.yaml
       ↓
VISTConfig (config_loader.py)
       ↓
   ┌───┴───┬───────┬──────────┐
   ↓       ↓       ↓          ↓
Motion  VIST   Intent    Safety
Mapper  Kalman Detector  Monitor
```

### 配置参数传递

```python
# 1. 加载配置
config = get_config()

# 2. 传递给各模块
mapper = ArmMotionMapper()  # 使用默认配置
vist_filter = VISTKalmanFilter(ik_solver, config)
intent_detector = EnhancedIntentDetector(config)
safety_monitor = SimplifiedSafetyMonitor(config.max_velocity)
```

---

## 📊 性能指标

### 计算时间分布

| 模块 | 平均时间 | 最大时间 | 占比 |
|------|---------|---------|------|
| MediaPipe | 30ms | 50ms | 60% |
| MotionMapper | 2ms | 5ms | 4% |
| IntentDetector | 2ms | 3ms | 4% |
| VISTKalman | 5ms | 10ms | 10% |
| GeometricSolver | 0.5ms | 1ms | 1% |
| SafetyController | 1ms | 2ms | 2% |
| 其他 | 10ms | 15ms | 20% |
| **总计** | **50ms** | **86ms** | **100%** |

### 数据吞吐量

| 数据类型 | 大小 | 频率 | 带宽 |
|---------|------|------|------|
| 图像 | 640×480×3 = 921KB | 30Hz | 27MB/s |
| 关键点 | 5×3×4B = 60B | 30Hz | 1.8KB/s |
| 关节角度 | 7×4B = 28B | 30Hz | 0.84KB/s |
| 调试信息 | ~1KB | 30Hz | 30KB/s |

---

## 🔍 调试数据流

### 调试信息结构

```python
debug_info = {
    # 基础信息
    'mode': str,                    # 'basic' 或 'enhanced'
    'target_pos': np.ndarray,       # 目标位置
    'target_elbow': np.ndarray,     # 肘部位置
    'ik_error': float,              # IK 误差 (m)

    # 增强模式特有
    'intent_state': str,            # 意图状态
    'alpha': float,                 # 基础意图因子
    'beta': float,                  # 冲突因子
    'alpha_effective': float,       # 有效意图因子
    'target_detected': bool,        # 是否检测到目标
    'safety_warning': str,          # 安全警告

    # 安全信息
    'safety_status': dict,          # 安全状态
}
```

### 日志数据流

```
[VISTController] → logger.info()
       ↓
[Logger] → 格式化
       ↓
   ┌───┴───┐
   ↓       ↓
Console  File
(实时)  (logs/*.log)
```

---

## 🚀 优化建议

### 1. 并行化

**当前**: 串行处理
**改进**: 并行处理关键点提取和目标检测

```python
with ThreadPoolExecutor() as executor:
    future_keypoints = executor.submit(mediapipe.process, image)
    future_target = executor.submit(apriltag.detect, image)

    keypoints = future_keypoints.result()
    target = future_target.result()
```

**预期收益**: 延迟降低 10-15ms

### 2. 数据缓存

**当前**: 每次重新计算
**改进**: 缓存不变的计算结果

```python
@lru_cache(maxsize=128)
def compute_rotation_matrix(quat):
    # 缓存四元数到旋转矩阵的转换
    pass
```

### 3. 批处理

**当前**: 逐帧处理
**改进**: 批量处理多帧

```python
# 批量 IK 求解
q_solutions = vist_filter.solve_batch(target_poses)
```

---

## ✅ 总结

### 数据流特点

1. **层次化**: 清晰的层次结构，模块解耦
2. **可扩展**: 易于添加新模块（如力觉传感器）
3. **高效**: 关键路径优化，实时性强
4. **鲁棒**: 多层安全检查，容错性好

### 接口设计原则

1. **类型安全**: 使用 NumPy 数组，明确 shape
2. **错误处理**: 返回 Optional，明确失败情况
3. **调试友好**: 丰富的 debug_info
4. **文档完善**: 每个接口有详细说明

---

**最后更新**: 2026-02-10
**作者**: VIST Research Team
**版本**: v2.0
