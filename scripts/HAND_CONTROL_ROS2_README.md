# LinkerHand L10 键盘控制 - ROS2 版本

## 概述

这是基于 ROS2 通信的 LinkerHand L10 键盘控制程序。通过 ROS2 话题与灵巧手驱动节点通信，实现键盘控制。

## 系统架构

```
┌─────────────────────┐         ROS2 话题          ┌──────────────────────┐
│  hand_control.py    │ ──────────────────────────> │ linker_hand_        │
│  (键盘控制)         │  /cb_left_hand_control_cmd │ advanced_l10        │
│                     │                             │ (ROS2 节点)         │
│                     │ <────────────────────────── │                      │
└─────────────────────┘  /cb_left_hand_state       └──────────────────────┘
                                                              │
                                                              │ CAN 总线
                                                              ↓
                                                    ┌──────────────────────┐
                                                    │  LinkerHand L10      │
                                                    │  (硬件)              │
                                                    └──────────────────────┘
```

## 使用步骤

### 第一步：启动 LinkerHand ROS2 节点

在一个终端中运行：

```bash
./scripts/start_6_dexterous_hand.sh
```

或者手动启动：

```bash
# 加载 ROS2 环境
source /opt/ros/humble/setup.bash
source install/setup.bash

# 启动节点
ros2 run linker_hand_ros2_sdk linker_hand_advanced_l10 \
  --hand_type left \
  --can can0 \
  --is_touch false
```

**验证节点是否运行**：

```bash
# 检查节点
ros2 node list | grep linker_hand

# 检查话题
ros2 topic list | grep hand
```

应该看到：
- `/cb_left_hand_control_cmd` - 控制命令话题
- `/cb_left_hand_state` - 手部状态话题

### 第二步：启动键盘控制程序

在另一个终端中运行：

```bash
./scripts/start_hand_keyboard.sh
```

或者直接运行 Python 脚本：

```bash
python3 scripts/hand_control.py --hand_type left --preset medium
```

## 按键说明

| 按键 | 功能 | 说明 |
|------|------|------|
| `1` | IDLE | 空闲状态，手完全张开 |
| `2` | PRE-GRASP | 预抓取状态，手部分闭合 |
| `3` | GRASP | 抓取状态，手完全闭合 |
| `h` | 帮助 | 显示帮助信息 |
| `q` | 退出 | 退出程序 |

## 命令行参数

### hand_control.py

```bash
python3 scripts/hand_control.py [选项]

选项:
  --hand_type {left,right}  手的类型 (默认: left)
  --preset {small,medium,large}  抓取预设 (默认: medium)
```

### start_hand_keyboard.sh

```bash
./scripts/start_hand_keyboard.sh [hand_type] [preset]

参数:
  hand_type  手的类型: left 或 right (默认: left)
  preset     抓取预设: small, medium, large (默认: medium)
```

**示例**：

```bash
# 左手，中等物体预设
./scripts/start_hand_keyboard.sh left medium

# 右手，小物体预设
./scripts/start_hand_keyboard.sh right small
```

## ROS2 话题

### 发布的话题

- **`/cb_{hand_type}_hand_control_cmd`** (sensor_msgs/JointState)
  - 发送关节位置命令
  - 包含 10 个关节的目标位置

### 订阅的话题

- **`/cb_{hand_type}_hand_state`** (sensor_msgs/JointState)
  - 接收当前手部状态
  - 包含 10 个关节的实际位置

## 关节顺序

LinkerHand L10 有 10 个自由度：

1. `thumb_cmc_pitch` - 拇指俯仰
2. `thumb_cmc_yaw` - 拇指偏航
3. `index_mcp_pitch` - 食指俯仰
4. `middle_mcp_pitch` - 中指俯仰
5. `ring_mcp_pitch` - 无名指俯仰
6. `pinky_mcp_pitch` - 小指俯仰
7. `index_mcp_roll` - 食指侧摆
8. `ring_mcp_roll` - 无名指侧摆
9. `pinky_mcp_roll` - 小指侧摆
10. `thumb_cmc_roll` - 拇指侧摆

角度范围：0-255

## 故障排除

### 问题 1: ROS2 节点未运行

**错误信息**：
```
❌ LinkerHand ROS2 节点未运行
```

