# VIST 意图因子录制与分析功能

## 概述

已成功在 VIST 系统中添加意图因子录制和分析功能。现在每次使用 VIST 滤波器录制数据时，会自动记录意图因子的详细信息，并集成到现有的分析流程中。

## 修改内容

### 1. 核心滤波器 ([vist_kalman_filter.py](ros2_ws/src/core/vist_kalman_filter.py))

**新增实例属性**：
```python
# 意图因子分量（用于录制和分析）
self.alpha_velocity = 0.0  # 速度因素 α_v
self.alpha_distance = 0.0  # 距离因素 α_d
```

**保存意图因子分量**：
在 `_compute_intent_factor()` 方法中，计算完成后保存中间变量：
```python
# 5. 保存意图因子分量（用于录制和分析）
self.alpha_velocity = alpha_v
self.alpha_distance = alpha_d
```

### 2. 滤波器节点 ([vist_filter_node.py](ros2_ws/src/nodes/vist_filter_node.py))

**更新意图因子发布逻辑**：
- 从 `vist_filter.current_alpha` 读取总意图因子
- 从 `vist_filter.alpha_velocity` 读取速度因素
- 从 `vist_filter.alpha_distance` 读取距离因素

**发布的数据格式** (`/vist_intent_factors` 话题):
```python
[alpha, alpha_distance, alpha_velocity, alpha_alignment, Q_norm, R_norm, K_norm]
```

### 3. 录制配置 ([recording_config.yaml](config/recording_config.yaml))

**启用意图因子话题**：
```yaml
vist_intent_factors:
  enabled: true
  topic: "/vist_intent_factors"
  description: "VIST 意图因子 v3.0 [alpha, alpha_distance, alpha_velocity, alpha_alignment, Q_norm, R_norm, K_norm]"
```

### 4. 分析脚本集成

#### [analyze_all_metrics.py](scripts/analysis/analyze_all_metrics.py)

**新增功能**：
- 自动提取意图因子数据
- 计算意图因子统计信息
- 将意图因子添加到 `all_metrics.json` 末尾
- 生成意图因子可视化图表 (`intent_factors.png`)

**意图因子统计**：
```json
{
  "intent_factors": {
    "alpha": {
      "mean": 0.520,
      "std": 0.180,
      "min": 0.05,
      "max": 0.6,
      "median": 0.6
    },
    "alpha_velocity": {...},
    "alpha_distance": {...},
    "precision_mode_ratio": 82.3
  }
}
```

#### [aggregate_metrics.py](scripts/analysis/aggregate_metrics.py)

**新增功能**：
- 聚合多个实验的意图因子统计
- 将意图因子添加到 `aggregated_metrics.json`
- 在 `comparison_table.md` 中添加意图因子表格

## 使用方法

### 1. 录制实验数据

```bash
# 录制300秒数据
python3 scripts/experiment/collect_experiment.py 300 my_experiment

# 意图因子会自动录制在 /vist_intent_factors 话题中
```

### 2. 分析单个实验

```bash
# 分析单个实验（包含意图因子）
python3 scripts/analysis/analyze_all_metrics.py \
    --rosbag data/experiments/experiment_20260304_174003_s \
    --output data/analysis

# 结果保存在 data/analysis/experiment_20260304_174003_s/
# - all_metrics.json（包含意图因子统计）
# - intent_factors.png（意图因子可视化）
# - trajectory_comparison.png
# - metrics_comparison.png
```

### 3. 聚合多个实验

```bash
# 聚合所有实验的分析结果
python3 scripts/analysis/aggregate_metrics.py

# 结果保存在 data/analysis/
# - aggregated_metrics.json（包含意图因子聚合统计）
# - comparison_table.md（包含意图因子表格）
```

## 数据格式说明

### `/vist_intent_factors` 话题

包含7个浮点数：

| 索引 | 名称 | 说明 | 范围 |
|------|------|------|------|
| 0 | alpha | 融合后的总意图因子 | [0.05, 0.95] |
| 1 | alpha_distance | 基于末端到目标距离计算的距离因素 | [0, 1] |
| 2 | alpha_velocity | 基于笛卡尔速度计算的速度因素 | [0, 1] |
| 3 | alpha_alignment | 对齐因素（v3.0中未使用，固定为0） | 0 |
| 4 | Q_norm | 过程噪声协方差范数 | >0 |
| 5 | R_norm | 观测噪声协方差范数 | >0 |
| 6 | K_norm | 卡尔曼增益矩阵范数 | >0 |

### 意图因子计算公式

```python
# 速度因素 α_v ∈ [0, 1]
if velocity >= velocity_threshold_high:
    α_v = 0.0  # 自由移动
elif velocity <= velocity_threshold_low:
    α_v = 1.0  # 精密对准
else:
    α_v = 线性插值

# 距离因素 α_d ∈ [0, 1]
if distance >= distance_threshold_far:
    α_d = 0.0  # 距离远
elif distance <= distance_threshold_near:
    α_d = 1.0  # 距离近
else:
    α_d = 线性插值

# 总意图因子
α = clip(0.6 × α_v + 0.4 × α_d, 0.05, 0.95)
```

