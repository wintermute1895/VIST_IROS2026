# VIST 项目结构

## 📁 核心目录

### `/scripts/core/` - 核心启动脚本 ⭐
手动启动系统各组件的脚本：
- `launch_linkerta.sh` - 外骨骼节点
- `launch_filter_left_unique.sh` - 左臂滤波
- `launch_filter_right_unique.sh` - 右臂滤波
- `launch_bridge.sh` - 遥操桥接
- `check_real_robot_config.sh` - 配置检查
- `quick_verify_dataflow.sh` - 数据流验证

### `/scripts/debug/` - 调试工具
系统诊断和调试脚本：
- `check_filter_status.sh` - 滤波器状态检查
- `check_frequencies.sh` - 话题频率检查
- `check_system_status.sh` - 系统状态检查
- `diagnose_data_flow.sh` - 数据流诊断
- `debug_linkerta_data.sh` - 外骨骼数据调试
- `test_connectivity.sh` - 连接测试
- `meshcat_robot_visualizer.py` - Meshcat机器人可视化

### `/scripts/setup/` - 安装配置
第三方工具安装脚本：
- `install_foxglove.sh` - Foxglove安装
- `install_foxglove_fast.sh` - Foxglove快速安装
- `install_plotjuggler.sh` - PlotJuggler安装
- `foxglove_setup_guide.sh` - Foxglove配置指南

### `/scripts/visualization/` - 可视化工具
数据可视化相关脚本：
- `start_rqt.sh` - 启动RQT
- `start_rqt_tools.sh` - RQT工具选择器
- `start_visualization_suite.sh` - 可视化套件
- `start_robot_state_publisher.sh` - 机器人状态发布
- `restart_foxglove_bridge.sh` - 重启Foxglove桥接
- `fix_foxglove_display.sh` - 修复Foxglove显示

### `/scripts/monitoring/` - 监控工具
实时监控脚本：
- `monitor_linkerta_realtime.py` - 外骨骼实时监控

### `/scripts/testing/` - 测试脚本
系统测试和验证：
- 各种测试脚本

### `/scripts/legacy/` - 遗留代码
已弃用但保留的代码：
- `log_alpha.py` - 旧版日志工具

### `/scripts/experiment/` - 实验相关
数据采集和实验管理：
- `collect_experiment.py` - 数据采集
- `convert_rosbag_to_lerobot.py` - 格式转换
- `simulate_full_flow.py` - 完整流程仿真

### `/scripts/analysis/` - 数据分析
数据分析和可视化：
- `analyze_all_metrics.py` - 综合指标分析
- `analyze_camera_sync.py` - 相机同步分析
- `compare_trajectories_3d.py` - 轨迹对比

### `/docs/guides/` - 操作指南
系统使用文档：
- `real_robot_startup_guide.sh` - 真机启动指南
- `rqt_usage_guide.sh` - RQT使用指南

### `/docs/architecture/` - 架构文档
系统架构和设计文档：
- `CODE_REVIEW_CHECKLIST.md` - 代码审查清单
- `DUAL_ARM_README.md` - 双臂系统说明

## 📁 代码目录

### `/ros2_ws/src/nodes/` - ROS2节点
- `vist_filter_node.py` - VIST滤波节点

### `/ros2_ws/src/core/` - 核心算法
- `vist_kalman_filter.py` - VIST卡尔曼滤波器
- `baseline_filters.py` - 基线滤波器

### `/ros2_ws/src/external_sdk/` - 外部SDK
- `arm_teleop/` - 机械臂遥操作
  - `linkerta/` - LinkerTA外骨骼SDK
  - `lbot_teleop/` - LBot桥接节点
  - `lbot_driver/` - LBot驱动
- `linkerhand-ros2-sdk/` - 灵巧手SDK

## 📁 配置目录

### `/config/` - 配置文件
- `baseline_filters_config.yaml` - 滤波器配置
- `joint_directions.yaml` - 关节方向配置
- `urdf/` - 机器人模型文件

## 📁 数据目录

### `/data/` - 数据存储
- `experiments/` - 实验数据
- `archive/` - 归档数据

## 🗑️ 已删除的冗余脚本

以下一键式启动脚本已删除（不符合手动启动需求）：
- `start_full_system.sh`
- `start_vist_system.sh`
- `deploy_dual_arm_real.sh`
- `deploy_dual_arm_complete.sh`
- `test_dual_arm.sh`

以下重复脚本已删除：
- `start_linkerta.sh` (与 `launch_linkerta.sh` 重复)
- `launch_filter_left.sh` (被 `_unique` 版本替代)
- `launch_filter_right.sh` (被 `_unique` 版本替代)
- `restart_vist_node.sh`

## 🚀 快速开始

### 真机遥操作
```bash
# 终端1
cd /home/ilex/Dev/VIST/scripts/core
./launch_linkerta.sh

# 终端2
./launch_filter_left_unique.sh

# 终端3
./launch_filter_right_unique.sh

# 终端4
ros2 launch lbot_driver lbot_start_driver.launch.py

# 终端5
./launch_bridge.sh
```

### 验证系统
```bash
cd /home/ilex/Dev/VIST/scripts/core
./check_real_robot_config.sh
./quick_verify_dataflow.sh
```

### 调试问题
```bash
cd /home/ilex/Dev/VIST/scripts/debug
./check_system_status.sh
./diagnose_data_flow.sh
```

## 📝 下一步计划

根据你的需求，接下来需要：

1. **仿真集成** - 准备 `/simulation/` 目录
2. **模型训练** - 准备 `/training/` 目录
3. **项目主页** - 准备 `/web/` 前端展示
4. **软件工程优化** - 代码重构和模块化
5. **通用性优化** - 配置化和参数化

---

最后更新: 2026-03-18
