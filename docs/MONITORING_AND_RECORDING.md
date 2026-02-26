# VIST系统监控与数据采集指南

本文档描述系统调试、监控和数据采集所需的额外终端。

---

## 终端8 - 频率监控

用于实时监控所有关键topic的发布频率。

### 启动命令

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash

# 方法1: 逐个监控（推荐用于调试）
ros2 topic hz /camera/color/image_raw

# 方法2: 同时监控多个topic（使用tmux或多个窗口）
```

### 监控脚本

创建一个监控脚本来同时显示所有频率：

```bash
#!/bin/bash
# 监控所有关键topic的频率

echo "=== VIST系统频率监控 ==="
echo ""

echo "1. 相机频率:"
timeout 5 ros2 topic hz /camera/color/image_raw 2>&1 | grep "average rate" | tail -1

echo ""
echo "2. 外骨骼频率:"
timeout 5 ros2 topic hz /left_arm_joint_control 2>&1 | grep "average rate" | tail -1

echo ""
echo "3. 滤波器输出频率:"
timeout 5 ros2 topic hz /filtered_joint_states 2>&1 | grep "average rate" | tail -1

echo ""
echo "4. 数据手套频率:"
timeout 5 ros2 topic hz /cb_left_hand_control_cmd 2>&1 | grep "average rate" | tail -1

echo ""
echo "5. 机械臂控制频率:"
timeout 5 ros2 topic hz /robot1/left_arm/joint_follow 2>&1 | grep "average rate" | tail -1

echo ""
echo "=== 监控完成 ==="
```

### 预期频率

| Topic | 预期频率 | 备注 |
|-------|---------|------|
| `/camera/color/image_raw` | ~12-15 Hz | 禁用深度流后 |
| `/left_arm_joint_control` | ~80 Hz | 外骨骼原始数据 |
| `/filtered_joint_states` | ~80 Hz | 滤波后数据 |
| `/cb_left_hand_control_cmd` | ~30 Hz | 数据手套 |
| `/robot1/left_arm/joint_follow` | ~80 Hz | 机械臂控制命令 |

---

## 终端9 - Topic验证与数据流检查

用于验证所有topic是否正确发布，以及数据流是否正常。

### 启动命令

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
```

### 验证脚本

#### 1. 检查所有topic

```bash
# 列出所有活跃的topic
ros2 topic list

# 预期输出应包含:
# /camera/color/image_raw
# /camera/color/camera_info
# /left_arm_joint_control
# /filtered_joint_states
# /cb_left_hand_control_cmd
# /cb_left_hand_control_angle_cmd
# /robot1/left_arm/joint_follow
# /robot1/left_arm/joint_states
```

#### 2. 检查topic类型

```bash
# 验证topic的消息类型
ros2 topic type /camera/color/image_raw
# 预期: sensor_msgs/msg/Image

ros2 topic type /left_arm_joint_control
# 预期: sensor_msgs/msg/JointState

ros2 topic type /filtered_joint_states
# 预期: sensor_msgs/msg/JointState

ros2 topic type /cb_left_hand_control_cmd
# 预期: sensor_msgs/msg/JointState
```

#### 3. 查看topic数据

```bash
# 查看相机图像信息（不显示图像数据）
ros2 topic echo /camera/color/image_raw --no-arr

# 查看外骨骼关节数据
ros2 topic echo /left_arm_joint_control

# 查看滤波后的关节数据
ros2 topic echo /filtered_joint_states

# 查看数据手套命令
ros2 topic echo /cb_left_hand_control_cmd
```

#### 4. 完整验证脚本

```bash
#!/bin/bash
# 验证VIST系统所有topic

echo "=== VIST系统Topic验证 ==="
echo ""

# 检查必需的topic是否存在
REQUIRED_TOPICS=(
    "/camera/color/image_raw"
    "/left_arm_joint_control"
    "/filtered_joint_states"
    "/cb_left_hand_control_cmd"
    "/robot1/left_arm/joint_follow"
)

echo "检查必需的topic..."
for topic in "${REQUIRED_TOPICS[@]}"; do
    if ros2 topic list | grep -q "^${topic}$"; then
        echo "✓ $topic - 存在"
    else
        echo "✗ $topic - 缺失"
    fi
done

echo ""
echo "=== 验证完成 ==="
```

### 数据流验证

验证数据是否正确流动：

