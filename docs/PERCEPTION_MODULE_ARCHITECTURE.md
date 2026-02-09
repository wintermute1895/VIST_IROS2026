# VIST 感知模块架构文档

## 📋 模块概述

本模块实现 VIST (Vision-based Intent-aware State Teleoperation) 的**目标感知**部分，对应 `docs/VIST_modeling_v2.md` 的完整实现。

### 核心功能

1. **目标检测**：检测USB插口的3D位置
2. **意图感知**：基于距离和速度计算意图因子 α
3. **协方差调度**：α 驱动卡尔曼滤波参数动态调整
4. **虚拟夹具/导纳控制**：精密阶段提供引导

---

## 🏗️ 架构设计

### 完整流程

```
┌─────────────────────────────────────────────────────────────┐
│  人体姿态检测 (MediaPipe + RealSense)                       │
│  - 已集成在臂控制模块                                       │
│  - 输出: 肩、肘、腕关键点                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  运动映射 (ArmMotionMapper)                                 │
│  - 人体关键点 → 机器人目标位姿                             │
│  - 输出: target_pos, target_quat                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  目标检测 (TargetDetector) ← 本模块                        │
│  - 检测USB插口位置                                          │
│  - 输出: goal_pos, confidence                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  VIST 卡尔曼滤波 (VISTKalmanFilter)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. 意图感知 (detect_intent)                         │   │
│  │    - 输入: target_pos, goal_pos, velocity           │   │
│  │    - 输出: α ∈ [0, 1]                               │   │
│  │    - α → 0: 接近阶段（快速移动）                    │   │
│  │    - α → 1: 精密阶段（慢速微调）                    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. 协方差调度                                       │   │
│  │    - Q(α): 过程噪声（α↓ → Q↑ 信任恒速模型）        │   │
│  │    - R(α): 观测噪声（α↑ → R↑ 不信任人类指令）      │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. 虚拟夹具/导纳控制 (α → 1 时)                     │   │
│  │    - 计算朝向目标的微分IK                           │   │
│  │    - 融合人类指令和虚拟引导                         │   │
│  │    - z_total = (1-α)·z_human + α·z_goal             │   │
│  └─────────────────────────────────────────────────────┘   │
│  输出: joint_angles (7-DoF)                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  机器人驱动 (RealArmDriver)                                 │
│  - 发送关节角度到真机                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 模块组成

### 1. 目标检测模块 (`src/perception/target_detector.py`)

**抽象接口**：`ITargetDetector`
- `initialize()`: 初始化检测器
- `detect()`: 检测目标位置
- `cleanup()`: 清理资源

**实现类**：

| 检测器 | 适用场景 | 优点 | 缺点 |
|--------|---------|------|------|
| `ManualTargetDetector` | 测试、开发 | 简单、稳定 | 需要手动指定 |
| `ArUcoTargetDetector` | 快速原型 | 易部署、实时 | 需要标记 |
| `YOLOTargetDetector` | 生产环境 | 鲁棒、通用 | 需要训练模型 |

**使用示例**：
```python
from src.perception.target_detector import create_target_detector

# 方案 1: 手动指定（测试）
detector = create_target_detector(
    detector_type='manual',
    target_position=[0.35, 0.0, 0.45]
)

# 方案 2: ArUco 标记（快速原型）
detector = create_target_detector(
    detector_type='aruco',
    camera_source=0,
    marker_id=0
)

# 方案 3: YOLO（生产）
detector = create_target_detector(
    detector_type='yolo',
    model_path='usb_detector.pt'
)
```

### 2. VIST 感知控制器 (`examples/vist_perception_control.py`)

**核心类**：`VISTPerceptionController`

**功能**：
- 集成目标检测、运动映射、VIST滤波
- 处理完整的感知-控制流程
- 提供统计信息和调试输出

**使用示例**：
```python
from examples.vist_perception_control import VISTPerceptionController

controller = VISTPerceptionController(
    target_detector=detector,
    motion_mapper=mapper,
    vist_filter=vist_filter
)

# 处理一帧
joint_angles, alpha, debug_info = controller.process_frame(human_kps)
```

---

## 🎯 意图感知机制（对应 VIST_modeling_v2.md 第4节）

### 意图因子 α 的计算

**距离因子**：
```python
alpha_d = 1 / (1 + exp(-k * (d_threshold - d)))
```

**速度因子**：
```python
alpha_v = 1 / (1 + exp(-k * (v_threshold - v)))
```

**综合意图因子**：
```python
alpha = 0.5 * (alpha_d + alpha_v)
```

**物理意义**：

| α 值 | 阶段 | 距离 | 速度 | 系统行为 |
|------|------|------|------|---------|
| 0.0 | 接近 | 远 | 快 | 跟随人手，强力去噪 |
| 0.5 | 过渡 | 中 | 中 | 平衡跟随和引导 |
| 1.0 | 精密 | 近 | 慢 | 辅助对齐，提供引导 |

### 协方差调度（对应 VIST_modeling_v2.md 第5节）

**过程噪声 Q(α)**：
```python
Q(α) = Q_base * [1 + (1-α) * 9]
```
- α → 0: Q 大，信任恒速模型（人手快速移动）
- α → 1: Q 小，不信任恒速模型（人手微调或静止）

**观测噪声 R(α)**：
```python
R(α) = R_min + (R_max - R_min) * α
```
- α → 0: R 小，信任人类指令（跟随人手）
- α → 1: R 大，不信任人类指令（人手可能抖动）

---

## 🚀 快速开始

### 1. 运行完整示例

```bash
python examples/vist_perception_control.py
```

**输出示例**：
```
🚀 VIST 感知控制完整流程示例
============================================================

