# 视觉模块开发路线图

## 📋 概述

基于已定义的**视觉-控制标准交互协议**，本文档提供视觉模块的分阶段开发计划。

---

## 🎯 核心设计决策

### 1. 意图因子 α 的计算位置

**决策：α 在控制端计算**

**理由：**
- α 的计算需要机器人当前状态（current_pos, velocity）
- 视觉端无法获取机器人实时状态
- 控制端的 `VISTKalmanFilter.detect_intent()` 已实现此功能

**视觉端职责：**
- 提供原始数据：target_pos, elbow_pos, shoulder_pos
- 提供置信度和追踪状态

**控制端职责：**
- 计算 α = f(distance, velocity)
- 调度观测噪声协方差 R(α)

---

## 🏗️ 接口架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Vision Module                            │
│  (MediaPipe / YOLO / DepthAI - 可替换)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ VisionPacket
                       │ - 5个关键点 (Keypoint3D)
                       │ - 时间戳、帧ID
                       │ - 置信度、追踪状态
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Safety Layer                               │
│  - 陈旧数据检测 (Stale Data)                                │
│  - 目标跳变检测 (Teleportation)                             │
│  - 遮挡处理 (Occlusion)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ SafetyCheckResult
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Vision-Control Bridge                          │
│  - 数据格式转换                                             │
│  - 异常处理和降级                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ human_kps (Dict)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ArmMotionMapper                                │
│  (已完成 ✅)                                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ target_pos, target_quat
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              VISTKalmanFilter                               │
│  (已完成 ✅)                                                │
│  - detect_intent() 计算 α                                   │
│  - solve() 输出关节角度                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 开发路线图

### 阶段 1: 基础视觉模块（MediaPipe 实现）

**目标：** 实现第一个可工作的视觉系统，验证接口设计。

**任务清单：**

#### 1.1 实现 MediaPipeVision 类
- [ ] 继承 `IVisionSystem` 抽象基类
- [ ] 实现 `initialize()`: 初始化 MediaPipe Pose 模型
- [ ] 实现 `start()`: 启动相机流（RealSense 或 USB 相机）
- [ ] 实现 `get_latest_frame()`: 返回 `VisionPacket`

**关键代码位置：**
```python
# 文件: src/vision/mediapipe_vision.py

class MediaPipeVision(IVisionSystem):
    def __init__(self, camera_type='realsense'):
        # 初始化 MediaPipe
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(...)

        # 初始化相机
        if camera_type == 'realsense':
            self.camera = RealSenseCamera()
        else:
            self.camera = USBCamera()

    def get_latest_frame(self, timeout=0.1) -> Optional[VisionPacket]:
        # 1. 获取相机帧
        color_frame, depth_frame = self.camera.get_frames()

        # 2. MediaPipe 检测
        results = self.pose.process(color_frame)

        # 3. 提取关键点
        landmarks = results.pose_landmarks.landmark
        shoulder = self._extract_keypoint(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)
        elbow = self._extract_keypoint(landmarks, mp_pose.PoseLandmark.RIGHT_ELBOW)
        wrist = self._extract_keypoint(landmarks, mp_pose.PoseLandmark.RIGHT_WRIST)
        # ...

        # 4. 深度融合（RealSense）
        shoulder_3d = self._fuse_depth(shoulder, depth_frame)
        elbow_3d = self._fuse_depth(elbow, depth_frame)
        # ...

        # 5. 坐标系转换（相机坐标系 → 肩部坐标系）
        shoulder_3d, elbow_3d, wrist_3d = self._transform_to_shoulder_frame(...)

        # 6. 构建 VisionPacket
        packet = VisionPacket(
            shoulder=Keypoint3D(shoulder_3d, confidence=shoulder.visibility),
            elbow=Keypoint3D(elbow_3d, confidence=elbow.visibility),
            wrist=Keypoint3D(wrist_3d, confidence=wrist.visibility),
            # ...
            timestamp=time.time(),
            frame_id=self.frame_count,
            tracking_status=TrackingStatus.TRACKING,
            source_algorithm="MediaPipe"
        )

        return packet
```

