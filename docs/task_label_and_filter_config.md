# 任务标签和滤波器类型配置说明

## 📝 修改总结

### 1. 配置文件更新 (recording_config.yaml)

在配置文件顶部添加了实验配置部分：

```yaml
# 实验配置
experiment:
  # 任务标签（用于标识当前录制的任务类型）
  task_label: "grab_object"  # 可选: grab_object, place_object, push_button, etc.

  # 滤波器类型（用于判断是否记录意图因子）
  filter_type: "vist"  # 可选: vist, one_euro, kalman, none
```

### 2. 数据采集脚本更新 (collect_experiment.py)

#### 2.1 条件记录意图因子
- ✅ 只有当 `filter_type: "vist"` 时才记录和分析意图因子
- ✅ 其他滤波器类型会跳过意图因子分析，避免不必要的处理

```python
filter_type = config.get('experiment', {}).get('filter_type', 'vist')
if record_exit_code == 0 and filter_type == 'vist' and '/vist_intent_factors' in topics:
    print(Colors.yellow(f"检测到VIST滤波器，正在提取意图因子..."))
    extract_and_visualize_intent_factors(data_dir)
elif record_exit_code == 0 and filter_type != 'vist':
    print(Colors.blue(f"当前滤波器类型: {filter_type}，跳过意图因子分析"))
```

#### 2.2 任务标签记录到元数据
- ✅ 任务标签和滤波器类型自动保存到 `experiment_metadata.yaml`
- ✅ 每次录制都会生成包含任务信息的元数据文件

```python
metadata = {
    'experiment': {
        'name': experiment_name,
        'type': 'teleoperation_experiment',
        'duration': f'{duration}s',
        'timestamp': datetime.now().isoformat(),
        'task_label': config.get('experiment', {}).get('task_label', ''),
        'filter_type': config.get('experiment', {}).get('filter_type', 'vist')
    },
    ...
}
```

### 3. LeRobot转换脚本更新 (convert_rosbag_to_lerobot.py)

#### 3.1 自动读取任务标签
- ✅ 新增 `load_task_label_from_metadata()` 函数
- ✅ 转换时优先从元数据读取任务标签
- ✅ 如果元数据中没有，则使用命令行参数
- ✅ 都没有则使用默认值

```python
# 尝试从元数据读取任务标签（优先级高于命令行参数）
metadata_task_label = load_task_label_from_metadata(bag_path)
if metadata_task_label:
    task_name = metadata_task_label
    logger.info(f"使用元数据中的任务标签: '{task_name}'")
else:
    logger.info(f"使用命令行指定的任务标签: '{task_name}'")
```

## 🎯 使用方法

### 录制数据时配置任务标签

编辑 `config/recording_config.yaml`：

```yaml
experiment:
  task_label: "grab_cup"      # 修改为你的任务名称
  filter_type: "vist"         # 或 "one_euro", "kalman", "none"
```

### 不同滤波器的行为

| 滤波器类型 | 意图因子记录 | 意图因子分析 | 说明 |
|-----------|------------|------------|------|
| `vist` | ✅ 是 | ✅ 是 | 完整的VIST功能 |
| `one_euro` | ❌ 否 | ❌ 否 | 跳过意图因子 |
| `kalman` | ❌ 否 | ❌ 否 | 跳过意图因子 |
| `none` | ❌ 否 | ❌ 否 | 跳过意图因子 |

### 转换为LeRobot格式

转换脚本会自动从元数据读取任务标签：

```bash
# 单个转换（自动读取任务标签）
python3 scripts/experiment/convert_rosbag_to_lerobot.py \
    --bag-path /path/to/experiment_xxx \
    --repo-id username/dataset

# 批量转换（自动读取每个experiment的任务标签）
python3 scripts/experiment/convert_rosbag_to_lerobot.py \
    --input-dir /path/to/experiments \
    --repo-id username/dataset

# 也可以手动指定任务标签（会被元数据覆盖）
python3 scripts/experiment/convert_rosbag_to_lerobot.py \
    --bag-path /path/to/experiment_xxx \
    --repo-id username/dataset \
    --task-name grab_object  # 如果元数据中有，这个会被忽略
```

## 📊 元数据文件示例

录制完成后，会在数据目录生成 `experiment_metadata.yaml`：

```yaml
experiment:
  name: experiment_20260305_163611
  type: teleoperation_experiment
  duration: 60s
  timestamp: '2026-03-05T16:36:11.123456'
  task_label: grab_cup          # 任务标签
  filter_type: vist              # 滤波器类型
components:
  - camera: RealSense D435i
  - left_arm: Linkerta Exoskeleton
  - dexterous_hand: Linker Hand L10 (Left)
  - robot: Controlled Robot Arm
recorded_topics:
  - /camera_global/camera_global/color/image_raw
  - /camera_wrist/camera_wrist/color/image_raw
  - /joint_states
  - /action
  ...
```

## 🔧 常见任务标签示例

```yaml
# 抓取任务
task_label: "grab_object"
task_label: "grab_cup"
task_label: "pick_and_place"

# 放置任务
task_label: "place_object"
task_label: "stack_blocks"

# 操作任务
task_label: "push_button"
task_label: "open_drawer"
task_label: "close_door"

# 组合任务
task_label: "pour_water"
task_label: "wipe_table"
```

## ✅ 优势

1. **自动化**: 任务标签在录制时配置，转换时自动读取
2. **一致性**: 避免手动输入错误
3. **灵活性**: 支持命令行覆盖（如果需要）
4. **可追溯**: 元数据文件记录完整的实验信息
5. **条件处理**: 根据滤波器类型智能决定是否处理意图因子

## 📌 注意事项

1. **任务标签为空**: 如果不设置task_label，转换时会使用命令行参数或默认值
2. **滤波器类型**: 确保filter_type与实际使用的滤波器一致
3. **元数据优先**: 转换时元数据中的任务标签优先级最高
4. **批量转换**: 每个experiment可以有不同的任务标签