📦 步骤 1: 初始化组件
🎯 [ManualTarget] 初始化手动目标检测器
   目标位置: [0.35 0.   0.45]
🗺️  [ArmMotionMapper] 初始化运动映射器...
✅ 所有组件初始化完成

🔄 步骤 2: 运行控制循环（模拟数据）
------------------------------------------------------------

[帧 10] VIST 状态:
  意图因子 α: 0.234 (接近)
  目标距离: 15.3cm
  位置误差: 2.45mm

[帧 20] VIST 状态:
  意图因子 α: 0.678 (精密)
  目标距离: 5.8cm
  位置误差: 0.87mm

[帧 30] VIST 状态:
  意图因子 α: 0.912 (精密)
  目标距离: 1.2cm
  位置误差: 0.23mm

📊 步骤 3: 统计信息
------------------------------------------------------------
总帧数: 30
平均意图因子: 0.612
平均目标距离: 8.4cm

✅ 示例完成
```

### 2. 集成到真机控制

```python
# 1. 初始化组件
target_detector = create_target_detector('aruco', marker_id=0)
controller = VISTPerceptionController(...)

# 2. 主控制循环
while True:
    # 获取人体关键点（从 MediaPipe）
    human_kps = vision_node.get_keypoints()

    # VIST 感知控制
    joint_angles, alpha, debug_info = controller.process_frame(human_kps)

    # 发送到机器人
    robot.move_to(joint_angles)
```

---

## 📝 开发检查清单

### 阶段 1: 基础功能（1周）
- [x] 目标检测抽象接口
- [x] 手动目标检测器（测试用）
- [x] VIST 感知控制器
- [x] 完整流程示例
- [ ] ArUco 目标检测器实现
- [ ] 真机集成测试

### 阶段 2: 高级功能（2周）
- [ ] YOLO 目标检测器
- [ ] 手眼标定集成
- [ ] 多相机融合
- [ ] 性能优化

### 阶段 3: 实验验证（2周）
- [ ] USB插入成功率测试
- [ ] 精度测试（<1mm）
- [ ] 对比实验（vs 固定权重）
- [ ] 用户研究

---

## 🔧 配置参数

在 `config/system_config.yaml` 中配置：

```yaml
# VIST 意图感知参数
vist:
  # 意图因子计算
  distance_threshold: 0.05  # 5cm，精密模式触发距离
  velocity_threshold: 0.02  # 2cm/s，慢速移动阈值
  sigmoid_k: 20.0           # Sigmoid 陡峭度
  intent_smoothing: 0.9     # EMA 平滑系数

  # 协方差调度
  human_base_variance: 1e-2   # 人类指令基础方差
  human_max_variance: 1e-1    # 人类指令最大方差
  virtual_base_variance: 1e-2 # 虚拟引导基础方差
  virtual_min_variance: 1e-4  # 虚拟引导最小方差

# 目标检测参数
target_detection:
  detector_type: 'manual'  # 'manual', 'aruco', 'yolo'
  target_position: [0.35, 0.0, 0.45]  # 手动模式的目标位置
```

---

## 📚 参考文档

- **VIST 建模文档**: [docs/VIST_modeling_v2.md](../docs/VIST_modeling_v2.md)
- **接口协议**: [docs/vision_control_protocol.md](../docs/vision_control_protocol.md)
- **开发路线图**: [docs/vision_development_roadmap.md](../docs/vision_development_roadmap.md)

---

## 🎓 关键概念

### 1. 意图感知 (Intent Detection)
- 根据距离和速度判断操作阶段
- 输出意图因子 α ∈ [0, 1]
- α 驱动整个系统的行为

### 2. 协方差调度 (Covariance Scheduling)
- 动态调整卡尔曼滤波参数
- Q(α): 过程噪声，控制预测信任度
- R(α): 观测噪声，控制观测信任度

### 3. 虚拟夹具 (Virtual Fixture)
- 精密阶段（α → 1）提供引导
- 计算朝向目标的微分IK
- 融合人类指令和虚拟引导

---

**分支**: feature/vision-perception
**状态**: 感知模块架构完成，准备实现具体检测器
**最后更新**: 2026-02-09
