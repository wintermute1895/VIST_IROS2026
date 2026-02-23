# VIST 项目代码结构

## 当前分支：feature/vision-perception

### 核心模块 (src/)

#### 1. 核心算法 (src/core/)
- `vist_kalman_filter.py` - VIST自适应卡尔曼滤波器（意图驱动）
- `intent_detector.py` - 意图检测器（计算α因子）
- `ik_solver.py` - 逆运动学求解器
- `geometric_arm_solver.py` - 几何解析求解器（S-R-S构型）
- `hand_retargeting.py` - 手部重定向（dex-retargeting）
- `motion_mapper.py` - 运动映射器
- `tcp_compensation.py` - TCP补偿
- `safety_monitor_simplified.py` - 安全监控

#### 2. 控制模块 (src/control/)
- `vist_controller.py` - VIST主控制器
- `threaded_vist_controller.py` - 多线程VIST控制器
- `safe_robot_controller.py` - 安全机器人控制器
- `trajectory_interpolator.py` - 轨迹插值器
- `filters/` - 滤波器库
  - `low_pass_filter.py` - 低通滤波器
  - `one_euro_filter.py` - One Euro滤波器
  - `filter_factory.py` - 滤波器工厂

#### 3. 机器人接口 (src/robot/)
- `arm_driver.py` - 机械臂驱动
- `hand_driver.py` - 灵巧手驱动
- `robot_interface.py` - 统一机器人接口
- `safety_checks.py` - 安全检查
- `sdk/` - 第三方SDK
  - `arm_teleop/` - 外骨骼臂遥操作SDK（lbot）
  - `linkerhand-ros-teleop-main/` - 手套遥操作SDK
  - `linkerhand-python-sdk-main/` - 手部Python SDK
  - `linkerarm/` - LinkerArm SDK
  - `dex_retargeting/` - 手部重定向库

#### 4. 视觉感知 (src/perception/)
- `camera.py` - 相机接口
- `detector.py` - 检测器
- `target_detector.py` - 目标检测器
- `coordinate_transform_manager.py` - 坐标变换管理器

#### 5. 通信模块 (src/communication/)
- `udp_receiver.py` - UDP接收器

#### 6. 工具模块 (src/utils/)
- `lie_algebra.py` - 李代数工具
- `data_logger.py` - 数据记录器
- `hdf5_logger.py` - HDF5记录器
- `performance_monitor.py` - 性能监控
- `robot_watchdog.py` - 机器人看门狗
- `safety_utils.py` - 安全工具

### 脚本目录 (scripts/)

#### 外骨骼遥操作相关
- `exo_baseline_1_raw.py` - 外骨骼基线（无滤波）
- `exo_ours_filtered.py` - 外骨骼+低通滤波
- `exo_teleop_simple.py` - 简单外骨骼遥操作
- `exo_ros2_bridge.py` - 外骨骼ROS2桥接
- `filter_middleware_node.py` - 滤波中间件节点

#### 遥操作主程序
- `02_teleop_run.py` - 主遥操作程序
- `02_teleop_baseline_raw.py` - 基线遥操作（无滤波）
- `02_teleop_with_filter.py` - 带滤波的遥操作

#### 手套和手部控制
- `glove_to_robot_bridge.py` - 手套到机器人桥接
- `start_hand_sdk.sh` - 启动手部SDK脚本

#### 标定和诊断
- `01_check_and_calibrate.py` - 检查和标定
- `calibrate_hand_eye.py` - 手眼标定
- `calibrate_zero_position.py` - 零位标定
- `diagnose_dataflow.py` - 数据流诊断
- `diagnose_joint_directions.py` - 关节方向诊断
- `diagnose_sim_vs_real.py` - 仿真vs真机诊断

#### 实验和分析
- `analyze_exo_data.py` - 外骨骼数据分析
- `ablation_velocity_estimation.py` - 速度估计消融实验
- `parameter_sensitivity_analysis.py` - 参数敏感性分析

### 未跟踪的新文件

#### SDK集成
- `src/robot/sdk/arm_teleop/` - 外骨骼臂SDK（lbot）
- `src/robot/sdk/linkerhand-ros-teleop-main/` - 手套SDK

#### 新脚本
- 外骨骼相关：`exo_*.py`
- 遥操作相关：`02_teleop_*.py`
- 手套相关：`glove_to_robot_bridge.py`
- 启动脚本：`start_*.sh`

### 外部SDK
- `~/Downloads/linkerhand-ros2-sdk-main/` - 原生手部SDK（已配置）

## 系统架构

### 当前实现的功能
1. ✅ 视觉遥操作（基于相机的手部跟踪）
2. ✅ VIST算法（意图驱动的自适应滤波）
3. ✅ 外骨骼臂遥操作（基于关节编码器）
4. ✅ 手套数据采集（LinkerHand数据手套）
5. ⚠️ 手部SDK集成（已配置，待测试）

### 待集成的功能
1. 🔲 完整VIST接入外骨骼控制流
2. 🔲 手套+手部SDK的完整数据流
3. 🔲 臂+手的统一遥操作系统
4. 🔲 数据采集和实验评估

## 下一步计划

### 新分支建议：feature/exo-hand-integration

目标：集成外骨骼臂+数据手套的完整遥操作系统

#### 需要完成的任务
1. 将外骨骼相关代码提交到新分支
2. 实现完整VIST接入外骨骼控制流
3. 测试手套+手部SDK的数据流
4. 创建统一的启动脚本
5. 完善数据记录和分析工具

#### 代码组织
- 保持核心VIST算法在 `src/core/`
- 外骨骼特定代码放在 `src/robot/exoskeleton/`
- 手套特定代码放在 `src/robot/glove/`
- 集成脚本放在 `scripts/integration/`