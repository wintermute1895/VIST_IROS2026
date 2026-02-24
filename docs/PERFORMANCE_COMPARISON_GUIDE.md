# 性能对比测试完整指南

## 概述

本指南说明如何使用你现有的节点（纯视觉控制 + 仿真）与遥操臂进行性能对比，验证插值效果。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    纯视觉控制流程                              │
└─────────────────────────────────────────────────────────────┘

视觉节点 (vision_node_depth.py)
    ↓ UDP (原始关键点数据)
仿真脚本 (simulate_full_flow.py)
    ├─> 运动映射 (motion_mapper)
    ├─> IK求解 (ik_solver)
    ├─> VIST滤波 (可选)
    └─> ROS2发布 (/vision_control/joint_follow, ~30Hz)


┌─────────────────────────────────────────────────────────────┐
│                    遥操臂控制流程                              │
└─────────────────────────────────────────────────────────────┘

遥操臂硬件
    ↓ 原始数据
遥操臂驱动 (lbot_teleop)
    └─> ROS2发布 (/left_joint_follow, ~241.75Hz)


┌─────────────────────────────────────────────────────────────┐
│                    数据对比分析                                │
└─────────────────────────────────────────────────────────────┘

rosbag记录
    ↓
分析脚本 (analyze_all_metrics.py)
    ├─> 插值到统一时间轴 (250Hz)
    ├─> 计算性能指标 (Jerk, 速度, 加速度)
    └─> 生成对比图表
```

## 快速开始

### 方案A：仅测试纯视觉控制（推荐先做）

**不需要连接真机，可以验证数据流是否正常**

```bash
# 步骤1：修改 simulate_full_flow.py 添加ROS2发布
# 参考 docs/ADD_ROS2_TO_SIMULATION.md

# 步骤2：启动视觉节点（终端1）
python3 src/nodes/vision_node_depth.py

# 步骤3：启动仿真脚本（终端2）
python3 scripts/experiments/simulate_full_flow.py

# 步骤4：验证数据（终端3）
ros2 topic echo /vision_control/joint_follow
ros2 topic hz /vision_control/joint_follow  # 应该是 ~30Hz
```

### 方案B：完整对比测试（需要真机）

```bash
# 使用快速测试脚本
./scripts/quick_comparison_test.sh

# 选择模式3：完整对比测试
# 然后在其他终端启动各个节点
```

## 详细步骤

### 1. 准备工作

**修改 simulate_full_flow.py**：

按照 [docs/ADD_ROS2_TO_SIMULATION.md](ADD_ROS2_TO_SIMULATION.md) 的说明，在三个地方添加代码：
1. 导入 `SimulationPublisherWrapper`
2. 在 `__init__` 中初始化发布器
3. 在 `run` 方法中发布数据

**配置文件**：

在 `config/system_config.yaml` 中确认：
```yaml
simulation_enable_ros2_publish: true
vision_fps: 30.0
```

### 2. 启动纯视觉控制

**终端1 - 视觉节点**：
```bash
source /opt/ros/humble/setup.bash
python3 src/nodes/vision_node_depth.py
```

**终端2 - 仿真脚本**：
```bash
source /opt/ros/humble/setup.bash
source external_sdk/arm_teleop/install/setup.bash
python3 scripts/experiments/simulate_full_flow.py
```

**验证**：
```bash
# 终端3
ros2 topic list | grep vision_control
# 应该看到：
#   /vision_control/joint_follow
#   /vision_control/joint_states

ros2 topic hz /vision_control/joint_follow
# 应该显示 ~30 Hz
```

### 3. 启动遥操臂（如果有真机）

**终端4**：
```bash
./scripts/start_arm_teleop.sh
```

**验证**：
```bash
ros2 topic hz /left_joint_follow
# 应该显示 ~241.75 Hz
```

### 4. 记录数据

```bash
# 终端5
ros2 bag record \
  /vision_control/joint_follow \
  /left_joint_follow \
  -o data/comparison_tests/test_$(date +%Y%m%d_%H%M%S)

