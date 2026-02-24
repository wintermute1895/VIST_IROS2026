# ROS2性能监控工具使用指南

## 功能特性

这个工具可以监控ROS2遥操作系统的性能指标：

1. **控制频率监控**：实时监控话题发布频率
2. **延迟测量**：计算端到端延迟（基于消息时间戳）
3. **统计分析**：计算平均值、标准差、最大最小值
4. **数据记录**：将所有数据保存到CSV文件
5. **实时显示**：定期打印统计信息
6. **离线分析**：提供数据分析脚本和图表生成

## 安装

### 1. 编译ROS2包

```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash
colcon build --packages-select performance_monitor
source install/setup.bash
```

### 2. 安装可选依赖（用于图表生成）

```bash
pip install matplotlib numpy
```

## 使用方法

### 方式一：使用启动脚本（推荐）

```bash
bash /home/ilex/Dev/VIST/scripts/start_performance_monitor.sh
```

### 方式二：使用launch文件

```bash
# 使用默认参数
ros2 launch performance_monitor performance_monitor.launch.py

# 自定义参数
ros2 launch performance_monitor performance_monitor.launch.py \
    input_topic:=/cb_left_hand_control_cmd \
    output_file:=my_performance_log.csv \
    print_interval:=10.0
```

### 方式三：直接运行节点

```bash
ros2 run performance_monitor performance_monitor \
    --ros-args \
    -p input_topic:=/cb_left_hand_control_cmd \
    -p output_file:=performance_log.csv \
    -p print_interval:=5.0
```

## 参数说明

- `input_topic`：要监控的输入话题（默认：`/cb_left_hand_control_cmd`）
- `output_topic`：要监控的输出话题（可选，用于计算往返延迟）
- `output_file`：性能数据输出文件（默认：`performance_log.csv`）
- `window_size`：统计窗口大小（默认：100）
- `print_interval`：打印统计信息的间隔，单位秒（默认：5.0）

## 输出说明

### 实时输出

每隔`print_interval`秒，会打印统计信息：

```
============================================================
性能统计 (运行时间: 30.5秒)
消息总数: 915
平均频率: 30.02 Hz (±0.15)
平均延迟: 2.35 ms (±0.42)
延迟范围: [1.85, 4.23] ms
============================================================
```

### CSV文件

数据会实时保存到CSV文件，包含以下列：

- `timestamp`：时间戳
- `message_count`：消息计数
- `frequency_hz`：瞬时频率
- `latency_ms`：瞬时延迟
- `avg_frequency`：平均频率（窗口内）
- `std_frequency`：频率标准差
- `avg_latency`：平均延迟
- `std_latency`：延迟标准差
- `min_latency`：最小延迟
- `max_latency`：最大延迟

## 数据分析

### 使用分析脚本

```bash
# 分析CSV文件
ros2 run performance_monitor analyze_performance performance_log.csv

# 或者直接运行Python脚本
python3 /home/ilex/Dev/VIST/src/performance_monitor/performance_monitor/analyze_performance.py performance_log.csv
```

分析脚本会：
1. 计算详细的统计指标（平均值、标准差、中位数、百分位数）
2. 生成图表（如果安装了matplotlib）
3. 保存图表为PNG文件

### 输出示例

```
============================================================
性能分析报告
============================================================
数据文件: performance_log.csv
数据点数: 1830
时间范围: 61.02 秒

频率统计:
  平均值: 30.01 Hz
  标准差: 0.18 Hz
  最小值: 29.45 Hz
  最大值: 30.52 Hz
  中位数: 30.00 Hz

延迟统计:
  平均值: 2.42 ms
  标准差: 0.51 ms
  最小值: 1.75 ms
  最大值: 5.12 ms
  中位数: 2.38 ms
  P50: 2.38 ms
  P95: 3.45 ms
  P99: 4.23 ms
============================================================

图表已保存到: performance_log_plot.png
```

## 使用场景

### 1. 手套遥操作性能测试

```bash
# 终端1：启动手套节点
bash /home/ilex/Dev/VIST/scripts/test_hand_glove_noconda.sh

# 终端2：启动灵巧手驱动
bash /home/ilex/Dev/VIST/scripts/start_hand_driver.sh

# 终端3：启动性能监控
bash /home/ilex/Dev/VIST/scripts/start_performance_monitor.sh

# 进行遥操作测试...

# 测试完成后，分析数据
ros2 run performance_monitor analyze_performance performance_log.csv
```

### 2. 机械臂遥操作性能测试

```bash
# 修改监控话题
ros2 launch performance_monitor performance_monitor.launch.py \
    input_topic:=/robot_control_cmd \
    output_file:=robot_performance_log.csv
```

### 3. 对比不同配置的性能

```bash
# 测试配置1
ros2 launch performance_monitor performance_monitor.launch.py \
    output_file:=config1_performance.csv

# 测试配置2
ros2 launch performance_monitor performance_monitor.launch.py \
    output_file:=config2_performance.csv

# 对比分析
ros2 run performance_monitor analyze_performance config1_performance.csv
ros2 run performance_monitor analyze_performance config2_performance.csv
```

## 注意事项

1. **时间戳要求**：延迟测量依赖于消息的`header.stamp`字段，确保发布者正确设置时间戳
2. **系统时钟**：确保系统时钟同步，避免时间戳异常
3. **文件权限**：确保有写入CSV文件的权限
4. **磁盘空间**：长时间运行会产生大量数据，注意磁盘空间
5. **性能影响**：监控本身会占用少量CPU和内存，对高频率系统影响较小

## 故障排查

### 问题：没有延迟数据

**原因**：消息没有时间戳或时间戳为0

**解决**：在发布者中添加时间戳：
```python
msg.header.stamp = self.get_clock().now().to_msg()
```

### 问题：频率异常

**原因**：话题没有数据或发布频率不稳定

**解决**：
```bash
# 检查话题是否存在
ros2 topic list

# 检查话题数据
ros2 topic echo /cb_left_hand_control_cmd

# 检查话题频率
ros2 topic hz /cb_left_hand_control_cmd
```

### 问题：CSV文件为空

**原因**：没有接收到消息或文件权限问题

**解决**：
- 检查话题名称是否正确
- 检查文件路径和权限
- 查看节点日志

## 扩展功能

### 添加自定义指标

编辑`performance_monitor.py`，在`input_callback`中添加自定义计算：

```python
def input_callback(self, msg):
    # 现有代码...

    # 添加自定义指标
    custom_metric = calculate_custom_metric(msg)
    self.custom_metrics.append(custom_metric)
```

### 监控多个话题

创建多个监控节点实例，每个监控不同的话题：

```bash
# 终端1：监控手套输入
ros2 run performance_monitor performance_monitor \
    --ros-args -p input_topic:=/cb_left_hand_control_cmd \
    -p output_file:=glove_performance.csv

# 终端2：监控机械臂输入
ros2 run performance_monitor performance_monitor \
    --ros-args -p input_topic:=/robot_control_cmd \
    -p output_file:=robot_performance.csv
```

## 参考资料

- ROS2文档：https://docs.ros.org/
- sensor_msgs/JointState：http://docs.ros.org/en/api/sensor_msgs/html/msg/JointState.html
- rosbag2：https://github.com/ros2/rosbag2
