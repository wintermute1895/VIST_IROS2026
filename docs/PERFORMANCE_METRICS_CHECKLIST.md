# VIST系统性能指标测量清单

## 概述
本文档列出VIST论文所需的所有性能指标、测量方法、当前状态和待完成任务。

---

## 📊 论文表格总览

### Table I: 任务成功率 (Success Rates)
**状态**: ⚠️ 待定义任务协议

| 任务类型 | GELLO | ACT | VIST (Ours) | 状态 |
|---------|-------|-----|-------------|------|
| Pick & Place | TBD | TBD | TBD | 🔴 未开始 |
| Assembly | TBD | TBD | TBD | 🔴 未开始 |
| Manipulation | TBD | TBD | TBD | 🔴 未开始 |

**需要完成**:
- [ ] 定义具体任务协议（插孔、抓取、组装等）
- [ ] 设计评估标准（成功/失败判定）
- [ ] 每个任务至少10次试验
- [ ] 记录成功率和失败原因

---

### Table II: 平滑度指标 (Smoothness Metrics)
**状态**: ✅ 脚本已完成，可直接使用

| Method | Normalized Jerk | SPARC | 状态 |
|--------|----------------|-------|------|
| Raw Teleoperation | 194091868.36 | 10.59 | ✅ 已测量 |
| VIST (Ours) | 17809357.58 | 13.71 | ✅ 已测量 |
| Improvement | 90.8% | 29.5% | ✅ 已计算 |

**测量指标**:
1. **Normalized Jerk (归一化急动度)**
   - 公式: `NJ = sqrt(T^5 / (2 * duration^3) * sum(jerk^2))`
   - 越小越好，表示运动越平滑
   - 当前改善: 90.8%

2. **SPARC (Spectral Arc Length)**
   - 基于速度频谱的平滑度指标
   - 越大越好，表示运动越平滑
   - 当前改善: 29.5%

**已完成**:
- ✅ 数据采集脚本
- ✅ 指标计算脚本 (`scripts/generate_paper_tables.py`)
- ✅ 单次试验数据分析

**使用方法**:
```bash
python3 scripts/generate_paper_tables.py \
  --rosbag data/exp_right_arm_only_20260225/test_flow \
  --raw-topic /right_arm_joint_control \
  --filtered-topic /filtered_right_joint_control
```

---

### Table III: 空间一致性 (Spatial Consistency)
**状态**: ⚠️ 需要多次试验数据

| Method | Spatial Variance (deg²) | Radial Deviation (deg) | 状态 |
|--------|------------------------|----------------------|------|
| VIST (Ours) | 239.22 (estimated) | 12.66 (estimated) | ⚠️ 单次估计 |

**测量指标**:
1. **Spatial Variance (空间方差)**
   - 多次重复相同任务的轨迹方差
   - 越小越好，表示一致性越高
   - 需要: 至少5次重复试验

2. **Radial Deviation (径向偏差)**
   - 每条轨迹到平均轨迹的距离
   - 越小越好，表示重复性越高
   - 需要: 至少5次重复试验

**需要完成**:
- [ ] 设计可重复的标准任务
- [ ] 采集至少5次重复试验数据
- [ ] 使用DTW对齐轨迹
- [ ] 计算真实的空间方差和径向偏差

---

## 🎯 当前系统能力

### 已实现功能
✅ **硬件集成**
- 左臂外骨骼 (Linkerta)
- 数据手套 (左手)
- 灵巧手 (左手, L10)
- RealSense相机 (D435i)
- 机械臂（被控端）

✅ **软件功能**
- One-Euro滤波器
- 实时数据采集
- 性能指标计算
- 论文表格生成

✅ **数据分析**
- Jerk改善: 90.8%
- 加速度改善: 63.5%
- SPARC改善: 29.5%
- 时间戳同步: 3.14ms误差

### 待实现功能
🔴 **任务协议**
- 插孔任务定义
- 抓取任务定义
- 组装任务定义
- 成功/失败判定标准

🔴 **数据采集**
- 多次重复试验
- 不同任务场景
- 对比实验（GELLO, ACT）

🔴 **高级分析**
- DTW轨迹对齐
- PCA主成分分析
- PSD功率谱密度
- 可视化工具

---

## 📋 数据采集计划

### Phase 1: 基础数据采集 ✅
**目标**: 验证系统功能
- [x] 单次遥操作数据
- [x] 滤波器性能验证
- [x] 时间戳同步验证

**数据位置**: `data/exp_right_arm_only_20260225/test_flow/`

