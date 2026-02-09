# 视觉-控制标准交互协议 (Vision-Control Interface Protocol)

## 📋 设计文档

**版本**: 1.0
**日期**: 2026-02-09
**作者**: Chief Robotics Software Architect
**状态**: 已定稿 ✅

---

## 🎯 设计目标

### 1. 解耦 (Decoupling)
- 视觉算法可替换（MediaPipe → YOLO → OpenPose）
- 控制模块无需修改一行代码
- 通过抽象接口实现策略模式

### 2. 安全性 (Safety)
- 多层防御：数据验证 + 异常检测 + 安全策略
- 异常情况可检测：陈旧、跳变、遮挡
- 支持急停触发

### 3. 可解释性 (Interpretability)
- 包含调试信息：置信度、时间戳、帧ID
- 完整的元数据：追踪状态、处理耗时、算法名称
- 支持日志和可视化

---

## 🏗️ 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    IVisionSystem                            │
│                  (抽象接口层)                                │
│                                                             │
│  + initialize() -> bool                                     │
│  + start() -> bool                                          │
│  + get_latest_frame(timeout) -> VisionPacket               │
│  + stop() -> bool                                           │
│  + cleanup() -> None                                        │
└─────────────────────────────────────────────────────────────┘
                           △
                           │ 实现
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────┴─────┐  ┌───────┴──────┐  ┌─────┴────────┐
│ MediaPipe     │  │ YOLO         │  │ OpenPose     │
│ Vision        │  │ Vision       │  │ Vision       │
└───────────────┘  └──────────────┘  └──────────────┘

                           │
                           │ 输出
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    VisionPacket                             │
│                   (数据契约)                                 │
│                                                             │
│  + shoulder: Keypoint3D                                     │
│  + elbow: Keypoint3D                                        │
│  + wrist: Keypoint3D                                        │
│  + index_mcp: Keypoint3D                                    │
│  + pinky_mcp: Keypoint3D                                    │
│  + timestamp: float                                         │
│  + frame_id: int                                            │
│  + tracking_status: TrackingStatus                          │
│  + source_algorithm: str                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 验证
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 VisionSafetyLayer                           │
│                  (安全握手层)                                │
│                                                             │
│  + check(packet) -> SafetyCheckResult                       │
│  + _check_stale_data()                                      │
│  + _check_teleportation()                                   │
│  + _check_occlusion()                                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 通过
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              VisionControlBridge                            │
│                (桥接适配层)                                  │
│                                                             │
│  + get_motion_mapper_input() -> Dict                        │
│  + get_vist_filter_input() -> Tuple                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 转换
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ArmMotionMapper (已完成)                       │
│              VISTKalmanFilter (已完成)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 数据契约 (Data Contract)

### VisionPacket 结构

```python
@dataclass
class VisionPacket:
    # ==================== 核心数据 ====================
    shoulder: Keypoint3D      # 肩部（坐标系原点）
    elbow: Keypoint3D         # 肘部
    wrist: Keypoint3D         # 腕部（末端执行器目标）
    index_mcp: Keypoint3D     # 食指掌指关节
    pinky_mcp: Keypoint3D     # 小指掌指关节

    # ==================== 元数据 ====================
    timestamp: float          # 采集时间戳（秒）
    frame_id: int             # 帧ID
    tracking_status: TrackingStatus  # 追踪状态

    # ==================== 调试信息 ====================
    source_algorithm: str     # 视觉算法名称
    processing_time: float    # 处理耗时（秒）
    debug_info: Dict          # 额外调试信息
```

### Keypoint3D 结构

```python
@dataclass
class Keypoint3D:
    position: np.ndarray      # 3D坐标 [x, y, z] (米)
    confidence: float         # 置信度 [0.0, 1.0]
    visible: bool             # 是否可见
```

### TrackingStatus 枚举

```python
class TrackingStatus(Enum):
    TRACKING = "tracking"              # 正常追踪
    LOST = "lost"                      # 目标丢失
    OCCLUDED = "occluded"              # 部分遮挡
    LOW_CONFIDENCE = "low_confidence"  # 低置信度
    INITIALIZING = "initializing"      # 初始化中
```

---

## 🔒 安全握手机制 (Safety Handshake)

### 异常检测

#### 1. 陈旧数据 (Stale Data)

**问题**: 视觉系统卡死，数据不更新

**检测方法**:
```python
def is_stale(packet: VisionPacket, max_age: float = 0.1) -> bool:
    age = time.time() - packet.timestamp
    return age > max_age
```

**处理策略**:
- `age > 100ms`: REJECT（拒绝数据）
- 连续拒绝 > 1秒: EMERGENCY_STOP（触发急停）

