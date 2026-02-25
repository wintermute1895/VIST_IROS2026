# 滤波器消融实验指南
# Filter Ablation Study Guide

## 概述

本文档说明如何使用统一的滤波器框架进行消融实验和对比试验，避免代码重复和话题碰撞问题。

## 架构重构

### 重构前的问题

```
❌ 旧架构（存在重复和冲突）:

   simple_filter_node.py
   ├── 重复实现 EMA
   └── 重复实现 One-Euro

   vist_filter_node.py
   ├── 再次重复实现 EMA
   ├── 再次重复实现 One-Euro
   └── VIST卡尔曼融合

   问题:
   1. 代码重复，维护困难
   2. 接口不统一
   3. 容易误用导致话题碰撞（多个节点发布到同一话题）
   4. 不利于消融实验的公平对比
```

### 重构后的架构

```
✅ 新架构（统一且可扩展）:

   BaseFilter (统一接口)
   ├── NoFilter (直通 - 消融对照组)
   ├── MovingAverageFilter (移动平均 - 基线)
   ├── EMAFilter (指数移动平均)
   ├── OneEuroFilterAdapter (One-Euro滤波器)
   └── VISTKalmanFilter (VIST卡尔曼融合)

   FilterFactory (工厂模式)
   └── create_filter(type, dim, **kwargs)

   unified_filter_node.py (统一节点)
   └── 使用FilterFactory创建滤波器
       支持所有滤波器类型切换

   优势:
   1. 代码复用，无重复
   2. 统一接口，易于对比
   3. 单一节点，避免话题碰撞
   4. 支持消融实验和对比试验
```

## 可用的滤波器类型

| 滤波器类型 | 描述 | 用途 | 参数 |
|-----------|------|------|------|
| `none` | 无滤波（直通） | 消融实验对照组 | 无 |
| `moving_average` | 移动平均 | 简单基线方法 | `window_size` (默认5) |
| `ema` | 指数移动平均 | 轻量级平滑 | `alpha` (默认0.3) |
| `one_euro` | One-Euro滤波器 | 自适应平滑 | `min_cutoff`, `beta`, `d_cutoff` |
| `vist_kalman` | VIST卡尔曼 | 双源融合（需使用vist_filter_node） | 见VIST配置 |

## 使用方法

### 1. 基本用法

```bash
# 启动统一滤波节点
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=one_euro \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

### 2. 消融实验：对照组（无滤波）

```bash
# 无滤波 - 作为对照组
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=none \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

### 3. 消融实验：EMA滤波

```bash
# EMA滤波 - 测试不同的alpha值
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=ema \
  -p ema_alpha:=0.3 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

### 4. 消融实验：One-Euro滤波

```bash
# One-Euro滤波 - 测试不同的参数
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=one_euro \
  -p one_euro_min_cutoff:=1.0 \
  -p one_euro_beta:=0.007 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

### 5. 对比试验：移动平均

```bash
# 移动平均 - 作为基线方法
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=moving_average \
  -p ma_window_size:=5 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

## 消融实验设计

### 实验1：滤波器类型对比

**目的**: 比较不同滤波器对控制性能的影响

**实验组**:
1. 对照组: `filter_type=none` (无滤波)
2. 基线: `filter_type=moving_average` (移动平均)
3. 实验组1: `filter_type=ema` (EMA)
4. 实验组2: `filter_type=one_euro` (One-Euro)
5. 实验组3: `filter_type=vist_kalman` (VIST卡尔曼)

**评估指标**:
- 轨迹平滑度 (Jerk)
- 跟踪误差 (RMSE)
- 响应延迟 (Latency)
- 计算开销 (CPU使用率)

### 实验2：EMA参数消融

**目的**: 研究EMA的alpha参数对性能的影响

**实验组**:
- alpha = 0.1 (强平滑)
- alpha = 0.3 (中等平滑)
- alpha = 0.5 (弱平滑)
- alpha = 0.7 (最小平滑)
- alpha = 1.0 (无平滑，等价于none)

### 实验3：One-Euro参数消融

**目的**: 研究One-Euro参数对性能的影响

**实验组**:
- min_cutoff: [0.5, 1.0, 2.0, 5.0]
- beta: [0.001, 0.007, 0.01, 0.05]

## 数据采集

### 启用性能监控

```bash
ros2 run vist unified_filter_node --ros-args \
  -p filter_type:=one_euro \
  -p enable_performance_monitoring:=true \
  -p performance_topic:=/filter_performance \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control
```

### 记录数据

```bash
# 记录输入、输出和性能指标
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /filter_performance \
  -o filter_ablation_exp1
```

## 避免话题碰撞

### ❌ 错误做法（会导致话题碰撞）

```bash
# 同时运行多个滤波节点，发布到同一话题
Terminal 1: ros2 run vist unified_filter_node -p output_topic:=/filtered
Terminal 2: ros2 run vist simple_filter_node -p output_topic:=/filtered

# 结果: 两个节点同时发布，频率叠加，可能烧毁电机！
```

### ✅ 正确做法（单一发布者）

```bash
# 方案1: 只运行一个滤波节点
ros2 run vist unified_filter_node -p filter_type:=one_euro

# 方案2: 如果需要对比，使用不同的输出话题
Terminal 1: ros2 run vist unified_filter_node \
  -p filter_type:=ema \
  -p output_topic:=/filtered_ema

Terminal 2: ros2 run vist unified_filter_node \
  -p filter_type:=one_euro \
  -p output_topic:=/filtered_one_euro

# 然后让下游节点选择订阅哪个话题
```

## 控制流集成

### 完整的控制流

```
linkerta (80Hz)
    ↓
unified_filter_node (80Hz)
    ↓ /filtered_right_joint_control
teleop_bridge (80Hz)
    ↓ /robot1/right_arm/joint_follow
lbot_driver (50Hz)
    ↓
硬件
```

### 配置teleop_bridge订阅滤波后的话题

修改 `teleop_bridge_params.yaml`:

```yaml
teleop_bridge_node:
  ros__parameters:
    master_right_topic: "/filtered_right_joint_control"  # 订阅滤波后的话题
    robot_type: "RS"
    first_move_speed: 0.2
    first_move_acce: 0.2
```

## 废弃的节点

以下节点已废弃，请勿使用:

- ❌ `simple_filter_node.py` - 代码重复，已被unified_filter_node替代
- ⚠️  `vist_filter_node.py` - 仅用于VIST卡尔曼融合（双源输入）

## 常见问题

### Q1: 为什么要重构？

A: 旧架构中simple_filter_node和vist_filter_node都重复实现了EMA和One-Euro，导致：
1. 代码维护困难
2. 容易误用导致话题碰撞
3. 不利于消融实验的公平对比

### Q2: 如何选择滤波器？

A: 根据场景选择：
- 外骨骼遥操（单源）: `one_euro` 或 `ema`
- 视觉+外骨骼（双源）: 使用 `vist_filter_node` 的 `vist_kalman`
- 消融实验: 从 `none` 开始，逐步测试各种滤波器

### Q3: VIST卡尔曼滤波器在哪里？

A: VIST卡尔曼需要双源输入（外骨骼+视觉），使用 `vist_filter_node.py`，不在unified_filter_node中。

### Q4: 如何验证没有话题碰撞？

A: 使用诊断脚本：

```bash
# 检查发布者数量
ros2 topic info /filtered_right_joint_control

# 应该只有1个发布者！
```

## 参考文献

1. Casiez, G., Roussel, N., & Vogel, D. (2012). 1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems.
2. VIST Project Documentation

---

更新日期: 2026-02-25
作者: VIST Team