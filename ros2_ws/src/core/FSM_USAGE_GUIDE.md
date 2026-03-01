# FSM 相对增量映射版本 - 使用指南

## 概述

本次重构实现了基于**全过程相对增量映射**的虚拟夹具 FSM，彻底消除了启动抖动问题。

## 核心改进

### 1. 全局锚点机制（Global Anchor）
- **启动时立即记录**：FSM 第一次运行时，立即记录 `initial_exo` 和 `initial_robot`
- **消除启动抖动**：所有自由态运动都基于全局锚点进行增量计算
- **公式**：`P_target = P_initial_robot + 1.0 × (P_exo - P_initial_exo)`

### 2. 状态锚点机制（State Anchor）
- **状态切换时记录**：进入粘滞态时，记录当前的外骨骼和机械臂位姿
- **防止切换跳变**：粘滞态运动基于状态锚点进行增量计算
- **公式**：
  - `P_target.xy = P_anchor.xy + 0.2 × (P_exo.xy - P_anchor_exo.xy)`
  - `P_target.z = P_anchor.z + 1.0 × (P_exo.z - P_anchor_exo.z)`

### 3. 接口变化

#### 旧接口（已废弃）
```python
target_position, current_state = fsm.update(
    exo_position=exo_position,      # 仅位置 [x, y, z]
    robot_flange_position=robot_flange_position,  # 仅位置 [x, y, z]
    dt=dt
)
```

#### 新接口（推荐）
```python
target_pose, current_state = fsm.update(
    exo_pose=exo_pose,              # 完整位姿 [x, y, z, rx, ry, rz]
    current_robot_pose=current_robot_pose  # 完整位姿 [x, y, z, rx, ry, rz]
)
```

## 在 ROS Node 中的使用

### 方式 1：使用外部 SDK 的 FK 结果（推荐）

如果你的 ROS Node 可以通过外部 SDK 获取机械臂的实时法兰位姿，请使用这种方式：

```python
# 在 vist_filter_node.py 中

def timer_callback(self):
    """控制循环回调"""

    # 1. 获取外骨骼关节角（从话题订阅）
    exo_joint_angles = self.exo_data.position  # [q1, q2, ..., q7]

    # 2. 通过外部 SDK 获取机械臂当前法兰位姿（推荐方式）
    # 例如：调用 LBOT SDK 的 FK 接口
    robot_flange_pose = self.get_robot_flange_pose_from_sdk()  # [x, y, z, rx, ry, rz]

    # 3. 调用滤波器更新（传入 robot_flange_pose）
    filtered_joint_angles = self.filter.update(
        q_in=exo_joint_angles,
        dt=dt,
        robot_flange_pose=robot_flange_pose  # 传入外部 FK 结果
    )

    # 4. 发布滤波后的关节角
    self.publish_filtered_command(filtered_joint_angles)


def get_robot_flange_pose_from_sdk(self) -> np.ndarray:
    """
    通过外部 SDK 获取机械臂当前法兰位姿

    Returns:
        robot_flange_pose: [x, y, z, rx, ry, rz]
    """
    # 示例：调用 LBOT SDK
    # from external_sdk.arm_teleop import LBotArmController
    # flange_pose = self.lbot_controller.get_current_flange_pose()

    # 或者从 ROS 话题订阅机械臂状态
    # robot_state = self.robot_state_subscriber.get_latest_state()
    # flange_pose = robot_state.flange_pose

    # 临时示例：返回零位姿（实际使用时需要替换）
    return np.array([0.5, 0.0, 0.3, 0.0, 0.0, 0.0])
```

### 方式 2：使用内部 FK 计算（备用）

如果无法获取外部 FK 结果，滤波器会自动使用上一次的输出关节角计算当前法兰位姿：

```python
# 在 vist_filter_node.py 中

def timer_callback(self):
    """控制循环回调"""

    # 1. 获取外骨骼关节角
    exo_joint_angles = self.exo_data.position

    # 2. 调用滤波器更新（不传入 robot_flange_pose）
    # 滤波器会自动使用上一次的输出关节角计算当前法兰位姿
    filtered_joint_angles = self.filter.update(
        q_in=exo_joint_angles,
        dt=dt
        # robot_flange_pose 参数省略
    )

    # 3. 发布滤波后的关节角
    self.publish_filtered_command(filtered_joint_angles)
```

## 配置文件

配置文件 `config/baseline_filters_config.yaml` 已包含所需参数，无需修改：