#### 2. 目标跳变 (Teleportation)

**问题**: 视觉误识别，坐标瞬移

**检测方法**:
```python
def check_teleportation(current_pos, last_pos, dt) -> bool:
    delta = np.linalg.norm(current_pos - last_pos)
    velocity = delta / dt

    # 检查 1: 绝对位置跳变
    if delta > 0.2:  # 20cm
        return True

    # 检查 2: 速度异常
    if velocity > 2.0:  # 2m/s
        return True

    return False
```

**处理策略**:
- 位置跳变 > 20cm: EMERGENCY_STOP
- 速度 > 2m/s: REJECT

#### 3. 遮挡 (Occlusion)

**问题**: 目标被遮挡，部分关键点不可见

**检测方法**:
```python
def check_occlusion(packet: VisionPacket) -> bool:
    return packet.tracking_status == TrackingStatus.OCCLUDED
```

**处理策略** (可配置):
- **reject**: 拒绝数据，等待恢复
- **last_known**: 使用最后已知状态（冻结）
- **extrapolate**: 基于速度外推（预测）

**配置示例**:
```yaml
vision:
  occlusion_strategy: 'last_known'
  occlusion_timeout: 1.0  # 超过1秒强制reject
```

---

## 🔑 关键设计决策

### 决策 1: 意图因子 α 的计算位置

**问题**: α 应该在视觉端计算还是控制端计算？

**分析**:
```python
# α 的计算公式（来自 vist_kalman_filter.py:222-265）
def detect_intent(target_pos, current_pos, velocity):
    distance = np.linalg.norm(target_pos - current_pos)
    speed = np.linalg.norm(velocity)

    alpha_distance = sigmoid(distance)
    alpha_velocity = sigmoid(speed)

    alpha = 0.5 * (alpha_distance + alpha_velocity)
    return alpha
```

**输入需求**:
- `target_pos`: 视觉端可提供 ✅
- `current_pos`: 机器人当前位置，只有控制端知道 ❌
- `velocity`: 机器人当前速度，只有控制端知道 ❌

**结论**: **α 必须在控制端计算**

**架构影响**:
- 视觉端：只提供原始数据 (target_pos, elbow_pos, shoulder_pos)
- 控制端：计算 α，调度观测噪声协方差 R(α)

### 决策 2: 遮挡时返回 None 还是 LastKnownState？

**问题**: 当目标被遮挡时，`get_latest_frame()` 应该返回什么？

**方案对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| 返回 None | 简单明确 | 控制端需要额外处理 |
| 返回 OCCLUDED 状态的包 | 保留元数据 | 控制端需要检查状态 |
| 返回 LastKnownState | 平滑过渡 | 可能导致延迟累积 |

**结论**: **返回带有 OCCLUDED 状态的数据包**

**理由**:
- 保留时间戳、置信度等元数据
- 安全层可以根据策略处理（reject / last_known / extrapolate）
- 控制端有完整的上下文信息

### 决策 3: 滤波器放在视觉端还是控制端？

**问题**: 数据平滑应该在哪里做？

**分析**:
- **视觉端滤波**（预滤波）：
  - 目的：去除传感器噪声（相机抖动、检测抖动）
  - 方法：One Euro Filter, 卡尔曼滤波
  - 优点：减少传输噪声，提高数据质量

- **控制端滤波**（后滤波）：
  - 目的：融合多源观测（人类指令 + 虚拟引导）
  - 方法：VIST 卡尔曼滤波
  - 优点：意图驱动，动态调整

**结论**: **两者都需要，互补而非冲突**

**架构**:
```
视觉端: 原始数据 → One Euro Filter → VisionPacket
                                        ↓
控制端: VisionPacket → VIST Kalman Filter → 关节角度
```

---

## 📊 接口方法签名

### IVisionSystem (抽象基类)

```python
class IVisionSystem(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        """初始化视觉系统（相机、模型）"""
        pass

    @abstractmethod
    def start(self) -> bool:
        """启动数据采集"""
        pass

    @abstractmethod
    def get_latest_frame(self, timeout: float = 0.1) -> Optional[VisionPacket]:
        """获取最新数据包（同步接口）"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止数据采集"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理资源"""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """检查是否运行中"""
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """获取当前帧率"""
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """获取算法名称"""
        pass
```

### VisionSafetyLayer (安全层)

```python
class VisionSafetyLayer:
    def check(self, packet: Optional[VisionPacket]) -> SafetyCheckResult:
        """执行完整的安全检查"""
        pass

    def get_last_known_state(self) -> Optional[VisionPacket]:
        """获取最后已知的有效状态"""
        pass

    def reset(self) -> None:
        """重置安全层状态"""
        pass

    def get_statistics(self) -> dict:
        """获取统计信息"""
        pass
```

