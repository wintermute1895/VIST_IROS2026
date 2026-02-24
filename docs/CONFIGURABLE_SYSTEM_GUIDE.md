# VIST 配置化系统使用指南

## 📋 概述

VIST系统现在完全配置化，通过YAML配置文件可以灵活控制：
- 录制什么数据
- 是否控制真机
- 分析什么指标
- 输出什么格式

## 🎯 核心配置文件

### config/full_config_example.yaml

完整的配置文件示例，包含所有可配置选项：

```yaml
task_info:
  name: "pick_and_place"
  description: "抓取和放置任务"

recording:
  enabled: true
  duration: 30
  topics:
    camera:
      enabled: true
      topics: ["/camera/color/image_raw", ...]
    control:
      enabled: true
      topics: ["/vision_right_joint_control", ...]

control:
  mode: "vision"  # vision | teleoperation | hybrid | none
  use_real_robot: true

analysis:
  enabled: true
  metrics:
    frequency:
      enabled: true
    time_sync:
      enabled: true
    trajectory:
      enabled: true
```

## 🚀 使用方法

### 1. 创建配置文件

复制示例配置并修改：

```bash
cp config/full_config_example.yaml config/my_task.yaml
# 编辑 config/my_task.yaml
```

### 2. 录制数据

```bash
# 使用配置文件录制
python scripts/configurable_manager.py record --config config/my_task.yaml
```

### 3. 分析数据

```bash
# 分析指定Episode
python scripts/configurable_manager.py analyze \
    --config config/my_task.yaml \
    --episode data/collection/task_name/session_*/episode_000000
```

### 4. 完整流程（录制+分析）

```bash
# 一键运行完整流程
python scripts/configurable_manager.py run --config config/my_task.yaml
```

## 📝 配置详解

### 录制配置

#### 选择录制话题

```yaml
recording:
  topics:
    camera:
      enabled: true  # 启用相机话题
      topics:
        - "/camera/color/image_raw"
        - "/camera/depth/image_rect_raw"

    control:
      enabled: true  # 启用控制话题
      topics:
        - "/vision_right_joint_control"

    robot_state:
      enabled: true  # 启用机器人状态
      topics:
        - "/robot1/right_arm/joint_states"

    exoskeleton:
      enabled: false  # 禁用外骨骼话题
```

#### 自动化选项

```yaml
recording:
  automation:
    auto_validate: true          # 自动验证数据质量
    auto_generate_metadata: true # 自动生成元数据
    auto_analyze: false          # 录制后自动分析
```

### 控制配置

#### 控制模式

```yaml
control:
  mode: "vision"  # 选项：
                  # - vision: 视觉控制
                  # - teleoperation: 遥操作
                  # - hybrid: 混合模式
                  # - none: 无控制（仅录制）

  use_real_robot: true  # 是否连接真机
```

#### 真机配置

```yaml
control:
  robot:
    ip: "192.168.1.100"
    port: 8080
    timeout: 5.0
```

### 分析配置

#### 选择分析指标

```yaml
analysis:
  metrics:
    frequency:
      enabled: true  # 频率分析
      min_frequency: 1.0

    time_sync:
      enabled: true  # 时间同步分析
      reference_topic: "/camera/color/image_raw"
      thresholds:
        excellent: 0.010  # 10ms
        good: 0.033       # 33ms

    integrity:
      enabled: true  # 完整性检查

    trajectory:
      enabled: true  # 轨迹分析

    performance:
      enabled: false  # 性能指标（高级）
```

#### 可视化配置

```yaml
analysis:
  visualization:
    enabled: true
    generate_plots: true
    plot_formats: ["png", "pdf"]
    dpi: 150
```

#### 报告配置

```yaml
analysis:
  reporting:
    enabled: true
    formats: ["json", "markdown", "html"]
    include_plots: true
```

### 质量要求

```yaml
quality:
  min_sync_quality: "good"      # 最低同步质量
  max_time_diff_ms: 33          # 最大时间差
  min_duration_sec: 10          # 最小时长
  max_duration_sec: 120         # 最大时长

  auto_cleanup:
    enabled: false
    remove_failed: false
    remove_low_quality: false
    quality_threshold: "C"
```

## 🎨 配置示例

### 示例1: 纯视觉控制录制

```yaml
task_info:
  name: "vision_control_test"

recording:
  enabled: true
  duration: 30
  topics:
    camera:
      enabled: true
      topics: ["/camera/color/image_raw"]
    control:
      enabled: true
      topics: ["/vision_right_joint_control"]
    robot_state:
      enabled: true
      topics: ["/robot1/right_arm/joint_states"]
    exoskeleton:
      enabled: false

control:
  mode: "vision"
  use_real_robot: true

analysis:
  enabled: true
  metrics:
    frequency:
      enabled: true
    time_sync:
      enabled: true
```

