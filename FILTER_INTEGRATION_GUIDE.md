# 外骨骼遥操 + 滤波器集成使用指南

**创建时间**: 2026-02-24
**目的**: 将VIST、One-Euro、EMA滤波器集成到外骨骼遥操控制流程，支持对比实验

---

## 快速开始

### 1. Baseline实验（无滤波）

```bash
cd /home/ilex/Dev/VIST
./scripts/start_arm_teleop_with_filter.sh --filter passthrough
```

### 2. One-Euro滤波实验

```bash
./scripts/start_arm_teleop_with_filter.sh --filter one_euro
```

### 3. EMA滤波实验

```bash
./scripts/start_arm_teleop_with_filter.sh --filter ema
```

### 4. VIST完整算法实验

```bash
./scripts/start_arm_teleop_with_filter.sh --filter vist_kalman
```

---

## 控制流程对比

### 原始流程（无滤波）

```
Linkerta外骨骼 (230Hz)
    ↓ /right_arm_joint_control
linkerta_node
    ↓ /right_arm_joint_control
teleop_bridge_node
    ↓ /robot1/right_arm/joint_follow
lbot_driver
    ↓ TCP/IP
LinkerArm A7 (50Hz执行)
```

### 新流程（集成滤波器）

```
Linkerta外骨骼 (230Hz)
    ↓ /right_arm_joint_control
linkerta_node
    ↓ /exo_right_joint_control  ← 重映射
VIST Filter Node (可切换类型)  ← 新增！
    ↓ /filtered_right_joint_control
teleop_bridge_node
    ↓ /robot1/right_arm/joint_follow
lbot_driver
    ↓ TCP/IP
LinkerArm A7 (50Hz执行)
```

---

## 滤波器说明

### Passthrough（无滤波）

**用途**: Baseline对照组

**特点**:
- 直接透传外骨骼数据
- 无任何滤波处理
- 保留所有高频震颤

**预期性能**:
- RMS Jerk: ~170 rad/s³（最高）
- 成功率: 低
- 认知负荷: 高

---

### One-Euro Filter

**用途**: 经典滤波方法对比

**特点**:
- 速度自适应截止频率
- 低延迟噪声抑制
- 参数: min_cutoff=1.0, beta=0.007

**预期性能**:
- RMS Jerk: ~120 rad/s³
- 成功率: 中等
- 认知负荷: 中等

**参考文献**:
```
Casiez, G., Roussel, N., & Vogel, D. (2012).
1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems.
In Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (pp. 2527-2530).
```

---

### EMA（指数移动平均）

**用途**: 简单滤波方法对比

**特点**:
- 固定平滑系数
- 简单低通滤波
- 参数: alpha=0.3

**预期性能**:
- RMS Jerk: ~100 rad/s³
- 成功率: 中等
- 认知负荷: 中等
- 延迟: 较高

---

### VIST Kalman Filter

**用途**: 完整VIST算法

**特点**:
- 自适应卡尔曼滤波
- 流形约束
- 意图驱动的权重调制
- 零空间高频抑制

**预期性能**:
- RMS Jerk: ~60-80 rad/s³（最低）
- 成功率: 高
- 认知负荷: 低（NASA-TLX）

---

## 数据采集

### 采集命令

```bash
# 创建数据目录
mkdir -p ~/Dev/VIST/data/filter_comparison_$(date +%Y%m%d_%H%M%S)
cd ~/Dev/VIST/data/filter_comparison_$(date +%Y%m%d_%H%M%S)

# 记录所有相关话题
ros2 bag record \
    /exo_right_joint_control \          # 原始外骨骼数据
    /filtered_right_joint_control \     # 滤波后数据
    /robot1/right_arm/joint_states \    # 真机反馈
    /vist_performance \                 # 性能指标
    /vist_intent_factors \              # 意图因子（仅VIST）
    -o filter_comparison_${FILTER_TYPE}
```

### 采集话题说明

| 话题 | 频率 | 内容 | 用途 |
|------|------|------|------|
| `/exo_right_joint_control` | ~230Hz | 外骨骼原始数据 | 分析输入震颤 |
| `/filtered_right_joint_control` | ~100Hz | 滤波后数据 | 分析滤波效果 |
| `/robot1/right_arm/joint_states` | ~50Hz | 真机反馈 | 分析实际执行 |
| `/vist_performance` | ~100Hz | 性能指标 | 实时Jerk/速度/加速度 |
| `/vist_intent_factors` | ~100Hz | 意图因子 | VIST算法分析 |

---

## 实验协议

### 实验任务

**任务1: USB插入**
- 重复次数: 20次/滤波器
- 评估指标: SR, CT, NJ

**任务2: 积木堆叠**
- 重复次数: 20次/滤波器
- 评估指标: SR, CT, NJ

**任务3: 3D打印件插入**
- 间隙: 0.5mm, 1.0mm, 2.0mm
- 重复次数: 20次/间隙/滤波器
- 评估指标: SR vs 容差

### 实验顺序（随机化）

```python
import random

filters = ['passthrough', 'one_euro', 'ema', 'vist_kalman']
tasks = ['usb_insertion', 'block_stacking', '3d_print_insertion']

# 随机化顺序（避免学习效应）
experiment_order = []
for task in tasks:
    task_filters = filters.copy()
    random.shuffle(task_filters)
    for filter_type in task_filters:
        experiment_order.append((task, filter_type))

print("实验顺序:")
for i, (task, filter_type) in enumerate(experiment_order, 1):
    print(f"{i}. {task} - {filter_type}")
```

