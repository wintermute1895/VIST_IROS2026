# LinkerTA 遥操臂调试指南

## 🔌 第一步：检查LinkerTA是否连接

```bash
# 1. 检查USB设备
lsusb | grep -i linker

# 2. 检查串口设备
ls -l /dev/ttyUSB* /dev/ttyACM*

# 3. 检查LinkerTA进程
ps aux | grep -i linkerta
```

## 📡 第二步：查看ROS2话题

### 快速检查
```bash
cd /home/ilex/Dev/VIST

# 查看所有话题
ros2 topic list

# 查看与arm相关的话题
ros2 topic list | grep -E "(arm|joint|linkerta)"

# 常见的LinkerTA话题名称：
# - /left_arm_joint_control
# - /right_arm_joint_control
# - /linkerta/left_arm/joint_states
# - /linkerta/right_arm/joint_states
```

### 使用调试脚本（推荐）
```bash
# 运行LinkerTA调试工具
./debug_linkerta_data.sh

# 会显示菜单，选择相应的调试模式
```

## 🔍 第三步：实时监控数据

### 方法1：使用监控脚本（推荐）
```bash
# 监控左臂数据
python3 monitor_linkerta_realtime.py /left_arm_joint_control

# 监控右臂数据
python3 monitor_linkerta_realtime.py /right_arm_joint_control

# 会显示：
# - 当前关节角度
# - 接收频率
# - 数据质量
# - 健康状态
```

### 方法2：使用ROS2命令行工具

#### 查看话题信息
```bash
# 查看话题类型和发布者
ros2 topic info /left_arm_joint_control -v

# 输出示例：
# Type: sensor_msgs/msg/JointState
# Publisher count: 1
# Subscription count: 0
```

#### 查看话题频率
```bash
# 查看发布频率（应该在50-100Hz）
ros2 topic hz /left_arm_joint_control

# 输出示例：
# average rate: 80.123
#   min: 0.012s max: 0.013s std dev: 0.00012s window: 100
```

#### 实时查看数据
```bash
# 查看原始数据
ros2 topic echo /left_arm_joint_control

# 只看关节位置
ros2 topic echo /left_arm_joint_control --field position

# 限制显示次数
ros2 topic echo /left_arm_joint_control --once
```

## 📊 第四步：数据格式检查

LinkerTA发布的数据应该是 `sensor_msgs/msg/JointState` 格式：

```yaml
header:
  stamp:
    sec: 1234567890
    nanosec: 123456789
  frame_id: 'base_link'
name: ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6', 'joint_7']
position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # 7个关节角度
velocity: []  # 可选
effort: []    # 可选
```

### 检查数据单位

```bash
# 查看一次数据
ros2 topic echo /left_arm_joint_control --once

# 判断单位：
# - 如果数值在 [-180, 180] 范围 → 角度（degree）
# - 如果数值在 [-3.14, 3.14] 范围 → 弧度（radian）
```

## 🐛 常见问题排查

### 问题1：找不到话题

```bash
# 检查LinkerTA驱动是否启动
ps aux | grep linkerta

# 如果没有，启动LinkerTA驱动
# （根据你的实际启动脚本）
cd /home/ilex/Dev/VIST/ros2_ws/src/external_sdk/linkerhand-ros-teleop
python3 start_linkerta.py  # 示例，根据实际情况调整
```

### 问题2：话题有数据但频率很低

```bash
# 检查频率
ros2 topic hz /left_arm_joint_control

# 如果频率 < 10 Hz：
# 1. 检查USB连接
# 2. 检查LinkerTA驱动日志
# 3. 重启LinkerTA驱动
```

### 问题3：数据全是0

```bash
# 使用监控脚本检查
python3 monitor_linkerta_realtime.py /left_arm_joint_control

# 如果"全零数据"比例 > 10%：
# 1. 检查LinkerTA是否正确初始化
# 2. 尝试移动遥操臂，看数据是否变化
# 3. 检查LinkerTA驱动配置
```

### 问题4：数据跳变很大

