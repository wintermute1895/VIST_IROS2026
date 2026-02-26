# 脚本清理和重组计划

## 当前问题
- 脚本数量: 21个shell脚本 + 39个Python脚本 = 60个脚本
- 存在重复功能
- 命名不一致
- 缺乏清晰的组织结构

## 重组策略

### 1. 核心启动脚本（保留）
**目的**: 日常实验使用

#### Shell脚本
- ✅ `start_camera.sh` - 启动相机
- ✅ `start_left_arm_teleop.sh` - 启动左臂外骨骼
- ✅ `start_filter.sh` - 启动滤波器
- ✅ `start_5_data_glove.sh` - 启动数据手套
- ✅ `start_6_dexterous_hand.sh` - 启动灵巧手
- ✅ `collect_full_experiment.sh` - 完整实验数据采集
- ✅ `view_camera.sh` - 查看相机画面

#### Python脚本
- ✅ `generate_paper_tables.py` - 生成论文表格
- ✅ `analyze_timestamp_sync.py` - 时间戳同步分析

### 2. 过时/重复脚本（删除或归档）

#### 删除候选（旧版本或重复功能）
```
# 旧的启动脚本（已被新版本替代）
start_1_exoskeleton.sh          → 被 start_left_arm_teleop.sh 替代
start_2_filter.sh               → 被 start_filter.sh 替代
start_3_robot_driver.sh         → 不需要（机器人驱动单独启动）
start_4_teleop_bridge.sh        → 不需要（已集成）
start_complete_system.sh        → 被 collect_full_experiment.sh 替代
start_right_arm_filter.sh       → 现在用左臂
collect_right_arm_data.sh       → 被 collect_full_experiment.sh 替代

# 诊断脚本（归档到 archive/）
check_all_frequencies.sh
check_topic_collision.sh
check_topic_safety.sh
diagnose_control_flow.sh
test_frequency.sh
validate_startup_config.sh

# 旧的分析脚本（归档）
analyze_exo_data.py             → 被 analyze_all_metrics.py 替代
analyze_exo_data_v2.py          → 被 analyze_all_metrics.py 替代
analyze_episode.py              → 功能已整合
compare_topics.py               → 不常用
compare_vision_vs_exo.py        → 不常用
comprehensive_analysis.py       → 功能重复

# 开发/测试脚本（归档）
mock_lbot_driver.py
mock_teleop_bridge.py
test_*.py (所有测试脚本)
high_freq_patch.py
high_frequency_publisher.py

# 特定功能脚本（归档到 tools/）
apply_joint_mapping.py
extract_joint_follow.py
play_trajectory.py
replay_in_simulation.py
run_ablation_experiments.py
simulation_ros2_publisher.py
vist_ros2_bridge.py
```

### 3. 新的目录结构

```
scripts/
├── startup/                    # 启动脚本
│   ├── start_camera.sh
│   ├── start_exoskeleton.sh   # 重命名 start_left_arm_teleop.sh
│   ├── start_filter.sh
│   ├── start_data_glove.sh    # 重命名 start_5_data_glove.sh
│   ├── start_dexterous_hand.sh # 重命名 start_6_dexterous_hand.sh
│   └── view_camera.sh
│
├── experiment/                 # 实验相关
│   ├── collect_experiment.sh  # 重命名 collect_full_experiment.sh
│   └── generate_paper_tables.py
│
├── analysis/                   # 数据分析
│   ├── analyze_timestamp_sync.py
│   ├── analyze_all_metrics.py
│   └── check_data_quality.py
│
├── tools/                      # 工具脚本（不常用）
│   ├── monitor_system_health.py
│   ├── check_node_data.py
│   └── ...
│
└── archive/                    # 归档（旧版本、诊断脚本）
    ├── old_startup/
    ├── diagnostics/
    └── deprecated/
```

### 4. 执行步骤

#### 步骤1: 创建新目录结构
```bash
mkdir -p scripts/{startup,experiment,analysis,tools,archive/{old_startup,diagnostics,deprecated}}
```

#### 步骤2: 移动核心脚本
```bash
# 启动脚本
mv scripts/start_camera.sh scripts/startup/
mv scripts/start_left_arm_teleop.sh scripts/startup/start_exoskeleton.sh
mv scripts/start_filter.sh scripts/startup/
mv scripts/start_5_data_glove.sh scripts/startup/start_data_glove.sh
mv scripts/start_6_dexterous_hand.sh scripts/startup/start_dexterous_hand.sh
mv scripts/view_camera.sh scripts/startup/

# 实验脚本
mv scripts/collect_full_experiment.sh scripts/experiment/collect_experiment.sh
mv scripts/generate_paper_tables.py scripts/experiment/

# 分析脚本
mv scripts/analyze_timestamp_sync.py scripts/analysis/
mv scripts/analyze_all_metrics.py scripts/analysis/
mv scripts/check_data_quality.py scripts/analysis/
```

#### 步骤3: 归档旧脚本
```bash
# 旧启动脚本
mv scripts/start_[1-4]_*.sh scripts/archive/old_startup/
mv scripts/start_complete_system.sh scripts/archive/old_startup/
mv scripts/start_right_arm_filter.sh scripts/archive/old_startup/
mv scripts/collect_right_arm_data.sh scripts/archive/old_startup/

# 诊断脚本
mv scripts/check_*.sh scripts/archive/diagnostics/
mv scripts/diagnose_*.sh scripts/archive/diagnostics/
mv scripts/test_*.sh scripts/archive/diagnostics/
mv scripts/validate_*.sh scripts/archive/diagnostics/

# 开发测试脚本
mv scripts/mock_*.py scripts/archive/deprecated/
mv scripts/test_*.py scripts/archive/deprecated/
mv scripts/high_freq*.py scripts/archive/deprecated/
```

#### 步骤4: 移动工具脚本
```bash
mv scripts/monitor_*.py scripts/tools/
mv scripts/check_node_data.py scripts/tools/
mv scripts/apply_joint_mapping.py scripts/tools/
mv scripts/extract_joint_follow.py scripts/tools/
```

### 5. 更新文档引用

需要更新以下文档中的脚本路径：
- `docs/FULL_EXPERIMENT_GUIDE.md`
- `docs/PERFORMANCE_METRICS_CHECKLIST.md`
- `docs/QUICK_START.md`
- `README.md`

### 6. 创建快捷启动脚本

在项目根目录创建 `quick_start.sh`:
```bash
#!/bin/bash
# 快速启动菜单

echo "VIST 系统快速启动"
echo "=================="
echo "1. 启动相机"
echo "2. 启动外骨骼"
echo "3. 启动滤波器"
echo "4. 启动数据手套"
echo "5. 启动灵巧手"
echo "6. 开始实验采集"
echo "7. 查看相机画面"
echo "0. 退出"
```

## 预期效果

### 清理前
- 60个脚本混在一起
- 难以找到需要的脚本
- 不知道哪些是最新的

### 清理后
- 核心脚本: ~15个（常用）
- 工具脚本: ~10个（偶尔用）
- 归档脚本: ~35个（不删除，以防需要）
- 清晰的目录结构
- 统一的命名规范

## 安全措施

1. ✅ 已提交当前版本到git
2. 不删除任何文件，只移动到archive
3. 保留所有功能，只是重新组织
4. 可以随时回滚

## 下一步

是否执行这个清理计划？我可以：
1. 自动执行所有移动操作
2. 更新所有文档引用
3. 创建快捷启动脚本
4. 生成迁移说明文档