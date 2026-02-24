# VIST 数据管理规范化方案

## 📊 当前问题分析

### 1. 数据目录混乱

**当前状态**：
```
data/
├── experiments/                    # 2个实验数据
├── recordings/                     # 5个配置化录制
├── vision_recordings/              # 12个视觉录制
├── vision_control_test_*/          # 5个测试（直接在根目录）
├── test_publisher_exo_*/           # 1个测试（直接在根目录）
└── vision_vs_exo_comparison/       # 1个对比分析
```

**问题**：
- ❌ 目录命名不统一（experiments vs recordings vs vision_recordings）
- ❌ 缺少层级结构（没有task/session/episode概念）
- ❌ 元数据缺失（大部分目录没有metadata.json）
- ❌ 测试数据混在根目录
- ❌ 没有质量评分和验证报告

### 2. 录制脚本重复

**发现5个录制脚本**：

| 脚本 | 输出目录 | 功能 | 状态 | 问题 |
|------|---------|------|------|------|
| collect_data.sh | experiments/ | 完整采集 | 可能废弃 | 输出目录不明确 |
| collect_vision_data.sh | vision_experiments/ | 视觉遥操作 | 较新 | 目录不存在 |
| quick_record.sh | vision_recordings/ | 快速录制 | 使用中 | 功能重复 |
| record_configurable.sh | recordings/ | 配置化录制 | 主要使用 | 未集成新工具 |
| record_vision_only.sh | vision_recordings/ | 纯视觉录制 | 使用中 | 功能重复 |

**问题**：
- ❌ 功能重复（quick_record.sh 和 record_vision_only.sh）
- ❌ 输出目录不统一（3个不同目录）
- ❌ 没有使用Episode管理器
- ❌ 没有自动质量验证
- ❌ 没有元数据生成

### 3. 分析脚本分散

**发现的分析脚本**：
- scripts/analyze_vision_control.py
- scripts/compare_vision_vs_exo.py
- scripts/evaluate_vision_performance.py
- scripts/compare_topics.py
- scripts/analysis/cli/analyze.py

**问题**：
- ❌ 输出目录不统一（有的用data/comparison，有的用data/analysis）
- ❌ 没有统一的分析流程
- ❌ 缺少自动化分析管道

---

## 🎯 规范化方案

### 阶段1: 统一数据目录结构

#### 新的目录结构

```
data/
├── collection/                     # 原始采集数据（新）
│   ├── task_name/                  # 按任务分类
│   │   ├── session_YYYYMMDD_HHMMSS/
│   │   │   ├── episode_000000/
│   │   │   │   ├── rosbag/
│   │   │   │   ├── metadata.json
│   │   │   │   ├── sync_validation_report.json
│   │   │   │   └── quality_report.json
│   │   │   ├── episode_000001/
│   │   │   └── session_manifest.json
│   │   └── all_episodes/           # 符号链接
│   └── README.md
│
├── training/                       # 训练数据（新）
│   ├── task_name/
│   │   ├── episode_000000.hdf5
│   │   ├── episode_000001.hdf5
│   │   └── dataset_manifest.json
│   └── README.md
│
├── analysis/                       # 分析结果（新）
│   ├── task_name/
│   │   ├── session_YYYYMMDD_HHMMSS/
│   │   │   ├── frequency_analysis.png
│   │   │   ├── trajectory_comparison.png
│   │   │   └── analysis_report.json
│   │   └── comparison_reports/
│   └── README.md
│
├── experiments/                    # 实验数据（保留，迁移）
│   └── experiment_name/
│       └── ...
│
└── archive/                        # 归档数据（新）
    ├── old_recordings/
    ├── old_vision_recordings/
    └── README.md
```

#### 迁移计划

**步骤1: 创建新目录结构**
```bash
mkdir -p data/collection
mkdir -p data/training
mkdir -p data/analysis
mkdir -p data/archive
```

