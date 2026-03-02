# VIST Teleoperation System Bringup Package

这个包提供了VIST遥操作系统的模块化启动文件。

## 包结构

```
bringup/
├── CMakeLists.txt
├── package.xml
├── README.md
└── launch/
    ├── camera.launch.py           # 相机节点
    ├── exoskeleton.launch.py      # 外骨骼节点
    ├── vist_filter.launch.py      # VIST滤波器节点
    ├── dexterous_hand.launch.py   # 灵巧手节点
    ├── robot_driver.launch.py     # 机械臂驱动节点
    ├── teleop_bridge.launch.py    # 遥操作桥接节点
    ├── hand_keyboard.launch.py    # 灵巧手键盘控制节点
    └── teleop_system.launch.py    # 顶层系统启动文件
```

## 编译安装

```bash
cd /home/ilex/Dev/VIST/ros2_ws
colcon build --packages-select bringup
source install/setup.bash
```

## 使用方法

### 0. 快速启动（最简单，推荐）

使用一键启动脚本：

```bash
cd /home/ilex/Dev/VIST
./scripts/start_system.sh
```

这个脚本会自动：
- 配置 CAN 接口（需要 sudo 权限）
- 检查机械臂网络连接
- 加载所有 ROS2 环境
- 启动完整的遥操作系统

### 1. 手动准备和启动

如果需要手动控制启动过程：

**步骤 1 - 系统准备（首次启动或重启后）：**

```bash
cd /home/ilex/Dev/VIST
./scripts/prepare_system.sh
```

这个脚本会：
- 配置 CAN0 和 CAN1 接口（需要 sudo 权限）
- 检查机械臂网络连接
- 加载 ROS2 环境

**步骤 2 - 启动完整系统：**

```bash
ros2 launch bringup teleop_system.launch.py
```

可选参数：
- `enable_camera:=true` - 启用相机（默认false）
- `enable_hand:=true` - 启用灵巧手（默认true）
- `arm_side:=left` - 选择手臂侧（left或right，默认left）

示例：
```bash
# 启动完整系统（包含相机）
ros2 launch bringup teleop_system.launch.py enable_camera:=true

# 启动右臂系统（不含相机）
ros2 launch bringup teleop_system.launch.py arm_side:=right enable_camera:=false
```

### 2. 单独启动各个模块

如果需要单独测试或调试某个模块：
cd /home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop
cd /home/ilex/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
conda activate robot_env

```bash
# 启动相机
ros2 launch bringup camera.launch.py

# 启动外骨骼
ros2 launch bringup exoskeleton.launch.py

# 启动VIST滤波器
ros2 launch bringup vist_filter.launch.py

# 启动灵巧手
ros2 launch bringup dexterous_hand.launch.py hand_type:=left

# 启动灵巧手键盘控制（在新终端窗口中）
ros2 launch bringup hand_keyboard.launch.py hand_type:=left preset:=medium

# 启动机械臂驱动
ros2 launch bringup robot_driver.launch.py

# 启动遥操作桥接
ros2 launch bringup teleop_bridge.launch.py
```
python3 scripts/experiment/collect_experiment.py

python3 scripts/analysis/analyze_all_metrics.py --rosbag data/experiments/experiment_20260227_145208

python3 scripts/analysis/aggregate_metrics.py



## 启动顺序说明

顶层launch文件 `teleop_system.launch.py` 按以下顺序启动各个子系统：

1. **T+0s**: 相机（可选）、外骨骼
2. **T+1s**: 灵巧手（可选）
3. **T+2s**: VIST滤波器（等待外骨骼数据）
4. **T+4s**: 机械臂驱动（等待滤波器就绪）
5. **T+7s**: 遥操作桥接（等待机械臂驱动就绪）
6. **T+10s**: 系统就绪提示

这些延迟确保了各个节点按正确的依赖关系启动。

## 话题连接关系

