# CSV记录采样频率说明

## 采样频率：80 Hz

### 配置位置
- 文件：`ros2_ws/src/nodes/vist_filter_node.py`
- 参数：`output_freq_hz = 80.0` (第244行)
- 定时器周期：`timer_period = 1.0 / 80.0 = 12.5 ms`

### 实际测量结果

从 `vist_monitor_20260303_163539.csv` 分析：

```
总记录数: 2964 条
时间跨度: 37.04 秒
平均采样间隔: 12.50 ms
实际采样频率: 80.19 Hz (误差 0.2%)
```

**结论：CSV记录的采样频率是 80 Hz，与配置一致。**

---

## 重要区分：采样频率 vs 单帧执行频率

### 1. 采样频率 (Sampling Frequency)
- **定义**：每秒记录多少条数据
- **计算方式**：`1 / (timestamp[i+1] - timestamp[i])`
- **实际值**：80 Hz
- **含义**：ROS2定时器每秒调用80次 `update()` 函数

### 2. 单帧执行频率 (Frame Processing Frequency)
- **定义**：如果每帧都像当前帧这么快，理论上能达到的频率
- **计算方式**：`1 / frame_duration`
- **CSV列名**：`frame_frequency_hz`
- **实际值**：平均 1355 Hz，范围 394-3109 Hz
- **含义**：单帧执行只需要 0.7 ms，理论上可以跑到 1355 Hz

### 对比表格

| 指标 | 采样频率 | 单帧执行频率 |
|------|---------|-------------|
| 数值 | 80 Hz | 1355 Hz (平均) |
| 含义 | 实际采样率 | 理论最大频率 |
| 计算 | 1/采样间隔 | 1/单帧耗时 |
| CSV列 | 从timestamp计算 | frame_frequency_hz |
| 限制因素 | ROS2定时器 | 算法执行速度 |

---

## 为什么单帧执行频率这么高？

### 单帧平均耗时：0.77 ms

从CSV数据：
```
frame_duration_ms 平均值: 0.77 ms
frame_duration_ms 中位数: 0.74 ms
```

这意味着VIST算法执行一次只需要 **0.77 毫秒**！

### 性能分析

如果算法执行需要 0.77 ms，理论上可以达到：
```
理论最大频率 = 1 / 0.00077 s ≈ 1300 Hz
```

但实际采样频率被限制在 80 Hz，因为：
1. ROS2定时器设置为 80 Hz
2. 每个周期 (12.5 ms) 中：
   - 算法执行：0.77 ms (6%)
   - 等待下一个周期：11.73 ms (94%)

### CPU利用率

```
CPU利用率 = 0.77 ms / 12.5 ms = 6.2%
```

**结论：算法非常高效，CPU大部分时间在空闲等待！**

---

## 数据记录机制

### 记录时机
每次 `update()` 函数被调用时记录一条数据：

```python
# vist_kalman_filter.py 第884-915行
if self._monitor_log_enabled:
    monitor_record = {
        'timestamp': time.time(),
        'iteration': self.iteration_count,
        'frame_duration_ms': frame_duration * 1000,
        'frame_frequency_hz': 1.0 / frame_duration,  # 理论最大频率
        ...
    }
    self._monitor_data_buffer.append(monitor_record)
```

### 记录频率 = 采样频率 = 80 Hz

- 定时器每 12.5 ms 触发一次
- 每次触发调用 `update()`
- 每次 `update()` 记录一条数据
- 因此记录频率 = 80 Hz

---

## 如何提高采样频率？

如果需要更高的采样频率（例如 200 Hz），需要修改配置：

### 方法1：修改配置文件
```yaml
# config/baseline_filters_config.yaml
/vist_filter_node:
  ros__parameters:
    output_freq_hz: 200.0  # 改为200 Hz
```

### 方法2：启动时指定参数
```bash
ros2 launch bringup vist_filter.launch.py output_freq_hz:=200.0
```

### 性能余量

当前算法执行耗时 0.77 ms，理论上可以支持：
```
最大安全频率 = 1 / (0.77 ms * 1.5) ≈ 866 Hz
```

考虑1.5倍安全系数，实际可以稳定运行到 **500-800 Hz**。

---

## 总结

| 问题 | 答案 |
|------|------|
| CSV记录的采样频率是多少？ | **80 Hz** |
| 为什么frame_frequency_hz显示1355 Hz？ | 这是单帧执行速度，不是采样频率 |
| 算法执行需要多长时间？ | 平均 **0.77 ms** |
| CPU利用率是多少？ | **6.2%** (大部分时间在等待) |
| 可以提高采样频率吗？ | 可以，理论上可达 **500-800 Hz** |
| 如何提高采样频率？ | 修改 `output_freq_hz` 参数 |

**关键理解**：
- **采样频率 (80 Hz)** = 数据记录的频率 = ROS2定时器频率
- **单帧执行频率 (1355 Hz)** = 算法理论最大频率 = 1/单帧耗时
- 两者不同，前者是实际采样率，后者是性能指标
