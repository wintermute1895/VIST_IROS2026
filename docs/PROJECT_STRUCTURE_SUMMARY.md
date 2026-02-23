# VIST 项目结构总结 - 重构后

## 分支信息
- **当前分支**: `feature/exo-hand-integration`
- **最新提交**: dd5325d - refactor: 重构项目结构，清理无用代码
- **状态**: 已清理，结构清晰

## 目录结构

```
VIST/
├── src/                          # 源代码
│   ├── core/                     # VIST核心算法
│   │   ├── vist_kalman_filter.py        # VIST自适应卡尔曼滤波
│   │   ├── intent_detector.py           # 意图检测器
│   │   ├── ik_solver.py                 # 逆运动学求解器
│   │   ├── geometric_arm_solver.py      # 几何解析求解器
│   │   ├── hand_retargeting.py          # 手部重定向
│   │   ├── motion_mapper.py             # 运动映射器
│   │   ├── tcp_compensation.py          # TCP补偿
│   │   ├── safety_monitor_simplified.py # 安全监控
│   │   └── one_euro_filter.py           # One Euro滤波器
│   │
│   ├── control/                  # 控制器模块
│   │   ├── vist_controller.py           # VIST主控制器
│   │   ├── threaded_vist_controller.py  # 多线程VIST控制器
│   │   ├── safe_robot_controller.py     # 安全机器人控制器
│   │   ├── trajectory_interpolator.py   # 轨迹插值器
│   │   └── filters/                     # 滤波器库
│   │       ├── base_filter.py
│   │       ├── low_pass_filter.py
│   │       ├── one_euro_filter.py
│   │       └── filter_factory.py
│   │
│   ├── robot/                    # 机器人接口
│   │   ├── arm_driver.py                # 臂驱动（待重构）
│   │   ├── hand_driver.py               # 手驱动（待重构）
│   │   ├── robot_interface.py           # 统一机器人接口
│   │   ├── safety_checks.py             # 安全检查
│   │   ├── arm/                         # 臂控制接口（新建，待实现）
│   │   ├── hand/                        # 手控制接口（新建，待实现）
│   │   └── sdk/                         # 第三方SDK
│   │       ├── arm_teleop/              # 外骨骼臂SDK（lbot）
│   │       ├── linkerhand-ros-teleop-main/  # 手套SDK
│   │       ├── linkerhand-python-sdk-main/  # 手部Python SDK
│   │       ├── linkerarm/               # LinkerArm SDK
│   │       └── dex_retargeting/         # 手部重定向库
│   │
│   ├── perception/               # 视觉感知
│   │   ├── camera.py
│   │   ├── detector.py
│   │   ├── target_detector.py
│   │   └── coordinate_transform_manager.py
│   │
│   ├── communication/            # 通信模块
│   │   └── udp_receiver.py
│   │
│   ├── config/                   # 配置加载器
│   │   ├── config_loader.py
│   │   └── __init__.py
│   │
│   └── utils/                    # 工具函数
│       ├── lie_algebra.py
│       ├── data_logger.py
│       ├── hdf5_logger.py
│       ├── performance_monitor.py
│       ├── robot_watchdog.py
│       └── safety_utils.py
│
├── scripts/                      # 脚本目录（已重组）
│   ├── experiments/              # 实验脚本
│   │   ├── vision_teleop.py             # 纯视觉遥操作
│   │   ├── vision_vist.py               # 视觉+VIST
│   │   ├── exo_baseline.py              # 外骨骼基线（无VIST）
│   │   ├── exo_vist.py                  # 外骨骼+VIST
│   │   └── simulate_full_flow.py        # 完整流程仿真
│   │
│   ├── calibration/              # 标定脚本
│   │   ├── 01_check_and_calibrate.py    # 检查和标定
│   │   ├── calibrate_hand_eye.py        # 手眼标定
│   │   └── calibrate_zero_position.py   # 零位标定
│   │
│   ├── diagnostics/              # 诊断工具
│   │   ├── diagnose_dataflow.py         # 数据流诊断
│   │   ├── diagnose_joint_directions.py # 关节方向诊断
│   │   ├── diagnose_sim_vs_real.py      # 仿真vs真机诊断
│   │   └── debug_interface.py           # 调试接口
│   │
│   ├── analysis/                 # 数据分析
│   │   ├── analyze_exo_data.py          # 外骨骼数据分析
│   │   ├── ablation_velocity_estimation.py  # 速度估计消融
│   │   └── parameter_sensitivity_analysis.py  # 参数敏感性分析
│   │
│   └── *.sh                      # 启动脚本
│       ├── start_hand_sdk.sh            # 启动手部SDK
│       ├── start_teleop.sh              # 启动遥操作
│       └── setup_can.sh                 # 设置CAN接口
│
├── config/                       # 配置文件
│   ├── experiment_config.yaml           # 统一实验配置（新建）
│   ├── system_config.yaml               # 系统配置
│   ├── task.yaml                        # 任务配置
│   ├── hand_config.yaml                 # 手部配置
│   ├── ablation_config.yaml             # 消融实验配置
│   └── *.urdf                           # 机器人模型
│
├── docs/                         # 文档
│   ├── REFACTOR_PLAN.md                 # 重构计划（新建）
│   ├── CODE_STRUCTURE.md                # 代码结构
│   ├── INTEGRATION_PLAN.md              # 集成计划
│   ├── QUICK_REFERENCE.md               # 快速参考
│   └── *.md                             # 其他文档
│
├── logs/                         # 日志文件
├── data/                         # 数据文件
├── calibration_new/              # 标定工具
└── examples/                     # 示例代码

```

## 清理成果

