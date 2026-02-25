# 外骨骼遥操 + 数据手套完整测试指南

## 系统架构

```
外骨骼遥操臂 (Linkerta) + 数据手套 (LinkerHand L10)
    ↓ ~250Hz                    ↓ ~30Hz
/right_arm_joint_control    /cb_left_hand_control_cmd
(臂关节角度)                 (手指控制命令: 10个关节)
    ↓                           ↓
teleop_bridge_node          linker_hand_sdk
(单位转换、限位检查)         (手指驱动)
    ↓ ~250Hz                    ↓ ~40Hz
/robot1/right_arm/joint_follow  /cb_left_hand_state
(跟随命令)                   (手指状态反馈: 10个关节)
    ↓
lbot_driver (机器人驱动)
    ↓ 底层自动降频到 ~50Hz
真机执行
    ↓ ~50Hz
/robot1/right_arm/joint_states (臂反馈)
```

## 数据手套 Topics 说明

### 控制命令 Topic
- **Topic**: `/cb_left_hand_control_cmd`
- **类型**: `sensor_msgs/msg/JointState`
- **频率**: ~30Hz
- **内容**:
  - `position`: 手指位置命令 (10个关节，L10型号)
  - `velocity`: 手指速度命令
  - `effort`: 手指力矩命令

### 状态反馈 Topic
- **Topic**: `/cb_left_hand_state`
- **类型**: `sensor_msgs/msg/JointState`
- **频率**: ~40Hz
- **内容**:
  - `position`: 手指实际位置 (10个关节)
  - `velocity`: 手指实际速度
  - `effort`: 手指实际力矩

### L10 手指关节对照表
```
position[0]: 拇指根部
position[1]: 拇指侧摆
position[2]: 食指根部
position[3]: 中指根部
position[4]: 无名指根部
position[5]: 小指根部
position[6]: 食指侧摆
position[7]: 无名指侧摆
position[8]: 小指侧摆
position[9]: 拇指旋转
```

## 完整启动流程

### 1. 准备工作

确保以下设备已连接：
- ✅ 外骨骼遥操臂（Linkerta）已连接并上电
- ✅ 数据手套（LinkerHand L10）已连接（CAN总线 can0）
- ✅ 机器人左臂已连接（IP: 192.168.10.21）
- ✅ RealSense相机已连接

### 2. 启动数据手套驱动

**终端1** - 启动数据手套：
```bash
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros2-sdk
source install/setup.bash

# 开启CAN端口（如果未开启）
sudo /usr/sbin/ip link set can0 up type can bitrate 1000000

# 启动数据手套驱动
ros2 launch linker_hand_ros2_sdk linker_hand.launch.py
```

**配置说明** (linker_hand.launch.py):
- `hand_type`: 'left' (左手)
- `hand_joint`: "L10" (10个关节)
- `is_touch`: False (无压力传感器)
- `can`: 'can0' (CAN总线名称)

### 3. 启动外骨骼遥操系统

**终端2** - 启动外骨骼遥操：
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop.launch.py
```

这个launch文件会启动：
- `lbot_driver`: 机器人驱动（连接真机）
- `linkerta`: 外骨骼遥操臂驱动
- `teleop_bridge_node`: 桥接节点（单位转换、限位检查）

### 4. 验证所有 Topics

**终端3** - 验证topics：
```bash
# 检查臂控制topics
ros2 topic hz /right_arm_joint_control
ros2 topic hz /robot1/right_arm/joint_follow
ros2 topic hz /robot1/right_arm/joint_states

# 检查手指控制topics
ros2 topic hz /cb_left_hand_control_cmd
ros2 topic hz /cb_left_hand_state

# 查看手指数据
ros2 topic echo /cb_left_hand_state --flow-style
```

### 5. 运行数据采集测试

**终端4** - 运行测试脚本：
```bash
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash

# 基础测试（30秒）
./scripts/test_exo_teleop_pipeline.sh

# 自定义时长和任务名
./scripts/test_exo_teleop_pipeline.sh 60 "pick_and_place_with_hand"

# 指定相机序列号
./scripts/test_exo_teleop_pipeline.sh 30 "test" "327122074150"
```

脚本会自动检测数据手套topics，如果检测到会自动录制手指数据。

## 采集的数据

### 臂控制数据
- `/right_arm_joint_control` - 外骨骼原始输出 (~250Hz, 7个关节)
- `/robot1/right_arm/joint_follow` - 跟随命令 (~250Hz, 7个关节)
- `/robot1/right_arm/joint_states` - 真机反馈 (~50Hz, 7个关节)

### 手指控制数据
- `/cb_left_hand_control_cmd` - 手指控制命令 (~30Hz, 10个关节)
- `/cb_left_hand_state` - 手指状态反馈 (~40Hz, 10个关节)

### 视觉数据
- `/camera/color/image_raw` - RGB图像 (~30Hz)
- `/camera/depth/image_rect_raw` - 深度图像 (~30Hz)

## 性能指标分析

采集数据后，可以分析以下指标：

### 1. 频率分析
- 外骨骼输出频率（期望 ~250Hz）
- 跟随命令频率（期望 ~250Hz）
- 真机反馈频率（期望 ~50Hz）
- 手指控制频率（期望 ~30Hz）
- 手指反馈频率（期望 ~40Hz）
- 相机频率（期望 ~30Hz）

### 2. 时间同步质量
- 外骨骼输出 vs 跟随命令的时间差
- 手指命令 vs 手指反馈的时间差

### 3. 延迟分析
- 臂控制端到端延迟
- 手指控制端到端延迟

### 4. 轨迹质量
- 臂关节角度平滑度
- 手指关节角度平滑度
- 速度/加速度连续性

## 手动录制（如果自动脚本有问题）

### 录制完整数据
```bash
# 创建目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EPISODE_DIR="data/collection/exo_hand_test_${TIMESTAMP}"
mkdir -p "$EPISODE_DIR"

