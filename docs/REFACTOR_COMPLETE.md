# VIST 架构重构完成报告

## 📋 重构概览

本次重构完成了三个核心层面的优化：

### 1. 滤波架构重构 ✅

**目标**：实现可配置的滤波架构，支持调试模式和生产模式切换

**实现**：
- 在 `config/system_config.yaml` 中添加了 `filtering` 配置节
- 支持两种滤波器：
  - `ema`: 指数移动平均（Exponential Moving Average）
  - `oneeuro`: One Euro Filter（自适应低通滤波）
- 通过 `enable_mapper_filter` 开关控制：
  - `true`: 调试模式，在 Mapper 层应用滤波，方便可视化
  - `false`: 生产模式，透传原始数据给控制节点，由 VIST 核心算法处理

**配置示例**：
```yaml
filtering:
  enable_mapper_filter: true  # 调试模式
  mapper_filter_type: "oneeuro"  # 使用 One Euro Filter
  oneeuro_min_cutoff: 0.3
  oneeuro_beta: 0.005
  oneeuro_d_cutoff: 1.0
```

**修改的文件**：
- `config/system_config.yaml`: 添加滤波配置
- `src/config/config_loader.py`: 添加配置属性访问器
- `src/core/motion_mapper.py`: 实现可配置滤波逻辑

---

### 2. 控制策略解耦 🚧

**目标**：使用策略模式支持多种 IK 算法

**设计**：
- 创建 `IKStrategy` 抽象基类
- 实现两种策略：
  - `DifferentialIKStrategy`: 基于 Pinocchio 的微分 IK（已有）
  - `PinkIKStrategy`: 基于 Pink 的多任务优化 IK（待实现）

**配置示例**：
```yaml
control:
  ik_strategy: "differential"  # 或 "pink"
  ik_damping: 1e-3
  ik_max_iter: 50
  ik_tolerance: 1e-3
```

**状态**：
- ✅ 配置文件已更新
- ✅ Config loader 已更新
- 🚧 策略模式框架已创建（`src/core/ik_strategies.py`）
- ⏳ 具体实现待完善

---

### 3. 全流程可视化仿真 ✅

**目标**：创建数字孪生仿真，验证完整控制流程

**实现**：`scripts/simulate_full_flow.py`

**功能**：
1. 接收视觉节点的 UDP 数据
2. 通过 `motion_mapper` 进行坐标转换
3. 使用 `ik_solver` 计算关节角度
4. 使用 MeshCat 进行实时 3D 可视化

**可视化元素**：
- 🤖 机器人本体：实时显示 IK 解算后的关节状态
- 🔴 红色球：目标末端（手腕）位置
- 🟢 绿色球：目标肘部位置
- 📐 坐标系：机器人基座坐标系（X=红, Y=绿, Z=蓝）
- 🌊 轨迹线：末端运动轨迹（青色）

---

## 🚀 使用方法

### 步骤 1：启动视觉节点

```bash
cd /home/ilex/Dev/VIST
python3 scripts/run_vision.py
```

### 步骤 2：启动全流程仿真

```bash
python3 scripts/simulate_full_flow.py
```

### 步骤 3：打开浏览器

仿真器会输出 MeshCat URL，例如：
```
✅ MeshCat 服务器启动: http://127.0.0.1:7000/static/
   请在浏览器中打开: http://127.0.0.1:7000/static/
```

在浏览器中打开该 URL，即可看到实时 3D 可视化。

---

## 🎯 测试要点

### 1. 滤波效果对比

**测试 A：启用 One Euro Filter**
```yaml
filtering:
  enable_mapper_filter: true
  mapper_filter_type: "oneeuro"
```

**测试 B：禁用滤波（透传模式）**
```yaml
filtering:
  enable_mapper_filter: false
```

**观察**：
- 红色球（目标手腕）的运动是否平滑？
- 是否存在抖动或跳变？
- 滤波是否引入了明显的延迟？

### 2. 坐标系验证

**测试动作**：
1. 向前伸手 → 红色球应沿 X 轴（红色）移动
2. 向左移动 → 红色球应沿 Y 轴（绿色）移动
3. 向上抬手 → 红色球应沿 Z 轴（蓝色）移动

**验证**：坐标系是否正交？方向是否正确？

### 3. IK 求解性能

**观察指标**：
- IK 成功率（应 > 95%）
- 平均帧率（应 > 20 fps）
- 目标位置与实际末端位置的误差

---

## 📊 预期效果

### 正常情况

```
✅ 帧数: 1234 | IK成功率: 98.5% | 目标位置: [0.350, -0.120, 0.850]
```

### 异常情况

**IK 失败**：
- 目标位置超出工作空间
- 奇异点附近
- 关节限位冲突

**解决方案**：
- 调整 `ik_damping` 参数（增大阻尼）
- 增加 `ik_max_iter`（更多迭代次数）
- 检查目标位置是否合理

---

## 🔧 配置调优

### 滤波参数

**One Euro Filter**：
- `min_cutoff`: 降低 → 更平滑，但延迟增加
- `beta`: 增大 → 对快速运动更敏感
- `d_cutoff`: 降低 → 速度估计更平滑

**推荐值**：
```yaml
oneeuro_min_cutoff: 0.3  # 平衡平滑度和响应性
oneeuro_beta: 0.005      # 适度响应快速运动
oneeuro_d_cutoff: 1.0    # 标准速度平滑
```

### IK 参数

**收敛性调优**：
```yaml
ik_damping: 1e-3    # 奇异点附近增大到 1e-2
ik_max_iter: 50     # 复杂姿态增加到 100
ik_tolerance: 1e-3  # 1mm 精度
```

---

## 📝 下一步工作

1. ✅ 测试全流程仿真，验证坐标系和滤波效果
2. ⏳ 完善 Pink IK 策略实现
3. ⏳ 实现 VIST 核心算法（Kalman Filter / State Estimator）
4. ⏳ 对比不同 IK 策略的性能
5. ⏳ 真机测试和参数调优

---

## 🎓 技术亮点

1. **可配置架构**：通过配置文件动态切换滤波器和 IK 策略
2. **策略模式**：解耦 IK 算法，便于扩展和对比
3. **数字孪生**：MeshCat 可视化，无需真机即可验证逻辑
4. **模块化设计**：视觉、映射、IK、控制各层职责清晰

---

## 📚 参考文档

- [One Euro Filter 论文](https://hal.inria.fr/hal-00670496/document)
- [Pinocchio 文档](https://gepettoweb.laas.fr/doc/stack-of-tasks/pinocchio/master/doxygen-html/)
- [Pink IK 库](https://github.com/stephane-caron/pink)
- [MeshCat 可视化](https://github.com/rdeits/meshcat-python)

---

**创建时间**: 2026-02-06
**作者**: Claude Sonnet 4.5
**项目**: VIST (Vision-based Intent-aware State Teleoperation)
