# 滤波器集成状态报告

**生成时间**: 2026-02-24
**目的**: 检查VIST、One-Euro、EMA等滤波算法是否已集成到机械臂遥操控制流程

---

## 执行摘要

✅ **滤波器已实现但未集成到外骨骼遥操主流程**

**当前状态**:
- ✅ VIST卡尔曼滤波器已实现 ([src/core/vist_kalman_filter.py](src/core/vist_kalman_filter.py))
- ✅ One-Euro滤波器已实现 ([src/core/one_euro_filter.py](src/core/one_euro_filter.py))
- ✅ EMA滤波器已实现 ([src/nodes/vist_filter_node.py](src/nodes/vist_filter_node.py#L209-L212))
- ✅ VIST Filter Node已实现 ([src/nodes/vist_filter_node.py](src/nodes/vist_filter_node.py))
- ❌ **外骨骼遥操主流程未使用滤波器**

---

## 详细分析

### 1. 当前外骨骼遥操控制流程

**启动脚本**: [scripts/start_arm_teleop_safe.sh](scripts/start_arm_teleop_safe.sh)

**控制流程**:
```
Linkerta外骨骼 (230Hz)
    ↓ /right_arm_joint_control
linkerta_node (ROS2)
    ↓ /right_arm_joint_control
teleop_bridge_node
    ↓ /robot1/right_arm/joint_follow
lbot_driver
    ↓ TCP/IP
LinkerArm A7 (50Hz执行)
```

**关键发现**:
- ❌ **没有滤波节点**在控制流程中
- ❌ 数据直接从外骨骼透传到机械臂
- ❌ 没有VIST、One-Euro或EMA滤波

**Launch文件**: [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py)

启动的节点:
1. `lbot_driver` - 机械臂驱动
2. `linkerta_node` - 外骨骼驱动
3. `teleop_bridge_node` - 桥接节点

**没有启动任何滤波节点！**

---

### 2. 已实现的滤波器

#### 2.1 VIST Kalman Filter

**文件**: [src/core/vist_kalman_filter.py](src/core/vist_kalman_filter.py)

**功能**:
- 自适应卡尔曼滤波
- 流形约束
- 意图因子调制
- 几何求解器融合

**状态**: ✅ 已实现，但未集成到遥操流程

---

#### 2.2 One-Euro Filter

**文件**: [src/core/one_euro_filter.py](src/core/one_euro_filter.py)

**功能**:
- 经典One-Euro滤波算法
- 速度自适应截止频率
- 低延迟噪声抑制

**状态**: ✅ 已实现，但未集成到遥操流程

---

#### 2.3 EMA Filter

**文件**: [src/nodes/vist_filter_node.py](src/nodes/vist_filter_node.py#L209-L212)

**功能**:
- 指数移动平均滤波
- 简单低通滤波

**状态**: ✅ 已实现，但未集成到遥操流程

---

### 3. VIST Filter Node (集成节点)

**文件**: [src/nodes/vist_filter_node.py](src/nodes/vist_filter_node.py)

**功能**:
- 订阅外骨骼和视觉的关节控制话题
- 支持可切换的滤波器类型 (VIST/One-Euro/EMA/Passthrough)
- 支持可配置的意图因子组合
- 发布滤波后的控制指令和性能指标

**支持的滤波器**:
```python
filter_type = 'vist_kalman'  # VIST卡尔曼滤波
filter_type = 'one_euro'     # One-Euro滤波
filter_type = 'ema'          # EMA滤波
filter_type = 'passthrough'  # 无滤波（对照组）
```

**话题订阅**:
- `/exo_left_joint_control` - 外骨骼左臂
- `/exo_right_joint_control` - 外骨骼右臂
- `/vision_left_joint_control` - 视觉左臂
- `/vision_right_joint_control` - 视觉右臂

**话题发布**:
- `/filtered_left_joint_control` - 滤波后左臂
- `/filtered_right_joint_control` - 滤波后右臂
- `/vist_performance` - 性能指标
- `/vist_intent_factors` - 意图因子

**启动脚本**: [scripts/start_vist_filter.sh](scripts/start_vist_filter.sh)

**状态**: ✅ 已实现，但**未集成到主遥操流程**

---

### 4. 视觉控制流程 (已集成VIST)

**文件**: [scripts/vist_ros2_bridge.py](scripts/vist_ros2_bridge.py)

**控制流程**:
```
视觉输入 (UDP)
    ↓
VISTController.process()
    ↓ VIST算法 (滤波+IK)
vist_ros2_bridge
    ↓ /vision_right_joint_control
high_freq_resampler (可选)
    ↓
lbot_driver
    ↓
LinkerArm A7
```

**关键发现**:
- ✅ 视觉控制流程**已集成VIST**
- ✅ 使用VISTController进行滤波和IK求解
- ✅ 支持意图检测和流形约束

**但是**: 这是**视觉控制**流程，不是**外骨骼遥操**流程！

---

## 问题诊断

### 为什么外骨骼遥操没有集成滤波器？

**可能原因**:

1. **架构分离**:
   - 外骨骼遥操使用SDK提供的标准流程
   - VIST算法主要用于视觉控制
   - 两条控制路径是独立的

2. **历史原因**:
   - 外骨骼遥操是早期实现
   - VIST算法是后期开发
   - 还没来得及集成

3. **实验设计**:
   - 可能计划用VIST Filter Node做对比实验
   - 但还没有替换主流程

---

## 集成方案

### 方案1: 修改teleop.launch.py (推荐)

**修改**: [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py)

**新的控制流程**:
```
Linkerta外骨骼 (230Hz)
    ↓ /right_arm_joint_control
linkerta_node
    ↓ /exo_right_joint_control
VIST Filter Node  ← 新增！
    ↓ /filtered_right_joint_control
teleop_bridge_node (修改订阅话题)
    ↓ /robot1/right_arm/joint_follow
lbot_driver
    ↓
LinkerArm A7
```

**修改步骤**:

1. 在teleop.launch.py中添加VIST Filter Node
2. 修改话题映射:
   - linkerta → `/exo_right_joint_control`
   - vist_filter订阅 → `/exo_right_joint_control`
   - vist_filter发布 → `/filtered_right_joint_control`
   - teleop_bridge订阅 → `/filtered_right_joint_control`

3. 支持参数切换滤波器类型:
   ```bash
   ros2 launch lbot_teleop teleop.launch.py filter_type:=vist_kalman
   ros2 launch lbot_teleop teleop.launch.py filter_type:=one_euro
   ros2 launch lbot_teleop teleop.launch.py filter_type:=ema
   ros2 launch lbot_teleop teleop.launch.py filter_type:=passthrough
   ```

---

### 方案2: 创建新的launch文件

**文件**: `teleop_with_filter.launch.py`

**优点**:
- 不修改原有流程
- 保留baseline对照组
- 便于对比实验

**缺点**:
- 需要维护两个launch文件

---

### 方案3: 使用现有的teleop_with_resampler.launch.py

**文件**: [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_resampler.launch.py)

**检查是否已经集成了滤波器**...

---

## 对比实验设计

### 实验组配置

| 实验组 | 滤波器 | Launch命令 |
|--------|--------|-----------|
| **Baseline** | 无滤波 | `ros2 launch lbot_teleop teleop.launch.py` |
| **One-Euro** | One-Euro | `ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=one_euro` |
| **EMA** | EMA | `ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=ema` |
| **VIST** | VIST Kalman | `ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=vist_kalman` |

### 数据采集

**话题记录**:
```bash
ros2 bag record \
    /right_arm_joint_control \          # 原始外骨骼数据
    /filtered_right_joint_control \     # 滤波后数据
    /robot1/right_arm/joint_states \    # 真机反馈
    /vist_performance \                 # 性能指标
    /vist_intent_factors                # 意图因子
```

---

## 行动建议

### 立即行动 (P0)

1. **检查teleop_with_resampler.launch.py**
   - 确认是否已经有滤波器集成
   - 如果有，直接使用

2. **如果没有，创建teleop_with_filter.launch.py**
   - 基于teleop.launch.py修改
   - 添加VIST Filter Node
   - 支持参数切换滤波器类型

3. **测试集成**
   - 先用passthrough模式测试（无滤波）
   - 确认数据流正常
   - 再测试各种滤波器

### 短期行动 (P1)

4. **对比实验**
   - Baseline vs One-Euro vs EMA vs VIST
   - 采集数据
   - 分析性能指标

5. **参数调优**
   - One-Euro: min_cutoff, beta
   - EMA: alpha
   - VIST: 意图因子权重

### 中期行动 (P2)

6. **论文实验**
   - 使用调优后的参数
   - 完整的对比实验
   - 统计分析

---

## 总结

**当前状态**:
- ✅ 滤波器已实现
- ✅ VIST Filter Node已实现
- ❌ **外骨骼遥操主流程未集成滤波器**

**下一步**:
1. 检查teleop_with_resampler.launch.py
2. 如果没有，创建teleop_with_filter.launch.py
3. 集成VIST Filter Node到遥操流程
4. 测试和对比实验

**预期效果**:
- 集成后可以方便地切换滤波器类型
- 支持公平的对比实验
- 为论文提供实验数据

---

## 附录: 关键文件清单

### 滤波器实现
- [src/core/vist_kalman_filter.py](src/core/vist_kalman_filter.py) - VIST卡尔曼滤波器
- [src/core/one_euro_filter.py](src/core/one_euro_filter.py) - One-Euro滤波器
- [src/nodes/vist_filter_node.py](src/nodes/vist_filter_node.py) - 滤波器集成节点

### 控制流程
- [scripts/start_arm_teleop_safe.sh](scripts/start_arm_teleop_safe.sh) - 外骨骼遥操启动脚本
- [external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py](external_sdk/arm_teleop/src/lbot_teleop/launch/teleop.launch.py) - 遥操launch文件
- [scripts/vist_ros2_bridge.py](scripts/vist_ros2_bridge.py) - 视觉控制桥接（已集成VIST）

### 启动脚本
- [scripts/start_vist_filter.sh](scripts/start_vist_filter.sh) - VIST Filter Node启动脚本

---

**结论**: 滤波器已实现但未集成到外骨骼遥操主流程，需要修改launch文件进行集成。