### Phase 2: 平滑度测试 (进行中)
**目标**: 完成Table II
- [x] 采集原始和滤波数据
- [x] 计算Normalized Jerk
- [x] 计算SPARC
- [ ] 多场景测试（不同速度、不同任务）

### Phase 3: 一致性测试 (待开始)
**目标**: 完成Table III
- [ ] 设计标准重复任务
- [ ] 采集5-10次重复数据
- [ ] 实现DTW对齐
- [ ] 计算空间方差和径向偏差

### Phase 4: 任务成功率测试 (待开始)
**目标**: 完成Table I
- [ ] 定义3-5个标准任务
- [ ] 每个任务10次试验
- [ ] 记录成功率
- [ ] 对比GELLO和ACT（如果可能）

---

## 🛠️ 工具和脚本

### 数据采集
```bash
# 完整实验数据采集（60秒）
bash scripts/collect_full_experiment.sh 60 experiment_name

# 采集的topic:
# - /camera/color/image_raw
# - /camera/depth/image_rect_raw
# - /left_arm_joint_control (原始)
# - /filtered_left_joint_control (滤波)
# - /cb_left_hand_control_cmd (手套)
# - /cb_left_hand_state (灵巧手)
# - /robot_joint_states (机械臂)
```

### 数据分析
```bash
# 生成论文表格
python3 scripts/generate_paper_tables.py \
  --rosbag <rosbag_path> \
  --raw-topic /left_arm_joint_control \
  --filtered-topic /filtered_left_joint_control

# 时间戳同步分析
python3 scripts/analyze_timestamp_sync.py <rosbag_path>
```

### 系统启动
参考: [docs/FULL_EXPERIMENT_GUIDE.md](FULL_EXPERIMENT_GUIDE.md)

---

## 📈 性能目标

### 平滑度改善目标
- Normalized Jerk: > 80% 改善 ✅ (当前: 90.8%)
- SPARC: > 20% 改善 ✅ (当前: 29.5%)

### 一致性目标
- Spatial Variance: < 50 deg² (待测量)
- Radial Deviation: < 5 deg (待测量)

### 成功率目标
- 插孔任务: > 90%
- 抓取任务: > 85%
- 组装任务: > 80%

---

## 🚀 下一步行动

### 立即可做
1. **多场景平滑度测试**
   - 不同速度（慢速、中速、快速）
   - 不同轨迹（直线、曲线、复杂路径）
   - 采集3-5组数据

2. **设计标准任务**
   - 插孔任务: 定义孔位、插头规格
   - 抓取任务: 定义物体、抓取点
   - 记录任务参数

### 短期目标（1-2周）
3. **重复性测试**
   - 选择1个标准任务
   - 采集10次重复数据
   - 完成Table III

4. **任务成功率测试**
   - 执行定义的任务
   - 记录成功/失败
   - 完成Table I

### 长期目标（1个月）
5. **对比实验**
   - 实现GELLO baseline（如果可能）
   - 对比实验数据
   - 完善论文数据

6. **可视化和报告**
   - 轨迹可视化
   - 性能对比图表
   - 实验视频录制

---

## 📝 数据管理

### 数据组织结构
```
data/
├── experiments/
│   ├── peg_in_hole_trial1/
│   │   ├── rosbag files
│   │   └── metadata.yaml
│   ├── peg_in_hole_trial2/
│   └── ...
├── analysis/
│   ├── table_ii_results.json
│   ├── table_iii_results.json
│   └── visualizations/
└── paper_data/
    ├── final_table_i.csv
    ├── final_table_ii.csv
    └── final_table_iii.csv
```

### 元数据记录
每次实验记录:
- 实验日期和时间
- 任务类型
- 操作者
- 环境条件
- 成功/失败
- 备注

---

## 🔍 质量检查清单

### 数据质量
- [ ] 时间戳同步 < 5ms
- [ ] 数据完整性（无丢包）
- [ ] 频率稳定性
- [ ] 传感器标定

### 实验质量
- [ ] 任务定义清晰
- [ ] 评估标准明确
- [ ] 重复性验证
- [ ] 对照组设置

### 分析质量
- [ ] 指标计算正确
- [ ] 统计显著性
- [ ] 可视化清晰
- [ ] 结果可重现

---

## 📚 参考文档

- [完整实验指南](FULL_EXPERIMENT_GUIDE.md)
- [数据采集计划](DATA_COLLECTION_PLAN.md)
- [快速启动指南](QUICK_START.md)
- [故障排查](TROUBLESHOOTING.md)

---

**最后更新**: 2026-02-25
**状态**: Phase 2 进行中
**下一个里程碑**: 完成Table III的多次试验数据采集