# VIST 论文数据采集规划

## 一、当前系统能力评估

### 已具备的采集能力 ✅

1. **运动学数据**
   - 外骨骼原始数据：80Hz
   - 滤波后数据：80Hz
   - 相机数据：30Hz
   - 时间戳同步：平均误差3.14ms

2. **已实现的分析指标**
   - 归一化加加速度（Normalized Jerk）
   - 抖动统计（Jerk RMS）
   - 功率谱密度（PSD）
   - 主成分分析（PCA）
   - 频率分布分析
   - SPARC平滑度（需添加）

## 二、论文所需数据映射

### Table I: 任务成功率与完成时间

| 数据项 | 当前状态 | 采集方案 |
|--------|----------|----------|
| USB盲插成功率 | ❌ 未采集 | 需要设计任务协议 |
| 3D打印件插入成功率 | ❌ 未采集 | 需要制作测试件 |
| 积木堆叠成功率 | ❌ 未采集 | 需要准备积木 |
| 任务完成时间 | ⚠️ 部分可用 | 需要标注起止点 |

**采集方案：**
```bash
# 1. 定义任务成功标准
# 2. 每个任务重复N次（建议N≥20）
# 3. 记录：成功/失败、完成时间、失败原因
# 4. 对比：无滤波 vs One-Euro滤波 vs VIST滤波
```

### Table II: 运动学平滑度

| 数据项 | 当前状态 | 采集方案 |
|--------|----------|----------|
| Normalized Jerk | ✅ 已实现 | 直接从现有数据计算 |
| SPARC | ⚠️ 需添加 | 添加SPARC计算函数 |
| 加速度统计 | ✅ 已实现 | 直接使用 |

**采集方案：**
```python
# 已有数据可直接分析
# 需要添加SPARC计算：
def calculate_sparc(velocity_profile, sampling_rate):
    """
    计算谱弧长（Spectral Arc Length）
    SPARC值越接近0越平滑
    """
    # 实现SPARC算法
    pass
```

### Table III: 数据空间一致性

| 数据项 | 当前状态 | 采集方案 |
|--------|----------|----------|
| 空间分布方差 | ⚠️ 需多次试验 | 同一任务重复N次 |
| 最大径向偏差 | ⚠️ 需定义轴线 | 定义任务主轴 |
| 轴向速度方差 | ⚠️ 需多次试验 | 同一任务重复N次 |

**采集方案：**
```bash
# 1. 选择标准任务（如：直线插入）
# 2. 重复采集20-30次
# 3. 对齐轨迹（DTW或时间对齐）
# 4. 计算空间管束（Tube）统计量
```

## 三、数据采集实施计划

### 第一阶段：基础数据采集（1-2天）

**目标：** 采集足够的重复试验数据

```bash
# 任务1：自由运动数据（基线）
./scripts/collect_right_arm_data.sh baseline_free_motion 30
# 重复10次

# 任务2：模拟插入任务（无真实物体）
./scripts/collect_right_arm_data.sh simulated_insertion 30
# 重复20次

# 任务3：带相机的视觉引导
# 启用意图计算，采集α因子
./scripts/collect_right_arm_data.sh visual_guided 30
# 重复20次
```

### 第二阶段：添加SPARC分析（半天）

**需要实现的功能：**

1. SPARC计算函数
2. 集成到综合分析脚本
3. 生成对比图表

### 第三阶段：多次试验统计分析（1天）

**需要实现的功能：**

1. 轨迹对齐算法（DTW）
2. 空间管束可视化
3. 方差与偏差计算
4. PCA能量分析

### 第四阶段：真实任务测试（可选，2-3天）

**需要准备：**

1. USB插座和USB插头
2. 3D打印测试件（不同间隙）
3. 积木或类似物体
4. 任务成功判定标准

## 四、数据分析脚本规划

### 脚本1：SPARC计算

```python
# scripts/calculate_sparc.py
# 输入：速度轨迹
# 输出：SPARC值
```

### 脚本2：多试验统计分析

```python
# scripts/analyze_multi_trial_consistency.py
# 输入：多个rosbag文件
# 输出：空间方差、径向偏差、DTW距离
```

### 脚本3：对比分析

```python
# scripts/compare_filtering_methods.py
# 输入：无滤波、One-Euro、VIST三组数据
# 输出：Table II和Table III的完整数据
```

## 五、当前可立即执行的任务

### 任务A：采集重复试验数据

```bash
# 创建实验目录
mkdir -p data/paper_experiments/baseline_no_filter
mkdir -p data/paper_experiments/one_euro_filter
mkdir -p data/paper_experiments/vist_filter

# 采集脚本（示例）
for i in {1..20}; do
    echo "Trial $i"
    ./scripts/collect_right_arm_data.sh trial_${i} 30
    sleep 5
done
```

### 任务B：分析现有数据

```bash
# 使用现有的test_flow数据
python3 scripts/comprehensive_analysis.py \
    --bag data/exp_right_arm_only_20260225/test_flow \
    --output data/paper_analysis/baseline
```

### 任务C：添加SPARC分析

需要实现SPARC计算函数并集成到分析流程中。

## 六、数据采集检查清单

- [ ] 基础重复试验数据（20次以上）
- [ ] 不同滤波方法对比数据
- [ ] SPARC平滑度计算
- [ ] 空间一致性统计
- [ ] DTW距离分析
- [ ] PCA能量分析
- [ ] 频域PSD对比
- [ ] 时间戳同步验证
- [ ] 任务成功率统计（可选）
- [ ] NASA-TLX问卷（可选）

## 七、预期产出

### 数据文件
- `baseline_statistics.json` - 基线统计数据
- `filtering_comparison.json` - 滤波对比数据
- `spatial_consistency.json` - 空间一致性数据

### 图表文件
- `jerk_comparison.png` - 加加速度对比
- `sparc_comparison.png` - SPARC对比
- `spatial_variance_plot.png` - 空间方差可视化
- `psd_comparison.png` - 频域对比
- `trajectory_tube.png` - 轨迹管束可视化

### 表格数据
- Table II 完整数据
- Table III 完整数据
- 频域统计数据
- PCA分析结果