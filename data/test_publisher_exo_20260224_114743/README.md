# 发布端数据流测试报告 - exo

**测试时间**: 2026年 02月 24日 星期二 11:48:05 CST
**测试模式**: exo
**测试时长**: 10秒

## 1. 发现的话题

```
/joint_error_code
/left_arm_joint_control
/right_arm_joint_control
```

## 2. 录制的数据

```

Files:             rosbag_0.db3
Bag size:          677.9 KiB
Storage id:        sqlite3
Duration:          13.836117015s
Start:             Feb 24 2026 11:47:51.404763000 (1771904871.404763000)
End:               Feb 24 2026 11:48:05.240880015 (1771904885.240880015)
Messages:          3390
Topic information: Topic: /joint_error_code | Type: std_msgs/msg/String | Count: 1130 | Serialization Format: cdr
                   Topic: /left_arm_joint_control | Type: sensor_msgs/msg/JointState | Count: 1130 | Serialization Format: cdr
                   Topic: /right_arm_joint_control | Type: sensor_msgs/msg/JointState | Count: 1130 | Serialization Format: cdr
```

## 3. 频率分析

```
========================================
话题频率汇总
========================================

话题: /joint_error_code
average rate: 80.769
	min: 0.012s max: 0.013s std dev: 0.00013s window: 82
average rate: 81.000
	min: 0.012s max: 0.013s std dev: 0.00013s window: 164
average rate: 81.211
	min: 0.012s max: 0.013s std dev: 0.00013s window: 246
average rate: 81.361
	min: 0.012s max: 0.013s std dev: 0.00012s window: 328
average rate: 81.446
	min: 0.012s max: 0.013s std dev: 0.00012s window: 410
average rate: 81.507
	min: 0.012s max: 0.013s std dev: 0.00012s window: 492
average rate: 81.530
	min: 0.012s max: 0.013s std dev: 0.00011s window: 574
average rate: 81.551
	min: 0.012s max: 0.013s std dev: 0.00011s window: 656

话题: /left_arm_joint_control
average rate: 80.717
	min: 0.012s max: 0.013s std dev: 0.00013s window: 82
average rate: 80.993
	min: 0.012s max: 0.013s std dev: 0.00013s window: 164
average rate: 81.211
	min: 0.012s max: 0.013s std dev: 0.00013s window: 246
average rate: 81.360
	min: 0.012s max: 0.013s std dev: 0.00013s window: 328
average rate: 81.447
	min: 0.012s max: 0.013s std dev: 0.00012s window: 410
average rate: 81.508
	min: 0.012s max: 0.013s std dev: 0.00012s window: 492
average rate: 81.529
	min: 0.012s max: 0.013s std dev: 0.00012s window: 574
average rate: 81.551
	min: 0.012s max: 0.013s std dev: 0.00011s window: 656

话题: /right_arm_joint_control
average rate: 80.728
	min: 0.012s max: 0.013s std dev: 0.00013s window: 82
average rate: 80.997
	min: 0.012s max: 0.013s std dev: 0.00013s window: 164
average rate: 81.212
	min: 0.012s max: 0.013s std dev: 0.00013s window: 246
average rate: 81.360
	min: 0.012s max: 0.013s std dev: 0.00013s window: 328
average rate: 81.447
	min: 0.012s max: 0.013s std dev: 0.00012s window: 410
average rate: 81.512
	min: 0.012s max: 0.013s std dev: 0.00012s window: 492
average rate: 81.530
	min: 0.012s max: 0.013s std dev: 0.00012s window: 574
average rate: 81.551
	min: 0.012s max: 0.013s std dev: 0.00011s window: 656
```

## 4. 消息数量统计

```
========================================
话题消息数量统计
========================================

Topic information: Topic: /joint_error_code | Type: std_msgs/msg/String | Count: 1130 | Serialization Format: cdr	                   Topic: /left_arm_joint_control | Type: sensor_msgs/msg/JointState | Count: 1130 | Serialization Format: cdr
                   Topic: /right_arm_joint_control | Type: sensor_msgs/msg/JointState | Count: 1130 | Serialization Format: cdr	
```

## 5. 结论

### 发布端分析

1. **哪个话题有数据？** → 这是发布端实际发布的话题
2. **实际频率是多少？** → 这是真实的发布频率
3. **消息数量是多少？** → 验证数据连续性

### 建议

根据上述分析：
- 如果要录制用于评估，应该录制 **消息数量最多** 的话题
- 确认这个话题是否会被机器人驱动订阅
- 如果需要插值，确认插值后的话题名称