### 删除的文件（23个）
- 7个测试脚本（test_*.py）
- 3个仿真脚本（simulate_*.py，保留simulate_full_flow.py）
- 13个重复/过时脚本

### 重组的文件（15个）
- 5个实验脚本 → `scripts/experiments/`
- 3个标定脚本 → `scripts/calibration/`
- 4个诊断工具 → `scripts/diagnostics/`
- 3个分析工具 → `scripts/analysis/`

### 新增的文件
- `config/experiment_config.yaml` - 统一实验配置系统
- `docs/REFACTOR_PLAN.md` - 详细重构计划

## 实验模式配置

通过 `config/experiment_config.yaml` 可以配置以下模式：

### 1. 纯视觉模式 (vision_vist)
```yaml
experiment:
  mode: "vision_vist"
arm:
  control_type: "vision"
  use_vist: true
hand:
  control_type: "vision"
```

### 2. 外骨骼臂+VIST (exo_arm_vist)
```yaml
experiment:
  mode: "exo_arm_vist"
arm:
  control_type: "exoskeleton"
  use_vist: true
  robot_ip: "192.168.10.21"
hand:
  control_type: "none"
```

### 3. 外骨骼臂+基线滤波 (exo_arm_baseline)
```yaml
experiment:
  mode: "exo_arm_baseline"
arm:
  control_type: "exoskeleton"
  use_vist: false
hand:
  control_type: "none"
baseline_filter:
  type: "low_pass"
  low_pass:
    alpha: 0.2
```

### 4. 完整遥操作 (exo_full)
```yaml
experiment:
  mode: "exo_full"
arm:
  control_type: "exoskeleton"
  use_vist: true
  robot_ip: "192.168.10.21"
hand:
  control_type: "glove"
  sdk_type: "ros2"
  can_interface: "can0"
```

## SDK职责划分

### 臂控制
- **外骨骼模式**: 使用 `src/robot/sdk/arm_teleop/` (ROS2)
  - 关节编码器数据 → ROS2话题 → lbot API → 机械臂
- **视觉模式**: 使用 `src/perception/` + `src/core/ik_solver.py`
  - 相机 → 手部检测 → IK → 机械臂

### 手控制
- **手套模式**: 使用 `src/robot/sdk/linkerhand-ros-teleop-main/` (ROS2)
  - 数据手套 → ROS2话题 → 手部SDK → CAN → L10手
- **视觉模式**: 使用 `src/core/hand_retargeting.py`
  - 相机 → 手部检测 → 重定向 → L10手

### 手部SDK选择
- **ROS2 SDK**: `~/Downloads/linkerhand-ros2-sdk-main/` (推荐)
  - 优点: 与ROS2生态集成，话题兼容
  - 用途: 实时控制，与外骨骼臂协同
- **Python SDK**: `src/robot/sdk/linkerhand-python-sdk-main/`
  - 优点: 纯Python，独立运行
  - 用途: 单独测试，脱离ROS2环境

## 下一步工作

### 优先级1: 实现统一的实验启动器
创建 `scripts/run_experiment.py`:
```python
# 读取config/experiment_config.yaml
# 根据mode选择对应的控制器
# 启动实验并记录数据
```

### 优先级2: 重构机器人接口
创建清晰的抽象接口：
- `src/robot/arm/arm_interface.py` - 臂控制抽象接口
- `src/robot/arm/exo_arm_controller.py` - 外骨骼臂实现
- `src/robot/arm/vision_arm_controller.py` - 视觉臂实现
- `src/robot/hand/hand_interface.py` - 手控制抽象接口
- `src/robot/hand/glove_hand_controller.py` - 手套手实现
- `src/robot/hand/vision_hand_controller.py` - 视觉手实现

### 优先级3: 完善VIST外骨骼集成
创建 `scripts/experiments/exo_vist_full.py`:
- 使用完整的VISTKalmanFilter
- 实现简化的意图检测（基于速度）
- 集成到外骨骼控制流

### 优先级4: 测试和验证
- 测试各种模式切换
- 验证数据记录
- 完善文档

## 使用指南

### 快速启动

#### 1. 外骨骼臂+VIST实验
```bash
# 修改配置
vim config/experiment_config.yaml
# 设置 mode: "exo_arm_vist"

# 启动实验
python3 scripts/experiments/exo_vist.py
```

#### 2. 完整遥操作（臂+手）
```bash
# 终端1: 启动手套节点
cd src/robot/sdk/linkerhand-ros-teleop-main/...
python3 linkerhand_retarget/handretarget.py

# 终端2: 启动手部SDK
./scripts/start_hand_sdk.sh

# 终端3: 启动外骨骼臂控制
python3 scripts/experiments/exo_vist.py
```

#### 3. 纯视觉+VIST实验
```bash
python3 scripts/experiments/vision_vist.py
```

### 数据分析
```bash
# 分析外骨骼数据
python3 scripts/analysis/analyze_exo_data.py logs/exo_*.jsonl

# 参数敏感性分析
python3 scripts/analysis/parameter_sensitivity_analysis.py
```

## 技术栈总结

### Python代码
- VIST核心算法
- 控制器
- 数据分析工具
- 手部Python SDK（可选）

### ROS2代码
- 外骨骼臂SDK（arm_teleop）
- 手套SDK（linkerhand-ros-teleop）
- 手部ROS2 SDK（linkerhand-ros2-sdk）

### 混合使用策略
- **实验脚本**: Python主程序 + ROS2订阅/发布
- **臂控制**: ROS2话题 → lbot API
- **手控制**: ROS2话题 → 手部SDK → CAN

---

**项目状态**: ✅ 结构清晰，准备开发
**下一步**: 实现统一的实验启动器和机器人接口抽象
