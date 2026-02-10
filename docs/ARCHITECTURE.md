# VIST 代码架构说明

## 📁 目录结构

```
VIST/
├── src/                    # 核心源代码
│   ├── core/              # 核心算法模块
│   ├── control/           # 控制器模块
│   ├── perception/        # 感知模块
│   ├── robot/             # 机器人接口
│   ├── config/            # 配置管理
│   ├── communication/     # 通信模块
│   ├── nodes/             # ROS-like 节点
│   ├── interfaces/        # 接口定义
│   └── utils/             # 工具函数
├── config/                # 配置文件
├── calibration/           # 手眼标定
├── scripts/               # 可执行脚本
├── tests/                 # 测试文件
├── docs/                  # 文档
└── logs/                  # 日志输出

```

## 🏗️ 核心架构

### 1. 核心算法层 (src/core/)

**职责**: 实现 VIST 算法的核心逻辑

```
motion_mapper.py          # 人体→机器人运动映射（三向量算法）
ik_solver.py              # 逆运动学求解器（Pinocchio CLIK）
vist_kalman_filter.py     # VIST 卡尔曼滤波器（状态估计）
geometric_arm_solver.py   # 几何解析求解器（肘部约束）
intent_detector.py        # 意图检测器（5阶段状态机 + 冲突检测）
safety_monitor_simplified.py  # 简化安全监控器
one_euro_filter.py        # One Euro 滤波器（噪声抑制）
hand_retargeting.py       # 手部重定向
```

**数据流**:
```
人体关键点 → motion_mapper → 目标位置/姿态
                ↓
         vist_kalman_filter (融合几何求解器)
                ↓
            关节角度 (q)
```

### 2. 控制层 (src/control/)

**职责**: 封装控制逻辑，提供安全保护

```
vist_controller.py        # VIST 控制器（双模式：基础/增强）
safe_robot_controller.py  # 安全控制器（速度/加速度限制）
```

**双模式设计**:
- **基础模式** (`enable_intent_detection: false`): 直接运动映射 + IK
- **增强模式** (`enable_intent_detection: true`): 意图检测 + 冲突检测 + 状态机

### 3. 感知层 (src/perception/)

**职责**: 视觉感知和目标检测

```
camera.py                 # 相机流管理（支持 context manager）
target_detector.py        # 目标检测器（AprilTag/ArUco）
detector.py               # 人体姿态检测（MediaPipe）
```

### 4. 机器人接口层 (src/robot/)

**职责**: 与真实机器人通信

```
robot_interface.py        # 机器人接口抽象类
linkerarm_interface.py    # LinkerArm 机器人实现
sdk/                      # 机器人 SDK
```

### 5. 配置管理层 (src/config/)

**职责**: 统一配置加载和管理

```
config_loader.py          # 配置加载器（570+ 行）
system_config.yaml        # 系统配置文件
```

**配置项分类**:
- 机器人参数（URDF、关节限位、DH 参数）
- 运动映射参数（缩放比例、滤波器）
- VIST 参数（卡尔曼滤波、意图检测）
- 安全参数（速度/加速度限制）
- 增强功能开关

### 6. 通信层 (src/communication/)

**职责**: 网络通信（UDP/TCP）

```
udp_client.py             # UDP 客户端
tcp_server.py             # TCP 服务器
```

### 7. 工具层 (src/utils/)

**职责**: 通用工具函数

```
logger.py                 # 统一日志系统（新增）
coordinate_transform.py   # 坐标变换
visualization.py          # 可视化工具
```

## 🔄 数据流图