#### 1.2 深度融合模块
- [ ] 实现 RealSense 深度相机接口
- [ ] 实现 2D 关键点 + 深度图 → 3D 坐标
- [ ] 处理深度缺失（插值、外推）

**参考：**
- 你现有的深度融合代码（如果有）
- RealSense SDK 文档

#### 1.3 坐标系转换
- [ ] 实现相机坐标系 → 肩部坐标系的转换
- [ ] 动态归零（肩部始终在原点）
- [ ] 验证与 `ArmMotionMapper` 的坐标系一致性

**关键：**
- 肩部坐标系定义：X=up, Y=right, Z=forward
- 与 `motion_mapper.py` 中的假设一致

#### 1.4 集成测试
- [ ] 使用 `examples/vision_control_integration.py` 测试
- [ ] 验证数据流：Vision → Safety → Mapper → VIST
- [ ] 可视化关键点（RViz 或 Matplotlib）

**验收标准：**
- 能够稳定输出 30fps 的 `VisionPacket`
- 所有关键点置信度 > 0.8
- 通过安全层检查率 > 95%

---

### 阶段 2: 安全性和鲁棒性增强

**目标：** 处理真实场景中的异常情况。

**任务清单：**

#### 2.1 遮挡处理
- [ ] 实现部分遮挡检测（基于置信度）
- [ ] 实现 `last_known` 策略：使用最后有效状态
- [ ] 实现 `extrapolate` 策略：基于速度外推

**策略选择：**
```python
# 配置文件: config/system_config.yaml
vision:
  occlusion_strategy: 'last_known'  # 'reject' / 'last_known' / 'extrapolate'
  occlusion_timeout: 1.0  # 秒，超过此时间强制 reject
```

#### 2.2 跳变抑制
- [ ] 实现卡尔曼滤波（在视觉端预滤波）
- [ ] 实现 One Euro Filter（低延迟平滑）
- [ ] 可配置的滤波强度

**注意：**
- 视觉端的滤波是**预滤波**，用于去除传感器噪声
- 控制端的 VIST 滤波是**后滤波**，用于融合多源观测
- 两者互补，不冲突

#### 2.3 多相机融合（可选）
- [ ] 支持多个 RealSense 相机
- [ ] 相机外参标定
- [ ] 多视角融合（提高鲁棒性）

**架构：**
```python
class MultiCameraVision(IVisionSystem):
    def __init__(self, camera_configs: List[CameraConfig]):
        self.cameras = [RealSenseCamera(cfg) for cfg in camera_configs]

    def get_latest_frame(self, timeout=0.1) -> Optional[VisionPacket]:
        # 1. 从所有相机获取数据
        packets = [self._process_camera(cam) for cam in self.cameras]

        # 2. 融合（加权平均，基于置信度）
        fused_packet = self._fuse_packets(packets)

        return fused_packet
```

#### 2.4 性能优化
- [ ] GPU 加速（MediaPipe GPU 模式）
- [ ] 多线程（相机采集 + 处理分离）
- [ ] 延迟分析和优化（目标 < 50ms）

**性能指标：**
- 帧率: ≥ 30fps
- 端到端延迟: < 100ms（相机 → 控制指令）
- CPU 占用: < 50%

---

### 阶段 3: 高级功能和算法替换

**目标：** 支持多种视觉算法，提升精度和鲁棒性。

**任务清单：**

#### 3.1 实现 YOLO + DepthAI 方案
- [ ] 使用 YOLO 进行人体检测
- [ ] 使用 DepthAI 进行关键点估计
- [ ] 实现 `YOLOVision` 类（继承 `IVisionSystem`）

**优势：**
- 更高的检测精度
- 更好的遮挡处理
- 支持多人场景

#### 3.2 实现 OpenPose 方案（可选）
- [ ] 集成 OpenPose
- [ ] 实现 `OpenPoseVision` 类

**优势：**
- 学术界标准
- 高精度关键点