```bash
# 1. 验证外骨骼 → 滤波器
echo "测试: 外骨骼 → 滤波器"
echo "移动外骨骼，观察两个topic的数据是否同步变化："
ros2 topic echo /left_arm_joint_control &
ros2 topic echo /filtered_joint_states &

# 2. 验证滤波器 → 机械臂
echo "测试: 滤波器 → 机械臂"
echo "移动外骨骼，观察机械臂是否跟随："
ros2 topic echo /filtered_joint_states &
ros2 topic echo /robot1/left_arm/joint_follow &

# 3. 验证数据手套 → 灵巧手
echo "测试: 数据手套 → 灵巧手"
echo "移动数据手套，观察灵巧手是否响应"
ros2 topic echo /cb_left_hand_control_cmd
```

---

## 终端10 - Rosbag数据采集

用于记录实验数据，供后续分析使用。

### 启动命令

```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
```

### 基础数据采集

#### 1. 记录所有topic

```bash
# 记录所有topic（不推荐，数据量大）
ros2 bag record -a -o ~/Dev/VIST/data/experiment_all
```

#### 2. 记录关键topic（推荐）

```bash
# 创建数据目录
mkdir -p ~/Dev/VIST/data/experiments

# 记录关键topic
ros2 bag record \
  /camera/color/image_raw \
  /camera/color/camera_info \
  /left_arm_joint_control \
  /filtered_joint_states \
  /cb_left_hand_control_cmd \
  /cb_left_hand_control_angle_cmd \
  /robot1/left_arm/joint_states \
  /robot1/left_arm/joint_follow \
  -o ~/Dev/VIST/data/experiments/stacking_task_$(date +%Y%m%d_%H%M%S)
```

#### 3. 记录特定子系统

**仅记录遥操作数据（外骨骼+机械臂）：**
```bash
ros2 bag record \
  /left_arm_joint_control \
  /filtered_joint_states \
  /robot1/left_arm/joint_states \
  /robot1/left_arm/joint_follow \
  -o ~/Dev/VIST/data/experiments/teleop_$(date +%Y%m%d_%H%M%S)
```

**仅记录灵巧手数据：**
```bash
ros2 bag record \
  /cb_left_hand_control_cmd \
  /cb_left_hand_control_angle_cmd \
  -o ~/Dev/VIST/data/experiments/dexterous_hand_$(date +%Y%m%d_%H%M%S)
```

**仅记录视觉数据：**
```bash
ros2 bag record \
  /camera/color/image_raw \
  /camera/color/camera_info \
  -o ~/Dev/VIST/data/experiments/vision_$(date +%Y%m%d_%H%M%S)
```

### 高级数据采集

#### 1. 压缩记录（节省空间）

```bash
ros2 bag record \
  --compression-mode file \
  --compression-format zstd \
  /camera/color/image_raw \
  /left_arm_joint_control \
  /filtered_joint_states \
  /cb_left_hand_control_cmd \
  /robot1/left_arm/joint_states \
  -o ~/Dev/VIST/data/experiments/compressed_$(date +%Y%m%d_%H%M%S)
```

#### 2. 限制录制时间

```bash
# 录制60秒
ros2 bag record \
  --duration 60 \
  /camera/color/image_raw \
  /left_arm_joint_control \
  /filtered_joint_states \
  -o ~/Dev/VIST/data/experiments/timed_recording
```

#### 3. 限制bag文件大小

```bash
# 每个bag文件最大1GB，自动分割
ros2 bag record \
  --max-bag-size 1073741824 \
  /camera/color/image_raw \
  /left_arm_joint_control \
  /filtered_joint_states \
  -o ~/Dev/VIST/data/experiments/split_recording
```

### 数据采集脚本

创建一个完整的数据采集脚本：