```bash
# 使用监控脚本检查
python3 monitor_linkerta_realtime.py /left_arm_joint_control

# 如果"大跳变"比例 > 5%：
# 1. 检查USB连接是否稳定
# 2. 检查LinkerTA驱动是否有错误日志
# 3. 可能需要重新标定LinkerTA
```

## 🎯 第五步：测试数据流

### 测试1：手动发布数据
```bash
# 手动发布测试数据到话题
ros2 topic pub --once /left_arm_joint_control sensor_msgs/msg/JointState \
  "{header: {frame_id: 'base_link'}, \
    position: [10.0, 20.0, 30.0, 0.0, 0.0, 0.0, 0.0]}"

# 检查滤波节点是否接收到
ros2 topic echo /filtered_left_joint_control --once
```

### 测试2：录制数据包
```bash
# 录制10秒的数据
ros2 bag record -o test_linkerta /left_arm_joint_control /right_arm_joint_control -d 10

# 回放数据
ros2 bag play test_linkerta

# 查看数据包信息
ros2 bag info test_linkerta
```

## 📈 第六步：可视化数据

### 使用rqt_plot（实时曲线）
```bash
# 安装rqt_plot（如果没有）
sudo apt install ros-humble-rqt-plot

# 绘制关节角度曲线
rqt_plot /left_arm_joint_control/position[0]:position[1]:position[2]
```

### 使用rqt_graph（节点拓扑）
```bash
# 查看节点和话题的连接关系
rqt_graph
```

### 使用Meshcat（3D可视化）
```bash
# 启动双臂可视化
python3 visualize_dual_arm_realtime.py

# 在浏览器中打开
# http://127.0.0.1:7000/static/
```

## 🔧 LinkerTA驱动配置

### 查找LinkerTA启动脚本
```bash
# 查找LinkerTA相关文件
find /home/ilex/Dev/VIST -name "*linkerta*" -o -name "*linker_arm*"

# 常见位置：
# - ros2_ws/src/external_sdk/linkerhand-ros-teleop/
# - scripts/
```

### 检查LinkerTA配置文件
```bash
# 查找配置文件
find /home/ilex/Dev/VIST -name "*.yaml" | xargs grep -l "linkerta"

# 常见配置项：
# - 串口设备: /dev/ttyUSB0
# - 波特率: 115200
# - 发布频率: 80 Hz
# - 话题名称: /left_arm_joint_control
```

## 📝 调试检查清单

- [ ] LinkerTA硬件已连接（USB）
- [ ] LinkerTA驱动已启动
- [ ] ROS2话题存在且有数据
- [ ] 话题频率正常（> 50 Hz）
- [ ] 数据格式正确（JointState）
- [ ] 数据单位正确（角度或弧度）
- [ ] 数据质量良好（无大量0值或跳变）
- [ ] 滤波节点能接收数据
- [ ] 可视化节点能显示运动

## 🚀 完整测试流程

```bash
# 1. 启动LinkerTA驱动（根据实际情况）
# cd /path/to/linkerta/driver
# python3 start_linkerta.py

# 2. 检查话题
ros2 topic list | grep arm

# 3. 监控数据
python3 monitor_linkerta_realtime.py /left_arm_joint_control

# 4. 启动滤波节点
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=left

# 5. 启动可视化
python3 visualize_dual_arm_realtime.py

# 6. 移动遥操臂，观察仿真中的运动
```

## 💡 提示

1. **先确认话题名称**：LinkerTA可能使用不同的话题名称，先用 `ros2 topic list` 确认
2. **检查数据单位**：确认是角度还是弧度，滤波节点需要正确的单位
3. **监控频率**：频率太低会导致控制不流畅
4. **数据质量**：使用监控脚本检查数据质量
5. **逐步测试**：先测试单臂，再测试双臂

---

**需要帮助？**
- 运行 `./debug_linkerta_data.sh` 获取交互式调试菜单
- 运行 `python3 monitor_linkerta_realtime.py <话题名>` 实时监控数据