### 数据分析

```bash
# 分析单个rosbag
python3 scripts/analyze_filter_performance.py \
    data/filter_comparison_20260224/filter_comparison_passthrough

# 对比分析
python3 scripts/compare_filters.py \
    data/filter_comparison_20260224/
```

---

## 参数调优

### One-Euro Filter

```bash
# 调优min_cutoff
./scripts/start_arm_teleop_with_filter.sh --filter one_euro

# 修改参数（需要修改launch文件）
# one_euro_min_cutoff: [0.5, 1.0, 2.0, 5.0]
# one_euro_beta: [0.001, 0.007, 0.01, 0.05]
```

### EMA Filter

```bash
# 调优alpha
# ema_alpha: [0.1, 0.2, 0.3, 0.4, 0.5]
```

### VIST Kalman Filter

```bash
# 调优意图因子权重
# 修改 config/system_config.yaml
```

---

## 性能监控

### 实时查看性能指标

```bash
# 终端1: 启动系统
./scripts/start_arm_teleop_with_filter.sh --filter vist_kalman

# 终端2: 监控性能
ros2 topic echo /vist_performance

# 输出格式: [velocity_norm, acceleration_norm, jerk_norm, max_joint_vel, max_joint_acc]
```

### 实时查看意图因子（仅VIST）

```bash
ros2 topic echo /vist_intent_factors

# 输出格式: [alpha]
# alpha=0: 完全人类控制
# alpha=1: 完全算法控制
```

---

## 故障排查

### 问题1: VIST Filter Node启动失败

**症状**:
```
[ERROR] [vist_filter_node]: Failed to initialize
```

**解决**:
```bash
# 检查VIST项目路径
ls /home/ilex/Dev/VIST/src/nodes/vist_filter_node.py

# 检查Python路径
echo $PYTHONPATH

# 手动添加路径
export PYTHONPATH=/home/ilex/Dev/VIST:$PYTHONPATH
```

---

### 问题2: 话题没有数据

**症状**:
```bash
ros2 topic echo /filtered_right_joint_control
# 无输出
```

**诊断**:
```bash
# 检查话题列表
ros2 topic list | grep filtered

# 检查节点状态
ros2 node list

# 检查话题连接
ros2 topic info /filtered_right_joint_control
```

---

### 问题3: 滤波器延迟过高

**症状**: 机械臂响应明显滞后

**解决**:
```bash
# 降低滤波强度
# One-Euro: 增大min_cutoff
# EMA: 增大alpha
# VIST: 检查output_freq_hz
```

---

## 对比实验检查清单

### 实验前

- [ ] 所有滤波器已实现并测试
- [ ] Launch文件已创建并验证
- [ ] 数据采集脚本已准备
- [ ] 实验顺序已随机化
- [ ] 硬件已检查（电机、网络、外骨骼）
- [ ] 安全措施已到位（急停、工作空间清理）

### 实验中

- [ ] 每次实验前记录滤波器类型
- [ ] 每次实验记录rosbag
- [ ] 每次实验记录成功/失败
- [ ] 每次实验记录完成时间
- [ ] 每次实验后填写NASA-TLX问卷
- [ ] 实验间休息（避免疲劳）

### 实验后

- [ ] 所有rosbag已保存
- [ ] 所有元数据已记录
- [ ] 数据完整性已验证
- [ ] 初步分析已完成
- [ ] 异常数据已标记

---

## 预期结果

### 性能指标对比

| 滤波器 | RMS Jerk | 成功率 | 完成时间 | NASA-TLX |
|--------|----------|--------|----------|----------|
| Passthrough | 170 | 60% | 基线 | 高 |
| One-Euro | 120 | 75% | +10% | 中 |
| EMA | 100 | 70% | +20% | 中 |
| VIST | 60-80 | 90% | +5% | 低 |

### 统计检验

```python
# 使用配对t检验
from scipy import stats

# VIST vs Baseline
t_stat, p_value = stats.ttest_rel(vist_jerk, baseline_jerk)
print(f"VIST vs Baseline: t={t_stat:.3f}, p={p_value:.4f}")

# 显著性: p < 0.05
```

---

## 论文图表

### 图1: Jerk对比

```python
import matplotlib.pyplot as plt

filters = ['Passthrough', 'One-Euro', 'EMA', 'VIST']
jerk_values = [170, 120, 100, 70]

plt.bar(filters, jerk_values)
plt.ylabel('RMS Jerk (rad/s³)')
plt.title('Jerk Comparison Across Filters')
plt.axhline(y=50, color='r', linestyle='--', label='Industrial Standard')
plt.legend()
plt.savefig('jerk_comparison.pdf')
```

### 图2: 成功率对比

### 图3: 容差灵敏度曲线

### 图4: 频谱分析

---

## 总结

**集成完成** ✅

- Launch文件: [teleop_with_filter.launch.py](../external_sdk/arm_teleop/src/lbot_teleop/launch/teleop_with_filter.launch.py)
- 启动脚本: [start_arm_teleop_with_filter.sh](start_arm_teleop_with_filter.sh)
- 支持滤波器: Passthrough, One-Euro, EMA, VIST Kalman

**下一步**:

1. 测试集成（先用passthrough验证）
2. 参数调优（grid search）
3. 对比实验（4种滤波器 × 3种任务）
4. 数据分析和论文撰写

**预期贡献**:

- 证明VIST在硬件限制下的有效性
- 提供公平的对比实验数据
- 量化不同滤波方法的性能差异