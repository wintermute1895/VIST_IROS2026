# 配置化数据录制报告

**录制时间**: 2026年 02月 24日 星期二 12:34:21 CST
**录制时长**: 15秒
**录制模式**: both

## 1. 配置信息

```yaml
# 数据录制配置文件
# 用于配置录制哪些话题，支持多层级数据采集

# 录制模式
recording_mode:
  # 可选: raw, processed, both
  # raw: 只录制原始输出（如 /right_arm_joint_control）
  # processed: 只录制处理后的数据（如 /robot1/right_arm/joint_follow）
  # both: 同时录制两者
  mode: "both"

# 话题配置
topics:
  # 遥操臂原始输出
  exo_raw:
    enabled: true
    topic: "/right_arm_joint_control"
    description: "遥操臂传感器原始读数（81.5Hz）"

  # 遥操臂处理后输出
  exo_processed:
    enabled: true
    topic: "/robot1/right_arm/joint_follow"
    description: "经过桥接处理后的数据（单位转换、限位检查）"

  # 视觉控制原始输出
  vision_raw:
    enabled: false
    topic: "/vision_right_joint_control"
    description: "视觉算法计算的关节角度（30Hz）"

  # 视觉控制插值后输出
  vision_resampled:
    enabled: false
    topic: "/robot1/right_arm/joint_follow"
    description: "经过高频重采样后的数据（200Hz）"

  # 真机反馈（如果连接真机）
  robot_feedback:
    enabled: true
    topic: "/robot1/right_arm/joint_states"
    description: "真机实际执行的关节角度反馈"

# 评估配置
evaluation:
  # 评估哪个话题的数据
  # 可选: raw, processed, feedback
  target: "processed"

  # 是否对比多个话题
  compare_topics: true

  # 对比的话题列表
  comparison_topics:
    - "/right_arm_joint_control"
    - "/robot1/right_arm/joint_follow"

# 数据保存配置
output:
  # 保存目录
  base_dir: "data/recordings"

  # 是否保存原始rosbag
  save_rosbag: true

  # 是否生成评估报告
  generate_report: true

  # 是否生成可视化图表
  generate_plots: true

# 频率分析配置
frequency_analysis:
  # 是否进行频率分析
  enabled: true

  # 是否检测频率不一致
  check_consistency: true

  # 期望的频率范围
  expected_frequencies:
    exo_raw: [80, 85]  # Hz
    vision_raw: [28, 32]  # Hz
    processed: [195, 205]  # Hz

# 数据质量检查
quality_checks:
  # 是否检查数据完整性
  check_completeness: true

  # 是否检查数据连续性
  check_continuity: true

  # 是否检查异常值
  check_outliers: true

  # 异常值阈值（标准差倍数）
  outlier_threshold: 3.0

# 注意：关节方向映射已移至控制配置
# 请在 external_sdk/arm_teleop/src/lbot_teleop/config/teleop_config.yaml 中配置
# 录制的数据是经过方向映射后的数据，不需要后处理
```

## 2. 录制的话题

```
/right_arm_joint_control /robot1/right_arm/joint_follow /robot1/right_arm/joint_states
```

## 3. 录制的数据

```

Files:             rosbag_0.db3
Bag size:          1.4 MiB
Storage id:        sqlite3
Duration:          18.842718180s
Start:             Feb 24 2026 12:34:01.764618923 (1771907641.764618923)
End:               Feb 24 2026 12:34:20.607337103 (1771907660.607337103)
Messages:          5421
Topic information: Topic: /right_arm_joint_control | Type: sensor_msgs/msg/JointState | Count: 4527 | Serialization Format: cdr
                   Topic: /robot1/right_arm/joint_states | Type: sensor_msgs/msg/JointState | Count: 894 | Serialization Format: cdr
```

## 4. 频率分析

```
========================================
话题频率汇总
========================================

话题: /right_arm_joint_control
average rate: 240.036
	min: 0.000s max: 0.015s std dev: 0.00531s window: 2892
average rate: 239.988
	min: 0.000s max: 0.015s std dev: 0.00532s window: 3132

话题: /robot1/right_arm/joint_follow

话题: /robot1/right_arm/joint_states
average rate: 49.990
	min: 0.011s max: 0.028s std dev: 0.00268s window: 610
average rate: 49.985
	min: 0.011s max: 0.028s std dev: 0.00274s window: 661
```

## 5. 数据层级说明

根据录制的话题，数据包含以下层级：

- **原始输出**: 控制算法的直接输出（如 /right_arm_joint_control, /vision_right_joint_control）
- **处理后输出**: 经过桥接/插值处理的数据（如 /robot1/right_arm/joint_follow）
- **真机反馈**: 真实机器人执行后的反馈（如 /robot1/right_arm/joint_states）

## 6. 评估建议

1. **对比原始输出**: 比较不同控制方法的算法输出
2. **对比处理后输出**: 比较实际发送给真机的指令
3. **分析频率差异**: 检查不同层级的频率变化
4. **验证数据一致性**: 确保数据格式和单位统一

## 7. 下一步

```bash
# 评估录制的数据
python scripts/evaluate_vision_performance.py \
    --rosbag /home/ilex/Dev/VIST/data/recordings/rec_20260224_123358/rosbag \
    --config config/evaluation_config.yaml \
    --output /home/ilex/Dev/VIST/data/recordings/rec_20260224_123358/evaluation

# 对比多个话题
python scripts/compare_topics.py \
    --rosbag /home/ilex/Dev/VIST/data/recordings/rec_20260224_123358/rosbag \
    --topics "/right_arm_joint_control /robot1/right_arm/joint_follow /robot1/right_arm/joint_states"
```

