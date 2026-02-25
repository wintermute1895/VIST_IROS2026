# 外骨骼数据采集指南（不连接机器人）

## 目标
采集两组对比数据：
1. **无滤波（Passthrough）** - 外骨骼原始数据直接透传
2. **One-Euro滤波** - 外骨骼数据经过One-Euro滤波

## 前置条件
- ✅ 外骨骼遥操臂（linkerta）已连接并正常工作
- ✅ ROS2环境已配置
- ❌ **不需要**连接真机机器人（lbot_driver）

---

## 第一组：无滤波数据采集

### 步骤1: 打开终端1 - 启动外骨骼节点（无滤波）

```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

# 只启动linkerta节点，不启动lbot_driver
ros2 run linkerta linkerta_node
```

**预期输出**: 外骨骼节点启动，发布话题 `/left_arm_joint_control` 和 `/right_arm_joint_control`

### 步骤2: 打开终端2 - 启动rosbag录制（无滤波）

```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash

# 创建数据目录
mkdir -p data/exo_raw_$(date +%Y%m%d_%H%M%S)
cd data/exo_raw_$(date +%Y%m%d_%H%M%S)

# 录制外骨骼原始数据（右臂为例）
ros2 bag record \
  /right_arm_joint_control \
  /left_arm_joint_control \
  -o exo_raw_data
```

**说明**:
- 录制外骨骼发布的原始关节角度数据
- 如果只用右臂，可以只录 `/right_arm_joint_control`

### 步骤3: 执行遥操动作

在外骨骼上执行你想要的动作序列，例如：
- 抓取动作
- 移动轨迹
- 重复性动作

**建议**: 录制30-60秒的数据

### 步骤4: 停止录制

在终端2按 `Ctrl+C` 停止rosbag录制

### 步骤5: 停止外骨骼节点

在终端1按 `Ctrl+C` 停止linkerta节点

---

## 第二组：One-Euro滤波数据采集

### 步骤1: 打开终端1 - 启动外骨骼节点

```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

# 启动linkerta节点
ros2 run linkerta linkerta_node
```

### 步骤2: 打开终端2 - 启动One-Euro滤波节点

```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash

# 使用简化的滤波节点（推荐）
python3 src/nodes/simple_filter_node.py \
  --ros-args \
  -p filter_type:=one_euro \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p one_euro_min_cutoff:=1.0 \
  -p one_euro_beta:=0.007
```

**预期输出**:
- 订阅 `/right_arm_joint_control` (外骨骼原始数据)
- 发布 `/filtered_right_joint_control` (One-Euro滤波后数据)

### 步骤3: 打开终端3 - 启动rosbag录制（滤波后）

```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash

# 创建数据目录
mkdir -p data/exo_oneeuro_$(date +%Y%m%d_%H%M%S)
cd data/exo_oneeuro_$(date +%Y%m%d_%H%M%S)

# 录制原始数据和滤波后数据（对比）
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  -o exo_oneeuro_data
```

**说明**: 同时录制原始和滤波后的数据，方便对比

### 步骤4: 执行相同的遥操动作

**重要**: 尽量重复第一组的动作序列，保证对比的公平性

### 步骤5: 停止所有节点

1. 终端3: `Ctrl+C` 停止rosbag
2. 终端2: `Ctrl+C` 停止滤波节点
3. 终端1: `Ctrl+C` 停止外骨骼节点

---

## 数据分析

### 查看录制的数据

```bash
# 查看bag信息
ros2 bag info data/exo_raw_XXXXXX/exo_raw_data
ros2 bag info data/exo_oneeuro_XXXXXX/exo_oneeuro_data

# 查看话题列表
ros2 bag info data/exo_raw_XXXXXX/exo_raw_data | grep topics -A 10
```

### 提取数据进行分析

```bash
cd /home/ilex/Dev/VIST

# 提取关节角度数据
python3 scripts/extract_joint_follow.py \
  --bag data/exo_raw_XXXXXX/exo_raw_data \
  --output data/exo_raw_XXXXXX/joints.csv

python3 scripts/extract_joint_follow.py \
  --bag data/exo_oneeuro_XXXXXX/exo_oneeuro_data \
  --output data/exo_oneeuro_XXXXXX/joints.csv
```

---

## 常见问题

### Q1: 滤波节点找不到？

**解决方案**: 使用简化的滤波节点

```bash
cd /home/ilex/Dev/VIST
python3 src/nodes/simple_filter_node.py --ros-args -p filter_type:=one_euro
```

### Q2: 如何验证滤波器是否工作？

**方法1**: 实时监控话题

```bash
# 终端A: 监控原始数据
ros2 topic echo /right_arm_joint_control

# 终端B: 监控滤波后数据
ros2 topic echo /filtered_right_joint_control
```

**方法2**: 使用rqt_plot可视化

```bash
rqt_plot /right_arm_joint_control/joints[0] /filtered_right_joint_control/joints[0]
```

### Q3: 如何调整One-Euro滤波器参数？

修改启动命令中的参数：
- `one_euro_min_cutoff`: 最小截止频率（越小越平滑，默认1.0）
- `one_euro_beta`: 速度敏感度（越大对速度变化越敏感，默认0.007）

---

## 数据目录结构

```
data/
├── exo_raw_20260225_143000/
│   ├── exo_raw_data/
│   │   ├── metadata.yaml
│   │   └── exo_raw_data_0.db3
│   └── joints.csv (提取后)
│
└── exo_oneeuro_20260225_143500/
    ├── exo_oneeuro_data/
    │   ├── metadata.yaml
    │   └── exo_oneeuro_data_0.db3
    └── joints.csv (提取后)
```

---

## 下一步

采集完数据后，可以使用以下脚本进行分析：

```bash
# 对比分析
python3 scripts/compare_filters.py \
  --raw data/exo_raw_XXXXXX/joints.csv \
  --filtered data/exo_oneeuro_XXXXXX/joints.csv \
  --output results/filter_comparison.png
```