**步骤2: 迁移现有数据**
```bash
# 迁移recordings到archive
mv data/recordings data/archive/old_recordings

# 迁移vision_recordings到archive
mv data/vision_recordings data/archive/old_vision_recordings

# 迁移测试数据
mv data/vision_control_test_* data/archive/
mv data/test_publisher_exo_* data/archive/

# 保留experiments和vision_vs_exo_comparison
# 这些可能还在使用
```

**步骤3: 为归档数据生成元数据**
```bash
# 批量生成元数据
python scripts/generate_episode_metadata.py data/archive/old_recordings --batch
python scripts/generate_episode_metadata.py data/archive/old_vision_recordings --batch
```

---

### 阶段2: 整合录制脚本

#### 保留的脚本

**主脚本: record_configurable.sh**
- 重命名为: `scripts/record_data.sh`
- 增强功能:
  - 集成Episode管理器
  - 自动质量验证
  - 自动元数据生成
  - 统一输出到 data/collection/

**快速录制: quick_record.sh**
- 保留，作为简化版本
- 修改输出目录为 data/collection/quick_test/
- 添加元数据生成

#### 废弃的脚本

**废弃并删除**:
- ❌ collect_data.sh - 功能已被record_configurable.sh覆盖
- ❌ collect_vision_data.sh - 输出目录不存在，功能重复
- ❌ record_vision_only.sh - 与quick_record.sh功能重复

**迁移到archive**:
```bash
mkdir -p scripts/archive
mv scripts/collect_data.sh scripts/archive/
mv scripts/collect_vision_data.sh scripts/archive/
mv scripts/record_vision_only.sh scripts/archive/
```

#### 新的录制脚本

**scripts/record_data.sh** (增强版record_configurable.sh)
```bash
#!/bin/bash
# 统一数据录制脚本
# 输出: data/collection/task_name/session_*/episode_*/

# 功能:
# 1. 使用Episode管理器
# 2. 自动质量验证
# 3. 自动元数据生成
# 4. 统一目录结构

# 用法:
#   bash scripts/record_data.sh --task pick_and_place --config config/task_config.yaml
```

**scripts/quick_record.sh** (简化版)
```bash
#!/bin/bash
# 快速录制脚本（用于测试）
# 输出: data/collection/quick_test/session_*/episode_*/

# 用法:
#   bash scripts/quick_record.sh [时长秒数]
```

---

### 阶段3: 统一分析流程

#### 分析脚本整合

**保留的核心分析脚本**:
1. `scripts/validate_time_sync.py` - 时间同步验证（已实现）
2. `scripts/generate_episode_metadata.py` - 元数据生成（已实现）
3. `scripts/analyze_vision_control.py` - 视觉控制分析
4. `scripts/compare_topics.py` - 话题对比

**新的统一分析脚本**:
```bash
scripts/analyze_episode.py
  - 输入: episode目录
  - 输出: data/analysis/task_name/session_*/
  - 功能:
    - 时间同步验证
    - 频率分析
    - 轨迹对比
    - 质量评分
    - 生成可视化报告
```

**分析流程**:
```
Episode录制完成
  ↓
自动运行 validate_time_sync.py
  ↓
自动运行 generate_episode_metadata.py
  ↓
（可选）运行 analyze_episode.py
  ↓
生成完整分析报告
```

---

## 📋 实施计划

### Phase 1: 清理和归档 (30分钟)

**任务**:
1. ✅ 创建新目录结构
2. ✅ 迁移旧数据到archive
3. ✅ 为归档数据生成元数据
4. ✅ 更新.gitignore

**脚本**:
```bash
# 执行清理脚本
bash scripts/cleanup_data_structure.sh
```

### Phase 2: 整合录制脚本 (1小时)

**任务**:
1. ⏳ 增强record_configurable.sh
   - 集成Episode管理器
   - 添加自动验证
   - 统一输出目录
2. ⏳ 简化quick_record.sh
3. ⏳ 归档废弃脚本
4. ⏳ 更新文档