**解决方法**：
1. 启动 ROS2 节点：
   ```bash
   ./scripts/start_6_dexterous_hand.sh
   ```

2. 检查 CAN 接口：
   ```bash
   ip link show can0
   ```

3. 如果 CAN 接口未启动：
   ```bash
   sudo ip link set can0 up type can bitrate 1000000
   ```

### 问题 2: 找不到话题

**错误信息**：
```
❌ 未找到话题: /cb_left_hand_state
```

**解决方法**：
1. 检查 ROS2 节点是否正常运行：
   ```bash
   ros2 node list
   ```

2. 检查话题列表：
   ```bash
   ros2 topic list
   ```

3. 检查节点日志：
   ```bash
   ros2 node info /linker_hand_advanced_l10
   ```

### 问题 3: 手没有反应

**可能原因**：
1. ROS2 节点未正确连接到硬件
2. CAN ID 配置错误
3. 硬件连接问题

**调试步骤**：

1. **监控话题数据**：
   ```bash
   # 监控控制命令
   ros2 topic echo /cb_left_hand_control_cmd

   # 监控手部状态
   ros2 topic echo /cb_left_hand_state
   ```

2. **手动发送测试命令**：
   ```bash
   ros2 topic pub --once /cb_left_hand_control_cmd sensor_msgs/JointState \
     "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, \
       name: ['thumb_cmc_pitch', 'thumb_cmc_yaw', 'index_mcp_pitch', 'middle_mcp_pitch', 'ring_mcp_pitch', 'pinky_mcp_pitch', 'index_mcp_roll', 'ring_mcp_roll', 'pinky_mcp_roll', 'thumb_cmc_roll'], \
       position: [255.0, 255.0, 255.0, 255.0, 255.0, 255.0, 255.0, 255.0, 255.0, 255.0], \
       velocity: [], \
       effort: []}"
   ```

3. **检查 ROS2 节点日志**：
   查看节点终端的输出，看是否有错误信息。

### 问题 4: ROS2 环境未加载

**错误信息**：
```
ros2: command not found
```

**解决方法**：
```bash
source /opt/ros/humble/setup.bash
source /home/ilex/Dev/VIST/install/setup.bash
```

## 与旧版本的区别

### 旧版本（直接 CAN 通信）

- 直接通过 CAN 总线发送命令
- 需要处理 CAN 缓冲区、重试等底层细节
- 可能遇到 CAN ID 不匹配等问题

### 新版本（ROS2 通信）

- 通过 ROS2 话题通信
- ROS2 节点处理所有底层 CAN 通信
- 更稳定、更易于调试
- 可以与其他 ROS2 节点集成

## 开发说明

### 修改抓取预设

编辑 `hand_control.py` 中的 `JointAnglesConfig` 类：

```python
JOINT_ANGLES_IDLE = [255.0, 255.0, ...]  # 空闲状态
JOINT_ANGLES_PRE_GRASP = [188.0, 51.0, ...]  # 预抓取状态
JOINT_ANGLES_GRASP = [138.0, 60.0, ...]  # 抓取状态
```

### 添加新状态

1. 在 `HandState` 枚举中添加新状态
2. 在 `JointAnglesConfig` 中定义对应的关节角度
3. 在 `KeyboardHandController.set_state()` 中添加处理逻辑
4. 在 `KeyboardHandController.run()` 中添加按键映射

### 集成到其他 ROS2 程序

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

class MyHandController(Node):
    def __init__(self):
        super().__init__('my_hand_controller')

        # 创建发布者
        self.cmd_pub = self.create_publisher(
            JointState,
            '/cb_left_hand_control_cmd',
            10
        )

    def send_command(self, positions):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['thumb_cmc_pitch', 'thumb_cmc_yaw', ...]
        msg.position = positions
        self.cmd_pub.publish(msg)
```

## 相关文件

- `scripts/hand_control.py` - 主控制程序
- `scripts/start_hand_keyboard.sh` - 启动脚本
- `scripts/start_6_dexterous_hand.sh` - ROS2 节点启动脚本
- `external_sdk/linkerhand-ros2-sdk/` - LinkerHand ROS2 SDK

## 许可证

请参考项目根目录的 LICENSE 文件。

---

**最后更新**: 2026-02-26
**版本**: 2.0 (ROS2)