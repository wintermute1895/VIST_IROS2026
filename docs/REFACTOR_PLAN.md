# 项目重构计划 - feature/exo-hand-integration

## 当前问题分析

### 1. 代码混乱
- 38个Python脚本，很多是临时测试代码
- SDK职责不清晰（Python SDK vs ROS2 SDK）
- 没有统一的配置管理
- 实验代码分散，难以切换模式

### 2. 技术栈混合
- **视觉遥操作**: Python + VIST算法
- **外骨骼臂**: ROS2 (arm_teleop SDK) + lbot API
- **数据手套**: ROS2 (linkerhand-ros-teleop)
- **灵巧手**: Python SDK 或 ROS2 SDK (linkerhand-ros2-sdk)

### 3. 控制模式需求
- 模式1: 纯视觉 + VIST
- 模式2: 外骨骼臂 + VIST
- 模式3: 外骨骼臂 + 基线滤波
- 模式4: 外骨骼臂 + 数据手套（完整遥操作）

## 重构目标

### 1. 清晰的目录结构
```
VIST/
├── src/
│   ├── core/              # VIST核心算法（保留）
│   ├── control/           # 控制器和滤波器（保留）
│   ├── robot/
│   │   ├── arm/          # 臂控制接口（新建）
│   │   ├── hand/         # 手控制接口（新建）
│   │   └── sdk/          # 第三方SDK（整理）
│   ├── perception/        # 视觉感知（保留）
│   └── utils/            # 工具函数（保留）
├── scripts/
│   ├── experiments/      # 实验脚本（整理后）
│   ├── calibration/      # 标定脚本
│   ├── diagnostics/      # 诊断工具
│   └── deprecated/       # 废弃代码（待删除）
├── config/               # 统一配置文件
└── docs/                 # 文档
```

### 2. 统一配置系统
创建 `config/experiment_config.yaml`:
```yaml
experiment:
  mode: "exo_arm_vist"  # vision_vist | exo_arm_vist | exo_arm_baseline | exo_full

arm:
  control_type: "exoskeleton"  # exoskeleton | vision
  use_vist: true
  robot_ip: "192.168.10.21"

hand:
  control_type: "glove"  # glove | vision | none
  sdk_type: "ros2"       # ros2 | python
  can_interface: "can0"

vist:
  enable: true
  intent_mode: "velocity_based"  # velocity_based | vision_based
```

### 3. 模块化接口
创建统一的机器人接口：
```python
# src/robot/arm/arm_interface.py
class ArmInterface(ABC):
    @abstractmethod
    def connect(self): pass
    @abstractmethod
    def move_joint(self, positions): pass
    @abstractmethod
    def get_joint_positions(self): pass

# src/robot/arm/exo_arm_controller.py
class ExoArmController(ArmInterface):
    """外骨骼臂控制器（基于ROS2）"""

# src/robot/arm/vision_arm_controller.py
class VisionArmController(ArmInterface):
    """视觉臂控制器（基于视觉重定向）"""
```

## 清理计划

### 阶段1: 识别和分类（今天）