# 运行10-30秒后按 Ctrl+C 停止
```

### 5. 分析数据

```bash
./scripts/run_analysis.sh \
  --rosbag data/comparison_tests/test_YYYYMMDD_HHMMSS \
  --config config/analysis_config.yaml \
  --output data/analysis/comparison
```

## 预期结果

### 数据频率

| 数据源 | 频率 | 说明 |
|--------|------|------|
| 纯视觉控制 | ~30 Hz | 视觉检测频率 |
| 遥操臂 | ~241.75 Hz | 硬件采样频率 |
| 插值后 | 250 Hz | 统一时间轴 |

### 性能指标

**成功标准**：
- ✅ 插值RMSE < 0.001 rad
- ✅ 纯视觉控制Jerk > 遥操臂Jerk（因为频率低）
- ✅ 两者轨迹趋势一致

**如果VIST滤波有效**：
- ✅ 滤波后Jerk显著降低
- ✅ 保持250Hz输出频率
- ✅ 延迟 < 50ms

## 故障排查

### 问题1：simulate_full_flow.py 没有发布数据

**检查**：
```bash
ros2 topic list | grep vision_control
```

**解决**：
1. 确认已按照 ADD_ROS2_TO_SIMULATION.md 修改代码
2. 检查终端输出是否有 "✅ ROS2发布器初始化完成"
3. 确认已source ROS2环境

### 问题2：找不到 lbot_arm_interfaces

**解决**：
```bash
cd external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
```

### 问题3：视觉节点没有输出

**检查**：
```bash
# 监听UDP端口
python3 scripts/check_node_data.py udp 5005
```

**解决**：
1. 确认摄像头已连接
2. 检查UDP端口配置
3. 查看视觉节点终端输出

### 问题4：频率不对

**检查**：
```bash
ros2 topic hz /vision_control/joint_follow
ros2 topic hz /left_joint_follow
```

**预期**：
- 纯视觉: 25-35 Hz
- 遥操臂: 230-250 Hz

如果频率异常，检查：
1. 系统负载（CPU/GPU）
2. 网络延迟（UDP）
3. ROS2 QoS设置

## 下一步

### 1. 添加VIST滤波

修改数据流，在中间插入VIST滤波节点：

```
纯视觉控制 → VIST滤波器 → /filtered_joint_control (250Hz)
```

参考：[docs/HIGH_FREQ_CONTROL_PLAN.md](HIGH_FREQ_CONTROL_PLAN.md)

### 2. 连接真机测试

将滤波后的数据发送到真机：

```bash
# 启动VIST滤波节点
./scripts/start_vist_filter.sh

# 连接真机
# (需要修改真机控制节点订阅 /filtered_joint_control)
```

### 3. 运行消融实验

对比不同滤波器的效果：

```bash
python3 scripts/run_ablation_experiments.py
```

参考：[docs/ABLATION_STUDY_GUIDE.md](ABLATION_STUDY_GUIDE.md)

## 相关文档

- [现有节点接入指南](EXISTING_NODES_INTEGRATION.md)
- [添加ROS2到仿真](ADD_ROS2_TO_SIMULATION.md)
- [轨迹对比测试](TRAJECTORY_COMPARISON_TEST.md)
- [高频控制计划](HIGH_FREQ_CONTROL_PLAN.md)
- [消融实验指南](ABLATION_STUDY_GUIDE.md)

## 常见问题

**Q: 为什么要用 simulate_full_flow 而不是直接用 vision_node？**

A: vision_node 只输出原始关键点数据，simulate_full_flow 包含完整的控制流程：
- 运动映射
- IK求解
- VIST滤波（可选）
- 安全控制

这样才能得到可以直接与遥操臂对比的关节角度数据。

**Q: 可以不连接真机测试吗？**

A: 可以！先测试纯视觉控制的数据流，验证：
- ROS2发布正常
- 数据格式正确
- 频率符合预期

然后再连接真机进行完整对比。

**Q: 插值会不会影响数据真实性？**

A: 插值是必要的，因为：
1. 两个数据源频率不同（30Hz vs 241.75Hz）
2. 需要统一时间轴才能对比
3. 使用三次样条插值，精度很高（RMSE < 0.001 rad）

这是标准的数据分析方法，不会"造假"。

---

**最后更新**: 2026-02-24