### 示例2: 遥操作录制

```yaml
task_info:
  name: "teleoperation_demo"

recording:
  enabled: true
  duration: 60
  topics:
    camera:
      enabled: false  # 不录制相机
    control:
      enabled: true
      topics: ["/right_arm_joint_control"]
    robot_state:
      enabled: true
      topics: ["/robot1/right_arm/joint_states"]
    exoskeleton:
      enabled: true  # 录制外骨骼数据
      topics: ["/exo_right_joint_states"]

control:
  mode: "teleoperation"
  use_real_robot: true

analysis:
  enabled: true
  metrics:
    frequency:
      enabled: true
    time_sync:
      enabled: true
    trajectory:
      enabled: true
```

### 示例3: 仅分析（不录制）

```yaml
task_info:
  name: "data_analysis_only"

recording:
  enabled: false  # 禁用录制

control:
  mode: "none"

analysis:
  enabled: true
  metrics:
    frequency:
      enabled: true
    time_sync:
      enabled: true
    integrity:
      enabled: true
    trajectory:
      enabled: true
    performance:
      enabled: true  # 启用高级性能分析

  visualization:
    enabled: true
    plot_formats: ["png", "pdf", "svg"]

  reporting:
    enabled: true
    formats: ["json", "markdown", "html"]
```

### 示例4: 快速测试（最小配置）

```yaml
task_info:
  name: "quick_test"

recording:
  enabled: true
  duration: 10
  topics:
    control:
      enabled: true
      topics: ["/right_arm_joint_control"]
    robot_state:
      enabled: true
      topics: ["/robot1/right_arm/joint_states"]

control:
  mode: "none"
  use_real_robot: false

analysis:
  enabled: false
```

## 🔧 高级功能

### 并行分析

```yaml
advanced:
  parallel_analysis: true
  num_workers: 4
```

### 调试模式

```yaml
advanced:
  debug:
    enabled: true
    verbose: true
    save_logs: true
```

### 性能优化

```yaml
advanced:
  performance:
    buffer_size: 1024
    batch_size: 100
    use_cache: true
```

## 📊 工作流程

### 完整工作流程

```bash
# 1. 创建配置
cp config/full_config_example.yaml config/my_experiment.yaml
vim config/my_experiment.yaml

# 2. 运行完整流程
python scripts/configurable_manager.py run --config config/my_experiment.yaml

# 3. 查看结果
ls data/collection/my_experiment/
ls data/analysis/my_experiment/
```

### 分步工作流程

```bash
# 1. 仅录制
python scripts/configurable_manager.py record --config config/my_experiment.yaml

# 2. 稍后分析
python scripts/configurable_manager.py analyze \
    --config config/my_experiment.yaml \
    --episode data/collection/my_experiment/session_*/episode_000000
```

## 🎓 最佳实践

### 1. 为不同任务创建不同配置

```bash
config/
├── vision_control.yaml      # 视觉控制任务
├── teleoperation.yaml       # 遥操作任务
├── hybrid_control.yaml      # 混合控制任务
└── analysis_only.yaml       # 仅分析
```

### 2. 使用版本控制管理配置

```bash
git add config/*.yaml
git commit -m "Add task configurations"
```

### 3. 记录配置变更

在配置文件中添加注释：

```yaml
# 修改历史:
# 2026-02-24: 增加相机话题
# 2026-02-23: 调整时间同步阈值
```

### 4. 验证配置

```bash
# 使用快速测试验证配置
python scripts/configurable_manager.py record \
    --config config/my_config.yaml \
    --duration 5
```

## 🔍 故障排除

### 问题1: 控制节点未运行

**错误**: "未检测到控制节点"

**解决**:
1. 启动控制系统
2. 或设置 `control.use_real_robot: false`
3. 或设置 `control.mode: "none"`

### 问题2: 话题不存在

**错误**: "话题 /xxx 不存在"

**解决**:
1. 检查话题名称是否正确
2. 使用 `ros2 topic list` 查看可用话题
3. 禁用不需要的话题类别

### 问题3: 分析失败

**错误**: "rosbag目录不存在"

**解决**:
1. 确认Episode路径正确
2. 检查录制是否成功
3. 查看录制日志

## 📚 相关文档

- [数据管理规范化方案](DATA_MANAGEMENT_STANDARDIZATION.md)
- [鲁棒数据采集系统设计](ROBUST_DATA_COLLECTION_DESIGN.md)
- [数据采集对比分析](DATA_COLLECTION_COMPARISON.md)

---

**配置化系统让VIST更灵活、更强大！**