### Phase 3: 统一分析流程 (1小时)

**任务**:
1. ⏳ 创建analyze_episode.py
2. ⏳ 整合现有分析脚本
3. ⏳ 创建自动化分析管道
4. ⏳ 更新文档

### Phase 4: 测试和验证 (30分钟)

**任务**:
1. ⏳ 测试新的录制流程
2. ⏳ 测试分析流程
3. ⏳ 验证数据完整性
4. ⏳ 更新使用文档

---

## 📝 新的工作流程

### 数据采集流程

```bash
# 1. 创建任务
python scripts/episode_manager.py create-task \
    --name pick_and_place \
    --config config/task_config.yaml

# 2. 交互式录制
python scripts/episode_manager.py interactive \
    --session session_20260224_153024

# 或使用增强的录制脚本
bash scripts/record_data.sh \
    --task pick_and_place \
    --config config/task_config.yaml \
    --duration 30

# 3. 自动验证和分析（录制完成后自动执行）
# - 时间同步验证
# - 元数据生成
# - 质量评分
```

### 数据分析流程

```bash
# 1. 分析单个Episode
python scripts/analyze_episode.py \
    --episode data/collection/pick_and_place/session_*/episode_000000

# 2. 对比多个Episodes
python scripts/compare_episodes.py \
    --session data/collection/pick_and_place/session_*

# 3. 生成训练数据
python scripts/episode_manager.py convert \
    --session session_20260224_153024 \
    --quality-threshold B \
    --format hdf5
```

### 数据管理流程

```bash
# 1. 查看会话统计
python scripts/episode_manager.py stats \
    --session session_20260224_153024

# 2. 清理低质量数据
python scripts/episode_manager.py cleanup \
    --session session_20260224_153024 \
    --quality-threshold C

# 3. 归档旧数据
bash scripts/archive_old_data.sh \
    --before 2026-02-01
```

---

## 🎓 规范和最佳实践

### 命名规范

**任务名称**:
- 使用小写字母和下划线
- 描述性名称
- 例: `pick_and_place`, `vision_control_test`, `teleoperation_demo`

**Session ID**:
- 格式: `session_YYYYMMDD_HHMMSS`
- 自动生成
- 例: `session_20260224_153024`

**Episode ID**:
- 格式: `episode_NNNNNN` (6位数字)
- 自动编号
- 例: `episode_000000`, `episode_000001`

### 元数据规范

**必需字段**:
- episode_id
- task_name
- timestamp
- duration_sec
- topics
- quality_score

**可选字段**:
- operator
- notes
- environment
- robot_config

### 质量标准

**A级（优秀）**:
- 时间同步 <10ms
- 无丢帧
- 数据完整

**B级（良好）**:
- 时间同步 <33ms
- 丢帧率 <1%
- 数据基本完整

**C级（可接受）**:
- 时间同步 <100ms
- 丢帧率 <5%
- 数据可用

**D级（较差）**:
- 时间同步 <200ms
- 丢帧率 <10%
- 建议重新录制

**F级（失败）**:
- 时间同步 >200ms
- 丢帧严重
- 不可用

---

## 🔧 需要创建的脚本

### 1. cleanup_data_structure.sh
清理和重组数据目录结构

### 2. record_data.sh
增强版录制脚本（基于record_configurable.sh）

### 3. analyze_episode.py
统一的Episode分析脚本

### 4. compare_episodes.py
Episode对比分析脚本

### 5. archive_old_data.sh
归档旧数据脚本

---

## 📚 文档更新

需要更新的文档:
1. README.md - 添加数据管理章节
2. docs/DATA_COLLECTION_GUIDE.md - 数据采集指南
3. docs/DATA_ANALYSIS_GUIDE.md - 数据分析指南
4. docs/DATA_MANAGEMENT_GUIDE.md - 数据管理指南

---

**需要我开始实施这个规范化方案吗？我可以从Phase 1开始，创建清理脚本并重组数据目录。**