#### 3.3 算法性能对比
- [ ] 建立评估数据集
- [ ] 对比 MediaPipe vs YOLO vs OpenPose
- [ ] 指标：精度、帧率、鲁棒性

**评估指标：**
- 关键点误差（mm）
- 追踪成功率（%）
- 遮挡恢复时间（ms）

#### 3.4 自适应算法切换
- [ ] 根据场景自动选择算法
- [ ] 运行时动态切换（无缝过渡）

**示例：**
```python
class AdaptiveVision(IVisionSystem):
    def __init__(self):
        self.mediapipe = MediaPipeVision()  # 快速，低延迟
        self.yolo = YOLOVision()            # 精确，高鲁棒
        self.current_algorithm = self.mediapipe

    def get_latest_frame(self, timeout=0.1) -> Optional[VisionPacket]:
        packet = self.current_algorithm.get_latest_frame(timeout)

        # 根据置信度切换算法
        if packet.wrist.confidence < 0.5:
            print("切换到 YOLO（MediaPipe 置信度低）")
            self.current_algorithm = self.yolo

        return packet
```

---

## 📊 里程碑和验收标准

### 里程碑 1: 基础功能（2周）
- ✅ MediaPipe 视觉模块可运行
- ✅ 输出符合 `VisionPacket` 格式
- ✅ 通过集成测试

### 里程碑 2: 鲁棒性（2周）
- ✅ 遮挡处理正常工作
- ✅ 跳变抑制有效
- ✅ 安全层通过率 > 95%

### 里程碑 3: 高级功能（3周）
- ✅ 至少支持 2 种视觉算法
- ✅ 算法可无缝切换
- ✅ 性能达标（30fps, <100ms延迟）

---

## 🔧 开发工具和资源

### 必需工具
- **MediaPipe**: `pip install mediapipe`
- **RealSense SDK**: `pip install pyrealsense2`
- **OpenCV**: `pip install opencv-python`

### 可选工具
- **YOLO**: `pip install ultralytics`
- **DepthAI**: `pip install depthai`
- **OpenPose**: 需要从源码编译

### 调试工具
- **RViz**: 3D 可视化（ROS）
- **Matplotlib**: 2D 可视化
- **Rerun**: 时序数据可视化

---

## 📝 开发注意事项

### 1. 坐标系一致性
- **相机坐标系**: 通常 Z=forward, Y=down, X=right
- **肩部坐标系**: X=up, Y=right, Z=forward
- **机器人坐标系**: X=forward, Y=left, Z=up

**关键：** 在 `MediaPipeVision._transform_to_shoulder_frame()` 中正确转换。

### 2. 时间同步
- 使用 `time.time()` 作为统一时间戳
- 相机帧时间戳 vs 处理完成时间戳（选择前者）

### 3. 线程安全
- `get_latest_frame()` 必须线程安全
- 使用 `threading.Lock` 保护共享数据

### 4. 错误处理
- 相机断开：返回 `None`，不抛出异常
- 检测失败：返回 `TrackingStatus.LOST` 的数据包
- 数据异常：在安全层拦截

---

## 🎓 参考资料

### 接口文档
- `src/interfaces/vision_packet.py` - 数据契约
- `src/interfaces/vision_system.py` - 接口定义
- `src/interfaces/vision_safety.py` - 安全层

### 控制模块
- `src/core/motion_mapper.py` - 运动映射器
- `src/core/vist_kalman_filter.py` - VIST 滤波器

### 示例代码
- `examples/vision_control_integration.py` - 完整集成示例

---

## ✅ 总结

通过这个分阶段的开发计划，你可以：

1. **快速启动**：先用 MediaPipe 实现基础功能
2. **逐步增强**：添加安全性和鲁棒性
3. **灵活扩展**：支持多种视觉算法
4. **无缝集成**：与现有控制模块完美配合

**关键优势：**
- ✅ 解耦：视觉算法可替换，控制代码不变
- ✅ 安全：多层防御，异常可检测
- ✅ 可维护：清晰的接口和文档

祝开发顺利！🚀