```
┌─────────────────┐
│  相机 (Camera)  │
└────────┬────────┘
         │ 图像
         ↓
┌─────────────────┐
│ 姿态检测器      │ (MediaPipe)
│ (Detector)      │
└────────┬────────┘
         │ 人体关键点
         ↓
┌─────────────────┐
│ 运动映射器      │ (三向量算法)
│ (MotionMapper)  │
└────────┬────────┘
         │ 目标位置/姿态
         ↓
┌─────────────────┐
│ VIST 控制器     │ (双模式)
│ (VISTController)│
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ↓         ↓
┌────────┐ ┌──────────┐
│基础模式│ │ 增强模式 │
└───┬────┘ └────┬─────┘
    │           │
    │      ┌────┴────┐
    │      │意图检测 │
    │      │冲突检测 │
    │      └────┬────┘
    │           │
    └─────┬─────┘
          ↓
┌─────────────────┐
│ VIST 卡尔曼滤波│ (状态估计)
│ (VISTKalman)   │
└────────┬────────┘
         │ 关节角度
         ↓
┌─────────────────┐
│ 安全控制器      │ (速度/加速度限制)
│ (SafeController)│
└────────┬────────┘
         │ 安全关节角度
         ↓
┌─────────────────┐
│ 机器人接口      │ (UDP/TCP)
│ (RobotInterface)│
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  真实机器人     │
└─────────────────┘
```

## 🎯 关键设计模式

### 1. 分层架构
- **算法层** (core): 纯算法，无硬件依赖
- **控制层** (control): 封装控制逻辑
- **接口层** (robot): 硬件抽象

### 2. 策略模式
- `VISTController` 支持双模式切换
- `TargetDetector` 支持多种检测器（AprilTag/ArUco）

### 3. 依赖注入
- `VISTKalmanFilter` 注入 `IKSolver` 和 `GeometricSolver`
- `VISTController` 注入 `Config` 对象

### 4. Context Manager
- `CameraStream` 支持 `with` 语句自动资源管理

## 📊 模块依赖关系

```
scripts/run_real_robot_vist_refactored.py
    ↓
src/control/vist_controller.py
    ↓
src/core/vist_kalman_filter.py
    ↓
src/core/ik_solver.py (Pinocchio)
```

## 🔧 可执行脚本

```
scripts/
├── run_real_robot_vist_refactored.py  # 主程序（真实机器人）
├── simulate_full_flow.py              # 仿真测试
├── calibrate_hand_eye.py              # 手眼标定
├── calibrate_zero_position.py         # 零位标定
└── emergency_stop_monitor.py          # 紧急停止监控
```

## 📝 配置文件

```
config/
├── system_config.yaml                 # 主配置文件
├── robot_arm_7dof.urdf               # 机器人模型
└── meshes/                           # 3D 模型
```

## 🧪 测试文件

```
tests/
├── test_motion_mapper.py             # 运动映射测试
├── test_ik_integration.py            # IK 集成测试
├── test_intent_detector.py           # 意图检测测试
├── test_real_hardware.py             # 真实硬件测试
└── test_simulation.py                # 仿真测试
```

## 🎨 架构优点

1. **模块化**: 每个模块职责单一，易于维护
2. **可测试**: 算法层无硬件依赖，易于单元测试
3. **可扩展**: 支持多种机器人、多种检测器
4. **向后兼容**: 双模式设计，渐进式启用新功能
5. **安全性**: 多层安全检查（SafeController + SafetyMonitor）

## ⚠️ 当前限制

1. **相机标定**: 使用硬编码内参（待实现真实标定）
2. **插入深度**: 未实现深度传感器（TODO）
3. **单线程**: 所有模块在主线程运行（可能成为性能瓶颈）
4. **日志系统**: 仅部分模块迁移到 logging

## 🚀 优化建议

### 短期优化（不影响功能）

1. **完成 logging 迁移**: 将所有模块的 print 替换为 logger
2. **添加类型注解**: 使用 Python type hints 提升代码可读性
3. **提取魔法数字**: 将硬编码值移到配置文件
4. **统一异常处理**: 定义自定义异常类

### 中期优化（小幅改动）

1. **实现相机标定**: 替换硬编码内参
2. **添加单元测试**: 使用 pytest 框架
3. **性能分析**: 使用 cProfile 识别瓶颈
4. **代码重构**: 提取重复代码到工具函数

### 长期优化（架构改进）

1. **多线程/异步**: 视觉、控制、通信分离到不同线程
2. **ROS 集成**: 迁移到 ROS2 架构
3. **GPU 加速**: 使用 CUDA 加速卡尔曼滤波
4. **分布式部署**: 视觉和控制分离到不同机器