### VisionControlBridge (桥接器)

```python
class VisionControlBridge:
    def start(self) -> bool:
        """启动桥接器"""
        pass

    def stop(self) -> None:
        """停止桥接器"""
        pass

    def get_safe_vision_data(self, timeout: float = 0.1) -> tuple:
        """获取经过安全检查的视觉数据"""
        pass

    def get_motion_mapper_input(self, timeout: float = 0.1) -> tuple:
        """获取 ArmMotionMapper 所需的输入"""
        pass

    def get_vist_filter_input(self, timeout: float = 0.1) -> tuple:
        """获取 VIST Kalman Filter 所需的输入"""
        pass
```

---

## 🚀 使用示例

### 基础使用

```python
# 1. 初始化组件
vision_system = MediaPipeVision()
bridge = VisionControlBridge(vision_system)
motion_mapper = ArmMotionMapper()

# 2. 启动系统
bridge.start()

# 3. 主控制循环
while True:
    # 获取安全的视觉数据
    human_kps, check_result = bridge.get_motion_mapper_input()

    # 检查安全性
    if check_result.should_stop():
        robot.emergency_stop()
        break

    if not check_result.is_safe():
        continue

    # 运动映射
    target_pos, target_quat, _ = motion_mapper.human_to_robot(human_kps)

    # VIST 滤波 + IK
    joint_angles, success, error = vist_filter.solve(
        target_pos, target_quat,
        elbow_pos=human_kps['elbow'],
        shoulder_pos=human_kps['shoulder']
    )

    # 发送到机器人
    robot.move_to(joint_angles)

# 4. 清理
bridge.stop()
```

### 算法替换

```python
# 方案 1: MediaPipe（快速原型）
vision = MediaPipeVision()

# 方案 2: YOLO（高精度）
vision = YOLOVision()

# 方案 3: OpenPose（学术标准）
vision = OpenPoseVision()

# 控制代码完全相同！
bridge = VisionControlBridge(vision)
```

---

## 📁 文件结构

```
VIST/
├── src/
│   ├── interfaces/
│   │   ├── vision_packet.py       # 数据契约
│   │   ├── vision_system.py       # 抽象接口
│   │   └── vision_safety.py       # 安全层
│   ├── vision/
│   │   ├── mediapipe_vision.py    # MediaPipe 实现
│   │   ├── yolo_vision.py         # YOLO 实现
│   │   └── openpose_vision.py     # OpenPose 实现
│   └── core/
│       ├── motion_mapper.py       # 运动映射器（已完成）
│       └── vist_kalman_filter.py  # VIST 滤波器（已完成）
├── examples/
│   └── vision_control_integration.py  # 集成示例
└── docs/
    ├── vision_development_roadmap.md  # 开发路线图
    └── vision_control_protocol.md     # 本文档
```

---

## ✅ 验收标准

### 功能性
- [ ] 支持至少 1 种视觉算法（MediaPipe）
- [ ] 输出符合 `VisionPacket` 格式
- [ ] 通过安全层检查率 > 95%
- [ ] 与 `ArmMotionMapper` 和 `VISTKalmanFilter` 无缝集成

### 性能
- [ ] 帧率 ≥ 30fps
- [ ] 端到端延迟 < 100ms
- [ ] CPU 占用 < 50%

### 鲁棒性
- [ ] 遮挡恢复时间 < 500ms
- [ ] 跳变检测准确率 > 99%
- [ ] 陈旧数据检测准确率 100%

### 可维护性
- [ ] 代码符合 PEP 8 规范
- [ ] 所有公共接口有文档字符串
- [ ] 包含单元测试和集成测试

---

## 🎓 参考资料

### 代码文件
- [vision_packet.py](../src/interfaces/vision_packet.py) - 数据契约定义
- [vision_system.py](../src/interfaces/vision_system.py) - 抽象接口定义
- [vision_safety.py](../src/interfaces/vision_safety.py) - 安全层实现
- [vision_control_integration.py](../examples/vision_control_integration.py) - 集成示例

### 文档
- [vision_development_roadmap.md](vision_development_roadmap.md) - 开发路线图
- [VIST_modeling_v2.md](VIST_modeling_v2.md) - VIST 算法建模文档

### 外部资源
- MediaPipe 文档: https://google.github.io/mediapipe/
- RealSense SDK: https://github.com/IntelRealSense/librealsense
- YOLO: https://github.com/ultralytics/ultralytics

---

## 📝 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-02-09 | 初始版本，定义核心接口和安全机制 |

---

**文档状态**: ✅ 已定稿
**下一步**: 开始实现 MediaPipe 视觉模块（参考开发路线图）