#### 保留的核心代码
**src/core/** - VIST核心算法
- ✅ `vist_kalman_filter.py` - VIST卡尔曼滤波
- ✅ `intent_detector.py` - 意图检测
- ✅ `ik_solver.py` - IK求解器
- ✅ `geometric_arm_solver.py` - 几何求解器
- ✅ `hand_retargeting.py` - 手部重定向
- ⚠️ `one_euro_filter.py` - 重复（control/filters/也有）
- ✅ `motion_mapper.py` - 运动映射
- ✅ `tcp_compensation.py` - TCP补偿
- ✅ `safety_monitor_simplified.py` - 安全监控

**src/control/** - 控制器
- ✅ `vist_controller.py` - VIST主控制器
- ✅ `threaded_vist_controller.py` - 多线程版本
- ✅ `safe_robot_controller.py` - 安全控制器
- ✅ `filters/` - 滤波器库

**src/robot/** - 机器人接口
- ✅ `arm_driver.py` - 臂驱动（需要重构）
- ✅ `hand_driver.py` - 手驱动（需要重构）
- ✅ `robot_interface.py` - 统一接口
- ✅ `sdk/` - 第三方SDK

**src/perception/** - 视觉感知
- ✅ 全部保留

**src/utils/** - 工具函数
- ✅ 全部保留

#### 需要整理的脚本

**实验脚本（保留并整理）**
- `02_teleop_run.py` → `experiments/vision_teleop.py`
- `exo_baseline_1_raw.py` → `experiments/exo_baseline.py`
- `exo_ours_filtered.py` → `experiments/exo_vist.py`
- `run_real_robot_vist_refactored.py` → `experiments/vision_vist.py`

**标定脚本（移动到calibration/）**
- `01_check_and_calibrate.py`
- `calibrate_hand_eye.py`
- `calibrate_zero_position.py`

**诊断工具（移动到diagnostics/）**
- `diagnose_dataflow.py`
- `diagnose_joint_directions.py`
- `diagnose_sim_vs_real.py`
- `debug_interface.py`

**分析工具（保留）**
- `analyze_exo_data.py`
- `ablation_velocity_estimation.py`
- `parameter_sensitivity_analysis.py`

#### 可以删除的代码

**测试脚本（临时代码）**
- ❌ `test_data_tools.py`
- ❌ `test_interpolator.py`
- ❌ `test_joint_directions_with_transforms.py`
- ❌ `test_low_pass_filter.py`
- ❌ `test_open_vs_closed_loop.py`
- ❌ `test_single_joint_mapping.py`
- ❌ `test_single_joint_vision_mapping.py`

**仿真脚本（不需要）**
- ❌ `simulate_ablation_and_escape.py`
- ❌ `simulate_alpha_validation.py`
- ❌ `simulate_full_flow.py`
- ❌ `simulate_peg_in_hole_task.py`

**重复/过时脚本**
- ❌ `02_teleop_baseline_raw.py` - 与exo_baseline重复
- ❌ `02_teleop_with_filter.py` - 与exo_ours_filtered重复
- ❌ `exo_ros2_bridge.py` - 不需要单独的桥接
- ❌ `exo_teleop_simple.py` - 简化版，不需要
- ❌ `filter_middleware_node.py` - 不需要中间件
- ❌ `glove_to_robot_bridge.py` - 话题已兼容，不需要桥接
- ❌ `safe_experiment_template.py` - 模板，不需要
- ❌ `simplified_sensitivity_analysis.py` - 与parameter_sensitivity重复
- ❌ `run_threaded_vist.py` - 已集成到主程序
- ❌ `emergency_stop_monitor.py` - 功能已集成
- ❌ `playback_vision_data.py` - 不需要
- ❌ `record_vision_data.py` - 不需要
- ❌ `run_ablation_study.py` - 实验完成后不需要

**无用的SDK**
- ❌ `src/robot/sdk/linkerhand-python-sdk-main/` - 使用ROS2版本
- ⚠️ `src/robot/sdk/linkerarm/` - 检查是否使用

### 阶段2: 重构代码结构（明天）

1. 创建新的目录结构
2. 移动和重命名文件
3. 创建统一的配置系统
4. 重构机器人接口

### 阶段3: 实现可配置实验系统（后天）

1. 创建实验启动器
2. 实现模式切换
3. 测试各种模式
4. 完善文档

## 立即行动

### 第一步：删除明确无用的代码
```bash
# 删除测试脚本
rm scripts/test_*.py
rm scripts/simulate_*.py

# 删除重复脚本
rm scripts/02_teleop_baseline_raw.py
rm scripts/02_teleop_with_filter.py
rm scripts/exo_ros2_bridge.py
rm scripts/exo_teleop_simple.py
rm scripts/filter_middleware_node.py
rm scripts/glove_to_robot_bridge.py
rm scripts/safe_experiment_template.py
rm scripts/simplified_sensitivity_analysis.py
rm scripts/run_threaded_vist.py
rm scripts/emergency_stop_monitor.py
rm scripts/playback_vision_data.py
rm scripts/record_vision_data.py
rm scripts/run_ablation_study.py

# 删除无用SDK
rm -rf src/robot/sdk/linkerhand-python-sdk-main/
```

### 第二步：创建新目录结构
```bash
mkdir -p scripts/{experiments,calibration,diagnostics,analysis}
mkdir -p src/robot/{arm,hand}
mkdir -p config
```

### 第三步：移动文件
```bash
# 移动实验脚本
mv scripts/02_teleop_run.py scripts/experiments/vision_teleop.py
mv scripts/exo_baseline_1_raw.py scripts/experiments/exo_baseline.py
mv scripts/exo_ours_filtered.py scripts/experiments/exo_vist.py
mv scripts/run_real_robot_vist_refactored.py scripts/experiments/vision_vist.py

# 移动标定脚本
mv scripts/01_check_and_calibrate.py scripts/calibration/
mv scripts/calibrate_hand_eye.py scripts/calibration/
mv scripts/calibrate_zero_position.py scripts/calibration/

# 移动诊断工具
mv scripts/diagnose_*.py scripts/diagnostics/
mv scripts/debug_interface.py scripts/diagnostics/

# 移动分析工具
mv scripts/analyze_exo_data.py scripts/analysis/
mv scripts/ablation_velocity_estimation.py scripts/analysis/
mv scripts/parameter_sensitivity_analysis.py scripts/analysis/
```

---

**准备好开始清理了吗？我可以帮你执行这些操作。**
