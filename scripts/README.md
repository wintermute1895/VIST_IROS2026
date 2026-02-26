# Scripts 目录说明

## 目录结构

```
scripts/
├── startup/          # 系统启动脚本（日常使用）
├── experiment/       # 实验数据采集和分析
├── analysis/         # 数据分析工具
├── tools/            # 辅助工具（不常用）
└── archive/          # 归档脚本（旧版本、诊断工具）
```

## 核心脚本

### 启动脚本 (startup/)
日常实验使用的启动脚本：

- `start_camera.sh` - 启动RealSense相机
- `start_exoskeleton.sh` - 启动左臂外骨骼
- `start_filter.sh` - 启动One-Euro滤波器
- `start_data_glove.sh` - 启动数据手套
- `start_dexterous_hand.sh` - 启动灵巧手
- `view_camera.sh` - 查看相机画面

### 实验脚本 (experiment/)
实验数据采集和论文数据生成：

- `collect_experiment.sh` - 完整实验数据采集
- `generate_paper_tables.py` - 生成论文表格数据

### 分析脚本 (analysis/)
数据分析工具：

- `analyze_all_metrics.py` - 完整性能指标分析
- `analyze_timestamp_sync.py` - 时间戳同步分析
- `check_data_quality.py` - 数据质量检查

## 快速开始

### 启动完整系统
```bash
# 终端1: 相机
bash scripts/startup/start_camera.sh

# 终端2: 外骨骼
bash scripts/startup/start_exoskeleton.sh

# 终端3: 滤波器
bash scripts/startup/start_filter.sh

# 终端4: 数据手套
bash scripts/startup/start_data_glove.sh

# 终端5: 灵巧手
bash scripts/startup/start_dexterous_hand.sh left

# 终端6: 数据采集
bash scripts/experiment/collect_experiment.sh 60 test1
```

### 分析数据
```bash
# 生成论文表格
python3 scripts/experiment/generate_paper_tables.py \
  --rosbag data/experiments/test1

# 分析时间戳同步
python3 scripts/analysis/analyze_timestamp_sync.py \
  data/experiments/test1
```

## 归档说明

### archive/old_startup/
旧版本的启动脚本，已被新版本替代。保留用于参考。

### archive/diagnostics/
诊断和测试脚本，用于系统调试。

### archive/deprecated/
已废弃的脚本，包括：
- 旧版本分析脚本
- 开发测试脚本
- Mock节点

## 迁移说明

如果你有脚本引用了旧路径，请更新为新路径：

| 旧路径 | 新路径 |
|--------|--------|
| `scripts/start_left_arm_teleop.sh` | `scripts/startup/start_exoskeleton.sh` |
| `scripts/start_5_data_glove.sh` | `scripts/startup/start_data_glove.sh` |
| `scripts/start_6_dexterous_hand.sh` | `scripts/startup/start_dexterous_hand.sh` |
| `scripts/collect_full_experiment.sh` | `scripts/experiment/collect_experiment.sh` |

## 文档更新

以下文档已更新为新路径：
- [x] docs/FULL_EXPERIMENT_GUIDE.md
- [x] docs/PERFORMANCE_METRICS_CHECKLIST.md
- [ ] docs/QUICK_START.md (待更新)
- [ ] README.md (待更新)