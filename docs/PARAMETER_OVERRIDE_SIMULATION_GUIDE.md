# VIST 参数覆盖仿真指南

## 概述

参数覆盖模式允许你在仿真中测试完整的VIST控制器效果，无需相机输入。通过手动设置意图因子α和其他参数，你可以验证VIST机制的实际效果。

## 核心功能

### 1. 参数覆盖模式

当启用`simulation_use_parameter_override`时：
- **意图因子α**：从参数覆盖管理器读取，而不是从视觉数据计算
- **完整VIST流程**：仍然运行完整的卡尔曼滤波、流形约束、协方差调度
- **实时调整**：通过debug_interface.py实时修改参数并立即看到效果

### 2. 配置方法

在`config/system_config.yaml`中：

```yaml
vist_kalman:
  # 启用参数覆盖模式（仿真专用）
  simulation_use_parameter_override: true
```

## 使用流程

### 步骤1：启动调试界面

在第一个终端中：

```bash
python scripts/debug_interface.py
```

这会启动Gradio Web界面，默认地址：`http://127.0.0.1:7860`

### 步骤2：启动仿真

在第二个终端中：

```bash
python scripts/simulate_full_flow.py
```

仿真启动时会显示：
```
✅ VIST Kalman Filter 初始化完成
   意图检测: 启用
   🎛️  参数覆盖模式: 启用（仿真专用）
      - α将从参数覆盖管理器读取，而不是从视觉数据计算
      - 可通过debug_interface.py实时调整参数
```

### 步骤3：在浏览器中打开可视化

打开MeshCat可视化界面（仿真启动时会显示URL）

### 步骤4：调整参数并观察效果

在调试界面中：

#### 实验1：测试流形约束

1. **机制层** → 启用"覆盖意图因子α"
2. 设置α = 1.0
3. 启用"应用流形约束"
4. 观察：末端应该只沿Z轴上下运动（X、Y、姿态被约束）

#### 实验2：测试协方差调度

1. 设置α = 0.0（自由移动）
   - 观察：R_human应该很小（高信任人类指令）
   - 观察：运动应该更跟随人类输入

2. 设置α = 1.0（精密操作）
   - 观察：R_human应该很大（低信任人类指令）
   - 观察：运动应该更平滑、更稳定

#### 实验3：测试多源融合

1. 调整R_human覆盖值（例如0.1）
2. 调整R_virtual覆盖值（例如0.001）
3. 观察融合效果的变化

## 状态显示

仿真运行时，每秒会打印状态信息：

```
✅ 帧数: 120 | IK成功率: 98.3% | 意图因子: 1.00 [覆盖: 1.00] | 目标位置: [0.234, -0.156, 0.789]
```

- **意图因子**：当前使用的α值
- **[覆盖: X.XX]**：显示参数覆盖值（仅在覆盖模式下显示）

## 技术细节

### 实现原理

1. **配置检查**：VISTKalmanFilter在`detect_intent()`方法开头检查`simulation_use_parameter_override`
2. **参数读取**：如果启用，从`ParameterOverrideManager`读取α值
3. **跳过计算**：跳过从视觉数据计算α的过程（几何势能、运动能量、方向对齐）
4. **保持平滑**：仍然应用EMA平滑
5. **完整流程**：Q/R调度、流形约束等机制正常运行

### 文件间通信

参数覆盖使用文件IPC：
- **文件位置**：`~/.vist_parameter_override.json`
- **更新机制**：debug_interface修改文件 → VISTKalmanFilter读取文件
- **实时性**：每次调用`detect_intent()`时重新读取

## 对比模式

### 模式1：几何IK映射（默认）

```yaml
control:
  ik_strategy: "differential"  # 或 "pink"
```

- 流程：视觉 → 映射 → IK → 可视化
- 不使用VIST控制器
- 适合测试基础运动映射

### 模式2：完整VIST控制器（参数覆盖）

```yaml
control:
  ik_strategy: "vist"

vist_kalman:
  simulation_use_parameter_override: true
```

- 流程：视觉 → 映射 → 意图检测(α覆盖) → 卡尔曼滤波 → 流形约束 → 可视化
- 使用完整VIST机制
- α由参数覆盖控制
- 适合验证VIST机制效果

### 模式3：完整VIST控制器（真实计算）

```yaml
control:
  ik_strategy: "vist"

vist_kalman:
  simulation_use_parameter_override: false
```

- 流程：视觉 → 映射 → 意图检测(计算α) → 卡尔曼滤波 → 流形约束 → 可视化
- 使用完整VIST机制
- α从视觉数据计算
- 适合真实遥操作场景

## 常见问题

### Q: 为什么调整α后没有立即看到效果？

A: 确保：
1. `simulation_use_parameter_override: true`已启用
2. 在调试界面中勾选了"覆盖意图因子α"
3. 仿真正在运行（有视觉数据输入）

### Q: 如何验证流形约束是否生效？

A:
1. 设置α = 1.0
2. 启用流形约束
3. 观察末端轨迹：应该只沿Z轴运动
4. 检查X、Y坐标：应该保持不变

### Q: 参数覆盖会影响真机运行吗？

A: 不会。参数覆盖是仿真专用功能，通过配置开关控制。真机运行时应该禁用此功能。

## 相关文档

- [参数覆盖集成指南](PARAMETER_OVERRIDE_INTEGRATION.md)
- [调试界面使用指南](DEBUG_INTERFACE_GUIDE.md)
- [VIST创新点分析](VIST_INNOVATION_AND_ELEGANCE.md)
- [任务空间流形约束实现](TASK_SPACE_MANIFOLD_CONSTRAINT_IMPLEMENTATION.md)