```bash
#!/bin/bash
# VIST系统完整数据采集脚本

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== VIST数据采集 ===${NC}"
echo ""

# 创建数据目录
DATA_DIR="$HOME/Dev/VIST/data/experiments"
mkdir -p "$DATA_DIR"

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 实验名称（可自定义）
EXPERIMENT_NAME="${1:-stacking_task}"
OUTPUT_DIR="${DATA_DIR}/${EXPERIMENT_NAME}_${TIMESTAMP}"

echo -e "${GREEN}实验名称: ${EXPERIMENT_NAME}${NC}"
echo -e "${GREEN}输出目录: ${OUTPUT_DIR}${NC}"
echo ""

# 记录的topic列表
TOPICS=(
    "/camera/color/image_raw"
    "/camera/color/camera_info"
    "/left_arm_joint_control"
    "/filtered_joint_states"
    "/cb_left_hand_control_cmd"
    "/cb_left_hand_control_angle_cmd"
    "/robot1/left_arm/joint_states"
    "/robot1/left_arm/joint_follow"
)

echo -e "${YELLOW}将记录以下topic:${NC}"
for topic in "${TOPICS[@]}"; do
    echo "  - $topic"
done
echo ""

echo -e "${GREEN}开始录制... (按Ctrl+C停止)${NC}"
echo ""

# 开始录制
ros2 bag record \
    --compression-mode file \
    --compression-format zstd \
    "${TOPICS[@]}" \
    -o "$OUTPUT_DIR"

echo ""
echo -e "${GREEN}录制完成！${NC}"
echo -e "数据保存在: ${OUTPUT_DIR}"
```

保存为 `~/Dev/VIST/scripts/record_experiment.sh` 并添加执行权限：

```bash
chmod +x ~/Dev/VIST/scripts/record_experiment.sh
```

使用方法：

```bash
# 使用默认名称
./scripts/record_experiment.sh

# 指定实验名称
./scripts/record_experiment.sh stacking_task_trial1
```

### 数据回放与分析

#### 1. 查看bag文件信息

```bash
ros2 bag info ~/Dev/VIST/data/experiments/stacking_task_20260226_120000
```

#### 2. 回放数据

```bash
# 正常速度回放
ros2 bag play ~/Dev/VIST/data/experiments/stacking_task_20260226_120000

# 慢速回放（0.5倍速）
ros2 bag play --rate 0.5 ~/Dev/VIST/data/experiments/stacking_task_20260226_120000

# 循环回放
ros2 bag play --loop ~/Dev/VIST/data/experiments/stacking_task_20260226_120000
```

#### 3. 导出特定topic

```bash
# 导出为CSV（需要额外工具）
ros2 bag play ~/Dev/VIST/data/experiments/stacking_task_20260226_120000 &
ros2 topic echo /left_arm_joint_control > arm_data.txt
```

---

## 完整监控终端布局建议

使用tmux或多个终端窗口，建议布局：

```
┌─────────────────────┬─────────────────────┐
│  终端1: 相机        │  终端2: 外骨骼      │
├─────────────────────┼─────────────────────┤
│  终端3: 滤波器      │  终端4: 数据手套    │
├─────────────────────┼─────────────────────┤
│  终端5: 灵巧手      │  终端6: 机械臂驱动  │
├─────────────────────┼─────────────────────┤
│  终端7: 遥操作桥接  │  终端8: 频率监控    │
├─────────────────────┼─────────────────────┤
│  终端9: Topic验证   │  终端10: 数据采集   │
└─────────────────────┴─────────────────────┘
```

---

## 快速检查清单

在开始数据采集前，使用此清单验证系统状态：

```bash
# 1. 检查所有节点是否运行
ros2 node list

# 2. 检查所有topic是否发布
ros2 topic list

# 3. 检查关键topic频率
ros2 topic hz /camera/color/image_raw &
ros2 topic hz /left_arm_joint_control &
ros2 topic hz /filtered_joint_states &
ros2 topic hz /cb_left_hand_control_cmd &

# 4. 测试功能
# - 移动外骨骼，观察机械臂是否跟随
# - 移动数据手套，观察灵巧手是否响应
# - 检查相机图像是否正常

# 5. 开始数据采集
./scripts/record_experiment.sh experiment_name
```

---

## 故障排查

### Topic频率异常

**症状**: 某个topic的频率明显低于预期

**排查步骤**:
1. 检查该节点的CPU使用率：`top` 或 `htop`
2. 检查网络延迟（如果是网络topic）
3. 检查USB带宽（相机、CAN设备）
4. 查看节点日志是否有错误

### Topic不存在

**症状**: `ros2 topic list` 中找不到某个topic

**排查步骤**:
1. 检查对应节点是否运行：`ros2 node list`
2. 检查节点日志是否有启动错误
3. 验证topic名称是否正确（注意命名空间）

### 数据采集失败

**症状**: rosbag录制失败或数据不完整

**排查步骤**:
1. 检查磁盘空间：`df -h`
2. 检查写入权限
3. 减少录制的topic数量
4. 使用压缩模式

---

最后更新: 2026-02-26