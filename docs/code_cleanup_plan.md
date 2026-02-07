# VIST 代码架构梳理

## 📦 核心架构（保留）

### 1. 核心算法层 (src/core/)
**保留的核心文件：**
- ✅ `vist_kalman_filter.py` - VIST 卡尔曼滤波器（核心）
- ✅ `geometric_arm_solver.py` - 几何解析求解器（核心）
- ✅ `ik_solver.py` - Pinocchio IK 求解器（用于 VIST）
- ✅ `motion_mapper.py` - 运动映射器（坐标转换）
- ✅ `one_euro_filter.py` - One Euro 滤波器（平滑）

**可删除的文件：**
- ❌ `differential_ik_solver.py` - 微分 IK（被 VIST 替代）
- ❌ `pink_ik_solver.py` - Pink IK（被 VIST 替代）
- ❌ `ik_strategies.py` - IK 策略（不再需要）
- ❌ `intent.py` - 旧的意图检测（已集成到 VIST）
- ❌ `estimator.py` - 旧的估计器（已集成到 VIST）
- ❌ `virtual.py` - 虚拟引导（已集成到 VIST）
- ❌ `dynamics.py` - 动力学（未使用）
- ❌ `coordinate_transform.py` - 旧的坐标转换（已集成到 motion_mapper）
- ⚠️ `safety_monitor.py` - 安全监控（功能已被 safe_robot_controller 替代，但可能还在用）
- ⚠️ `hand_retargeting.py` - 手部重定向（灵巧手功能，暂时保留）

### 2. 控制层 (src/control/)
**保留的核心文件：**
- ✅ `safe_robot_controller.py` - 安全控制器（核心）

### 3. 机器人驱动层 (src/robot/)
**保留的核心文件：**
- ✅ `arm_driver.py` - 真机驱动（核心）
- ✅ `sdk/` - LinkerArm SDK（核心）
- ⚠️ `viz_server.py` - 可视化服务器（调试用，可选）
- ⚠️ `hand_driver.py` - 灵巧手驱动（未来功能，暂时保留）

### 4. 感知层 (src/perception/)
**保留的核心文件：**
- ✅ `detector.py` - MediaPipe 检测器
- ✅ `camera.py` - 相机接口

### 5. 配置层 (src/config/)
**保留的核心文件：**
- ✅ `config_loader.py` - 配置加载器
- ✅ `__init__.py` - 配置接口

### 6. 视觉节点 (src/nodes/)
**保留的核心文件：**
- ✅ `vision_node_depth.py` - 深度相机视觉节点（核心）
- ❌ `arm_node.py` - 旧的控制节点（被 run_real_robot_vist.py 替代）

---

## 🚀 脚本层 (scripts/)

### 核心脚本（保留）
**真机测试：**
- ✅ `run_real_robot_vist.py` - VIST 真机控制主程序（核心）
- ✅ `test_udp_connection.py` - UDP 通信测试
- ✅ `emergency_stop_monitor.py` - 紧急停止监控
- ✅ `calibrate_zero_position.py` - 零位标定辅助

**仿真测试：**
- ✅ `simulate_full_flow.py` - VIST 仿真测试（核心）
- ✅ `run_vision.py` - 视觉节点启动脚本

**调试工具：**
- ✅ `test_geometric_solver.py` - 几何求解器测试
- ✅ `test_vist_integration.py` - VIST 集成测试

### 可删除的脚本
**旧的测试脚本：**
- ❌ `vist_teleoperation.py` - 旧的遥操作（使用微分 IK，已被 run_real_robot_vist.py 替代）
- ❌ `test_pink_ik.py` - Pink IK 测试（不再使用）
- ❌ `test_joint_mapping.py` - 关节映射测试（已验证完成）
- ❌ `test_both_directions.py` - 双向测试（已验证完成）
- ❌ `test_joint_directions.py` - 关节方向测试（已验证完成）
- ❌ `test_elbow_direction.py` - 肘部方向测试（已验证完成）
- ❌ `test_direction_logic.py` - 方向逻辑测试（已验证完成）
- ❌ `test_geometric_direction.py` - 几何方向测试（已验证完成）
- ❌ `debug_elbow_pitch.py` - 肘部调试（已修复）
- ❌ `debug_angle_offset.py` - 角度偏移调试（已修复）

**URDF 修改脚本：**
- ❌ `modify_urdf.py` - URDF 修改（已完成）
- ❌ `modify_urdf_bidirectional.py` - URDF 双向修改（已完成）
- ❌ `analyze_urdf.py` - URDF 分析（已完成）
- ❌ `test_urdf_limits.py` - URDF 限位测试（已完成）

**坐标系测试脚本：**
- ❌ `test_coordinate_transform.py` - 坐标转换测试（已验证）
- ❌ `test_coordinate_simple.py` - 简单坐标测试（已验证）
- ❌ `test_coordinate_display.py` - 坐标显示测试（已验证）
- ❌ `visualize_coordinate_system.py` - 坐标系可视化（已验证）
- ❌ `visualize_robot_frames.py` - 机器人坐标系可视化（已验证）
- ❌ `visualize_control_mapping.py` - 控制映射可视化（已验证）