```
外骨骼 → /left_arm_joint_control → VIST滤波器
VIST滤波器 → /filtered_left_joint_control → 遥操作桥接
遥操作桥接 → /robot1/left_arm/joint_follow → 机械臂驱动
```

## 故障排查

### 问题1：找不到包

```bash
# 确保已经编译并source
cd /home/ilex/Dev/VIST/ros2_ws
colcon build --packages-select bringup
source install/setup.bash
```

### 问题2：CAN端口未激活

灵巧手需要CAN端口，如果遇到CAN错误：

```bash
sudo ip link set can0 up type can bitrate 1000000
```

### 问题3：外部工作空间未找到

确保外骨骼工作空间已编译：

```bash
cd /home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop

# 如果遇到CMake缓存错误，先清理
rm -rf build install log

# 编译（使用allow-overriding避免冲突）
colcon build --allow-overriding lbot_driver lbot_teleop linkerta
source install/setup.bash
```

### 问题4：节点启动失败

检查各个节点的日志输出，确认：
- 配置文件路径正确
- 硬件设备已连接
- 权限设置正确（CAN、USB等）

### 问题5：灵巧手键盘控制无法启动

灵巧手键盘控制需要交互式终端来读取键盘输入。launch文件会自动在新的gnome-terminal窗口中启动控制程序。

如果遇到问题：
1. 确保已安装 gnome-terminal：`sudo apt install gnome-terminal`
2. 或者使用原始bash脚本：`./scripts/start_hand_keyboard.sh left medium`
3. 键盘控制说明：
   - `1` - IDLE (空闲/张开)
   - `2` - PRE-GRASP (预抓取)
   - `3` - GRASP (抓取/闭合)
   - `h` - 显示帮助
   - `q` - 退出程序

## 配置文件路径

各个模块使用的配置文件：
- 外骨骼: `/home/ilex/Dev/VIST/external_sdk/arm_teleop/src/linkerta/config/lta.yaml`
- VIST滤波器: `/home/ilex/Dev/VIST/config/baseline_filters_config.yaml`
- 遥操作桥接: `/home/ilex/Dev/VIST/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`

## 注意事项

1. **Python节点的特殊处理**:
   - `camera_manager` 和 `vist_filter_node` 是Python脚本节点
   - 这些节点使用 `ExecuteProcess` 而不是 `Node` action来启动
   - 原因：Python包的可执行文件安装在 `bin/` 目录，而ROS2的 `Node` action期望在 `lib/<package_name>/` 目录
   - 如果遇到 "libexec directory does not exist" 错误，说明需要使用 `ExecuteProcess`

2. **camera_manager包的安装**:
   - 首次使用前需要安装Python包元数据：
     ```bash
     cd /home/ilex/Dev/VIST/ros2_ws/src/camera_manager
     pip3 install -e . --user
     ```

3. **工作空间依赖**: 系统依赖两个工作空间：
   - 主工作空间: `/home/ilex/Dev/VIST/ros2_ws`
   - 外骨骼工作空间: `/home/ilex/Dev/VIST/external_sdk/arm_teleop`

3. **硬件要求**:
   - CAN接口（灵巧手）
   - USB接口（外骨骼、相机）
   - 网络连接（机械臂驱动）

## 从Bash脚本迁移

原有的Bash启动脚本已被以下launch文件替代：

| 原Bash脚本 | 新Launch文件 |
|-----------|-------------|
| `start_camera.sh` | `camera.launch.py` |
| `start_left_arm_teleop.sh` | `exoskeleton.launch.py` |
| `start_vist_filter.sh` | `vist_filter.launch.py` |
| `start_6_dexterous_hand.sh` | `dexterous_hand.launch.py` |
| `start_hand_keyboard.sh` | `hand_keyboard.launch.py` |
| `start_robot_driver.sh` | `robot_driver.launch.py` |
| `start_teleop_bridge.sh` | `teleop_bridge.launch.py` |

## 维护者

VIST Team

## 许可证

MIT