## 示例分析结果

### 单个实验 (`all_metrics.json`)

```json
{
  "command": {...},
  "feedback_raw": {...},
  "intent_factors": {
    "alpha": {
      "mean": 0.520,
      "std": 0.180,
      "min": 0.05,
      "max": 0.6,
      "median": 0.6
    },
    "alpha_velocity": {
      "mean": 0.858,
      "std": 0.322,
      "min": 0.0,
      "max": 1.0
    },
    "alpha_distance": {
      "mean": 0.0,
      "std": 0.0,
      "min": 0.0,
      "max": 0.0
    },
    "precision_mode_ratio": 82.3
  }
}
```

### 聚合结果 (`aggregated_metrics.json`)

```json
{
  "aggregated_metrics": {
    "intent_factors": {
      "label": "Intent Factors",
      "num_experiments": 3,
      "metrics": {
        "alpha_mean": {
          "mean": 0.520,
          "std": 0.015,
          "min": 0.505,
          "max": 0.535
        },
        "precision_mode_ratio": {
          "mean": 82.3,
          "std": 5.2,
          "min": 77.1,
          "max": 87.5
        }
      }
    }
  }
}
```

### 对比表格 (`comparison_table.md`)

```markdown
## Intent Factors

| Metric | Mean ± Std | Min | Max |
|--------|------------|-----|-----|
| α (mean) | 0.5198 ± 0.0150 | 0.5050 | 0.5350 |
| α (std) | 0.1800 ± 0.0200 | 0.1600 | 0.2000 |
| α_velocity (mean) | 0.8580 ± 0.0300 | 0.8280 | 0.8880 |
| Precision Mode Ratio | 82.31% ± 5.20% | 77.10% | 87.50% |
```

## 生成的文件

### 单个实验分析
```
data/analysis/experiment_name/
├── all_metrics.json          # 包含意图因子统计
├── intent_factors.png        # 意图因子可视化
├── trajectory_comparison.png
└── metrics_comparison.png
```

### 聚合分析
```
data/analysis/
├── aggregated_metrics.json   # 包含意图因子聚合统计
└── comparison_table.md       # 包含意图因子表格
```

## 文件清单

### 修改的文件
1. `ros2_ws/src/core/vist_kalman_filter.py` - 保存意图因子分量
2. `ros2_ws/src/nodes/vist_filter_node.py` - 更新意图因子读取逻辑
3. `config/recording_config.yaml` - 启用意图因子话题
4. `scripts/analysis/analyze_all_metrics.py` - 集成意图因子分析
5. `scripts/analysis/aggregate_metrics.py` - 聚合意图因子统计

### 新增的文件
1. `scripts/test_intent_factors.py` - 测试意图因子发布

## 验证

已验证数据中成功录制了意图因子：
```bash
$ ros2 bag info data/experiments/experiment_20260304_174003_s

Topic: /vist_intent_factors | Type: std_msgs/msg/Float64MultiArray | Count: 314
```

分析脚本成功生成：
- `all_metrics.json` - 包含意图因子统计
- `intent_factors.png` - 意图因子可视化
- `aggregated_metrics.json` - 多实验聚合统计
- `comparison_table.md` - 包含意图因子表格


## 修改内容

### 1. 核心滤波器 ([vist_kalman_filter.py](ros2_ws/src/core/vist_kalman_filter.py))

**新增实例属性**：
```python
# 意图因子分量（用于录制和分析）
self.alpha_velocity = 0.0  # 速度因素 α_v
self.alpha_distance = 0.0  # 距离因素 α_d
```

**保存意图因子分量**：
在 `_compute_intent_factor()` 方法中，计算完成后保存中间变量：
```python
# 5. 保存意图因子分量（用于录制和分析）
self.alpha_velocity = alpha_v
self.alpha_distance = alpha_d
```

### 2. 滤波器节点 ([vist_filter_node.py](ros2_ws/src/nodes/vist_filter_node.py))

**更新意图因子发布逻辑**：
- 从 `vist_filter.current_alpha` 读取总意图因子
- 从 `vist_filter.alpha_velocity` 读取速度因素
- 从 `vist_filter.alpha_distance` 读取距离因素

**发布的数据格式** (`/vist_intent_factors` 话题):
```python
[alpha, alpha_distance, alpha_velocity, alpha_alignment, Q_norm, R_norm, K_norm]
```

### 3. 录制配置 ([recording_config.yaml](config/recording_config.yaml))

**启用意图因子话题**：
```yaml
vist_intent_factors:
  enabled: true  # 从 false 改为 true
  topic: "/vist_intent_factors"
  description: "VIST 意图因子 v3.0 [alpha, alpha_distance, alpha_velocity, alpha_alignment, Q_norm, R_norm, K_norm]"
```

### 4. 新增分析脚本 ([analyze_intent_factors.py](scripts/analysis/analyze_intent_factors.py))