**其他测试脚本：**
- ❌ `test_human_observation.py` - 人类观测测试（已集成到 VIST）
- ❌ `test_vision_depth.py` - 深度视觉测试（功能已集成）
- ❌ `check_joint_health.py` - 关节健康检查（一次性工具）
- ⚠️ `record_demo.py` - 演示录制（可能有用，暂时保留）
- ⚠️ `calibrate_system.py` - 系统标定（可能有用，暂时保留）

---

## 📊 统计

### 核心文件（必须保留）
- **src/core/**: 5 个文件
- **src/control/**: 1 个文件
- **src/robot/**: 2 个文件 + SDK
- **src/perception/**: 2 个文件
- **src/config/**: 2 个文件
- **src/nodes/**: 1 个文件
- **scripts/**: 8 个核心脚本

### 可删除文件
- **src/core/**: 7 个文件
- **src/nodes/**: 1 个文件
- **scripts/**: 23 个脚本

### 总计
- **保留**: ~21 个核心文件
- **删除**: ~31 个文件
- **清理比例**: 约 60% 的代码可以删除

---

## 🎯 建议的清理顺序

### 第 1 步：删除明确无用的测试脚本（安全）
```bash
# 已验证完成的测试脚本
rm scripts/test_joint_mapping.py
rm scripts/test_both_directions.py
rm scripts/test_joint_directions.py
rm scripts/test_elbow_direction.py
rm scripts/test_direction_logic.py
rm scripts/test_geometric_direction.py
rm scripts/debug_elbow_pitch.py
rm scripts/debug_angle_offset.py

# URDF 修改脚本（已完成）
rm scripts/modify_urdf.py
rm scripts/modify_urdf_bidirectional.py
rm scripts/analyze_urdf.py
rm scripts/test_urdf_limits.py

# 坐标系测试脚本（已验证）
rm scripts/test_coordinate_transform.py
rm scripts/test_coordinate_simple.py
rm scripts/test_coordinate_display.py
rm scripts/visualize_coordinate_system.py
rm scripts/visualize_robot_frames.py
rm scripts/visualize_control_mapping.py

# 其他测试脚本
rm scripts/test_human_observation.py
rm scripts/test_vision_depth.py
rm scripts/check_joint_health.py
```

### 第 2 步：删除旧的 IK 实现（需要确认）
```bash
# 旧的 IK 求解器（已被 VIST 替代）
rm src/core/differential_ik_solver.py
rm src/core/ik_strategies.py
rm scripts/test_pink_ik.py
rm scripts/vist_teleoperation.py  # 使用微分 IK 的旧脚本
```

### 第 3 步：删除旧的意图检测和估计器（需要确认）
```bash
# 旧的意图检测和估计器（已集成到 VIST）
rm src/core/intent.py
rm src/core/estimator.py
rm src/core/virtual.py
rm src/core/dynamics.py
rm src/core/coordinate_transform.py
```

### 第 4 步：删除旧的控制节点（需要确认）
```bash
# 旧的控制节点（已被 run_real_robot_vist.py 替代）
rm src/nodes/arm_node.py
```

---

## ⚠️ 需要确认的文件

1. **src/core/safety_monitor.py** - 功能已被 safe_robot_controller 替代，但可能还在某些脚本中使用
2. **src/core/hand_retargeting.py** - 灵巧手功能，未来可能需要
3. **src/robot/hand_driver.py** - 灵巧手驱动，未来可能需要
4. **src/robot/viz_server.py** - 可视化服务器，调试时可能需要
5. **scripts/record_demo.py** - 演示录制，可能有用
6. **scripts/calibrate_system.py** - 系统标定，可能有用

---

## 🎯 清理后的最终架构

```
VIST/
├── src/
│   ├── core/                    # 核心算法（5个文件）
│   │   ├── vist_kalman_filter.py
│   │   ├── geometric_arm_solver.py
│   │   ├── ik_solver.py
│   │   ├── motion_mapper.py
│   │   └── one_euro_filter.py
│   ├── control/                 # 控制层（1个文件）
│   │   └── safe_robot_controller.py
│   ├── robot/                   # 机器人驱动（2个文件 + SDK）
│   │   ├── arm_driver.py
│   │   └── sdk/
│   ├── perception/              # 感知层（2个文件）
│   │   ├── detector.py
│   │   └── camera.py
│   ├── config/                  # 配置层（2个文件）
│   │   ├── config_loader.py
│   │   └── __init__.py
│   └── nodes/                   # 节点层（1个文件）
│       └── vision_node_depth.py
├── scripts/                     # 脚本层（8个核心脚本）
│   ├── run_real_robot_vist.py          # 真机控制主程序
│   ├── simulate_full_flow.py           # 仿真测试
│   ├── run_vision.py                   # 视觉节点
│   ├── test_udp_connection.py          # UDP 测试
│   ├── emergency_stop_monitor.py       # 紧急停止
│   ├── calibrate_zero_position.py      # 零位标定
│   ├── test_geometric_solver.py        # 几何求解器测试
│   └── test_vist_integration.py        # VIST 集成测试
└── config/                      # 配置文件
    ├── system_config.yaml
    └── lkls73_o2_dual_arm_description.urdf
```

---

## 🚀 下一步

你想让我：
1. 直接执行删除命令？
2. 先备份再删除？
3. 逐步确认每个文件后再删除？