# 录制30秒（包含臂+手指+相机）
ros2 bag record \
    -o "$EPISODE_DIR/rosbag" \
    /right_arm_joint_control \
    /robot1/right_arm/joint_follow \
    /robot1/right_arm/joint_states \
    /cb_left_hand_control_cmd \
    /cb_left_hand_state \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    --max-bag-duration 30
```

### 只录制臂数据（不含手指）
```bash
ros2 bag record \
    -o "$EPISODE_DIR/rosbag" \
    /right_arm_joint_control \
    /robot1/right_arm/joint_follow \
    /robot1/right_arm/joint_states \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    --max-bag-duration 30
```

### 只录制手指数据（测试手套）
```bash
ros2 bag record \
    -o "$EPISODE_DIR/rosbag" \
    /cb_left_hand_control_cmd \
    /cb_left_hand_state \
    --max-bag-duration 30
```

## 数据手套配置

### 配置文件位置
`external_sdk/linkerhand-ros2-sdk/linker_hand_ros2_sdk/launch/linker_hand.launch.py`

### 关键参数
```python
parameters=[{
    'hand_type': 'left',      # 左手/右手
    'hand_joint': "L10",      # 手套型号: O6/L6/L7/L10/L20/L21
    'is_touch': False,        # 是否有压力传感器
    'can': 'can0',            # CAN总线名称
    "modbus": "None"          # Modbus总线（如果使用RS485）
}]
```

### 支持的手套型号
- **O6/L6**: 6个关节（拇指弯曲、拇指横摆、食指、中指、无名指、小指）
- **L7**: 7个关节（L6 + 拇指旋转）
- **L10**: 10个关节（拇指根部、拇指侧摆、5指根部、3指侧摆、拇指旋转）
- **L20/L21**: 20+个关节（全自由度灵巧手）

## 常见问题

### Q1: 找不到数据手套
```bash
# 检查CAN设备
ip link show can0

# 如果can0不存在，开启CAN端口
sudo /usr/sbin/ip link set can0 up type can bitrate 1000000

# 检查CAN设备是否有数据
candump can0
```

### Q2: 数据手套topic频率不对
```bash
# 实时监控频率
ros2 topic hz /cb_left_hand_control_cmd
ros2 topic hz /cb_left_hand_state

# 检查CAN总线负载
canbusload can0@1000000
```

### Q3: 手指运动不流畅
- 检查CAN总线连接是否稳定
- 检查手套电池电量
- 检查手套固件版本
- 降低控制频率（修改launch文件中的timer频率）

### Q4: 录制的bag文件太大
建议：
- 降低相机分辨率（640x480 → 424x240）
- 降低相机帧率（30Hz → 15Hz）
- 如果不需要视觉数据，可以不录制相机topics
- 使用压缩格式

## 数据分析示例

### 查看手指数据
```bash
# 查看rosbag信息
ros2 bag info data/collection/exo_hand_test_*/rosbag

# 播放rosbag
ros2 bag play data/collection/exo_hand_test_*/rosbag

# 提取手指数据
python3 << EOF
from scripts.analysis.core.rosbag_reader import RosbagReader

reader = RosbagReader("data/collection/exo_hand_test_*/rosbag")
hand_cmd = reader.read_topic("/cb_left_hand_control_cmd")
hand_state = reader.read_topic("/cb_left_hand_state")

print(f"手指命令消息数: {len(hand_cmd)}")
print(f"手指状态消息数: {len(hand_state)}")
EOF
```

### 分析手指轨迹
```python
import matplotlib.pyplot as plt
import numpy as np

# 提取手指位置数据
positions = [msg.position for msg in hand_state]
timestamps = [msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
              for msg in hand_state]

# 绘制10个关节的轨迹
fig, axes = plt.subplots(5, 2, figsize=(12, 15))
joint_names = ["拇指根部", "拇指侧摆", "食指根部", "中指根部", "无名指根部",
               "小指根部", "食指侧摆", "无名指侧摆", "小指侧摆", "拇指旋转"]

for i, (ax, name) in enumerate(zip(axes.flat, joint_names)):
    joint_pos = [p[i] for p in positions]
    ax.plot(timestamps, joint_pos)
    ax.set_title(name)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Position")
    ax.grid(True)

plt.tight_layout()
plt.savefig("hand_trajectory.png")
```

## 注意事项

⚠️ **安全提醒**：
- 确保机器人工作空间内无障碍物
- 首次测试时使用较小的运动范围
- 随时准备按下急停按钮
- 数据手套和机器人手的关节映射可能需要调整

⚠️ **数据手套使用注意**：
- 确保CAN总线连接稳定
- 定期检查手套电池电量
- 避免手套受到强烈冲击
- 使用前校准手套（如果支持）

⚠️ **已知限制**：
- 数据手套控制频率较低（~30Hz），可能不适合高速操作
- 手指反馈延迟约25-33ms
- CAN总线带宽有限，同时控制臂和手时可能有干扰