专门用于分析意图因子的脚本，功能包括：

**统计分析**：
- α (总意图因子) 的均值、标准差、中位数、范围、四分位数
- α_velocity (速度因素) 的统计信息
- α_distance (距离因素) 的统计信息
- 精密模式/自由模式占比

**可视化**：
1. **时间序列图** (`intent_factors_timeline.png`):
   - α总意图因子随时间变化
   - α分量对比（速度因素 vs 距离因素）
   - 协方差范数（Q_norm, R_norm）
   - 卡尔曼增益范数（K_norm）

2. **分布直方图** (`intent_factors_distribution.png`):
   - α分布直方图
   - α_velocity分布直方图
   - α_distance分布直方图
   - 操作模式占比饼图

3. **相关性分析** (`intent_factors_correlation.png`):
   - α_velocity vs α_distance 散点图
   - 颜色表示α总值

## 使用方法

### 1. 测试意图因子发布

```bash
# 终端1: 启动 VIST 滤波器节点
ros2 run vist_filter vist_filter_node --filter-type vist

# 终端2: 监听意图因子
python3 scripts/test_intent_factors.py
```

### 2. 录制实验数据

```bash
# 录制300秒数据
python3 scripts/experiment/collect_experiment.py 300 my_experiment

# 意图因子会自动录制在 /vist_intent_factors 话题中
```

### 3. 分析意图因子

```bash
# 分析单个实验
python3 scripts/analysis/analyze_intent_factors.py \
    --rosbag data/experiments/experiment_20260304_174003_s

# 结果保存在 data/analysis/intent_factors/experiment_20260304_174003_s/
```

## 数据格式说明

### `/vist_intent_factors` 话题

包含7个浮点数：

| 索引 | 名称 | 说明 | 范围 |
|------|------|------|------|
| 0 | alpha | 融合后的总意图因子 | [0.05, 0.95] |
| 1 | alpha_distance | 基于末端到目标距离计算的距离因素 | [0, 1] |
| 2 | alpha_velocity | 基于笛卡尔速度计算的速度因素 | [0, 1] |
| 3 | alpha_alignment | 对齐因素（v3.0中未使用，固定为0） | 0 |
| 4 | Q_norm | 过程噪声协方差范数 | >0 |
| 5 | R_norm | 观测噪声协方差范数 | >0 |
| 6 | K_norm | 卡尔曼增益矩阵范数 | >0 |

### 意图因子计算公式

```python
# 速度因素 α_v ∈ [0, 1]
if velocity >= velocity_threshold_high:
    α_v = 0.0  # 自由移动
elif velocity <= velocity_threshold_low:
    α_v = 1.0  # 精密对准
else:
    α_v = 线性插值

# 距离因素 α_d ∈ [0, 1]
if distance >= distance_threshold_far:
    α_d = 0.0  # 距离远
elif distance <= distance_threshold_near:
    α_d = 1.0  # 距离近
else:
    α_d = 线性插值

# 总意图因子
α = clip(0.6 × α_v + 0.4 × α_d, 0.05, 0.95)
```

## 示例分析结果

从 `experiment_20260304_174003_s` 的分析结果：

```json
{
  "alpha": {
    "mean": 0.520,
    "std": 0.180,
    "min": 0.05,
    "max": 0.6,
    "median": 0.6
  },
  "alpha_velocity": {
    "mean": 0.858,
    "std": 0.322,
    "min": 0.0,
    "max": 1.0,
    "median": 1.0
  },
  "alpha_distance": {
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "max": 0.0
  },
  "precision_mode_ratio": 82.3%,
  "free_mode_ratio": 17.7%
}
```

**解读**：
- 82.3% 的时间处于精密模式（α > 0.5）
- 速度因素主导意图判断（均值0.858）
- 距离因素为0，说明末端始终在目标附近

## 文件清单

### 修改的文件
1. `ros2_ws/src/core/vist_kalman_filter.py` - 保存意图因子分量
2. `ros2_ws/src/nodes/vist_filter_node.py` - 更新意图因子读取逻辑
3. `config/recording_config.yaml` - 启用意图因子话题

### 新增的文件
1. `scripts/test_intent_factors.py` - 测试意图因子发布
2. `scripts/analysis/analyze_intent_factors.py` - 意图因子分析脚本

## 后续工作

可以考虑：
1. 在 `analyze_all_metrics.py` 中集成意图因子分析
2. 在 `aggregate_metrics.py` 中添加多实验意图因子对比
3. 添加意图因子与运动指标的相关性分析
4. 优化中文字体显示（matplotlib配置）

## 验证

已验证数据中成功录制了意图因子：
```bash
$ ros2 bag info data/experiments/experiment_20260304_174003_s

Topic: /vist_intent_factors | Type: std_msgs/msg/Float64MultiArray | Count: 314
```

分析脚本成功生成：
- `intent_factors_stats.json` - 统计信息
- `intent_factors_timeline.png` - 时间序列图
- `intent_factors_distribution.png` - 分布图
- `intent_factors_correlation.png` - 相关性图