```yaml
fsm:
  # 圆柱形结界配置
  socket_center_xy: [0.42, -0.11]      # 插座中心的 XY 坐标 [x, y] (单位: m)
  cylinder_radius: 0.15                # 圆柱形结界半径 (单位: m)

  # 运动缩放比例
  xy_scale_factor: 0.2                 # 粘滞态下的 XY 轴缩放比例 (0.2 = 1:5 微缩)
  z_scale_factor: 1.0                  # 粘滞态下的 Z 轴缩放比例 (1.0 = 1:1 保持)
```

## 关键特性

### ✅ NO IK in FSM
- FSM 模块仅生成笛卡尔空间的目标位姿
- IK 求解在包装器（`FSMTeleopFilter`）中完成

### ✅ FK Only in FSM
- FSM 接收外部提供的机械臂当前真实法兰位姿
- 通过外部 SDK 的 FK 接口获取（推荐）
- 或使用内部 FK 计算（备用）

### ✅ 全过程相对增量映射
- 启动时立即记录全局锚点
- 自由态：基于全局锚点的 1:1 增量映射
- 粘滞态：基于状态锚点的 XY 微缩 + Z 保持
- **禁止绝对映射**，彻底消除启动抖动

## 调试信息

FSM 会输出详细的调试信息，帮助你理解运行状态：

```
[FSM] ✓ 全局锚点已初始化
  初始外骨骼位姿: [0.5000, 0.0000, 0.3000]
  初始机械臂位姿: [0.5000, 0.0000, 0.3000]

[FSM Debug] ==================
  外骨骼位姿: [0.5100, 0.0100, 0.3100]
  机械臂位姿: [0.5050, 0.0050, 0.3050]
  插座中心 XY: [0.4200, -0.1100]
  到中心距离: 0.1500m (阈值: 0.1500m)
  当前状态: 自由态
    [自由态] 1:1 相对增量映射:
      全局锚点-外骨骼: [0.5000, 0.0000, 0.3000]
      全局锚点-机械臂: [0.5000, 0.0000, 0.3000]
      外骨骼增量: [0.0100, 0.0100, 0.0100]
      目标位姿: [0.5100, 0.0100, 0.3100]
  目标位姿: [0.5100, 0.0100, 0.3100]
  位姿增量: [0.0050, 0.0050, 0.0050]
  增量范数: 0.0087m
```

## 文件清单

1. **FSM 核心类**：`ros2_ws/src/core/vitual_fixture_fsm.py`（新文件）
2. **包装器**：`ros2_ws/src/filters.py`（已修改）
3. **配置文件**：`config/baseline_filters_config.yaml`（无需修改）
4. **使用指南**：`ros2_ws/src/core/FSM_USAGE_GUIDE.md`（本文件）

## 注意事项

1. **文件名拼写**：新的 FSM 文件名为 `vitual_fixture_fsm.py`（保持与你的命名一致）
2. **导入路径**：`filters.py` 已更新导入路径为 `from src.core.vitual_fixture_fsm import VirtualFixtureFSM`
3. **接口兼容性**：`update` 方法新增了可选参数 `robot_flange_pose`，向后兼容
4. **推荐使用方式**：优先使用外部 SDK 的 FK 结果，以获得最准确的机械臂位姿反馈

## 测试建议

1. **启动测试**：观察启动时是否有剧烈抖动（应该没有）
2. **自由态测试**：在结界外移动，观察是否平滑跟随
3. **粘滞态测试**：进入结界内，观察 XY 轴是否微缩，Z 轴是否保持 1:1
4. **状态切换测试**：反复进出结界，观察是否有跳变（应该没有）

## 常见问题

### Q: 如何获取机械臂的实时法兰位姿？
A: 推荐通过外部 SDK 的 FK 接口获取，例如 LBOT SDK 的 `get_current_flange_pose()` 方法。如果无法获取，滤波器会自动使用内部 FK 计算。

### Q: 为什么启动时还是有轻微抖动？
A: 检查是否正确传入了 `robot_flange_pose` 参数。如果使用内部 FK 计算，第一次调用时会使用外骨骼位姿作为初始值，可能会有轻微偏差。

### Q: 如何调整粘滞态的缩放比例？
A: 修改配置文件中的 `xy_scale_factor` 和 `z_scale_factor` 参数。例如，`xy_scale_factor: 0.2` 表示 1:5 微缩。

---

**作者**: VIST Team
**日期**: 2026-02-28
**版本**: 相对增量映射重构版本
