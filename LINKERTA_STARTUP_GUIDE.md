# LinkerTA 启动指南

## 🚀 快速启动（推荐）

```bash
cd /home/ilex/Dev/VIST

# 使用启动脚本（交互式菜单）
./start_linkerta.sh
```

## 📋 启动前准备

### 1. 硬件连接
- [ ] LinkerTA遥操臂已通过CAN接口连接到电脑
- [ ] 电源已接通
- [ ] CAN适配器驱动已安装

### 2. 启动CAN设备

```bash
# 查看CAN设备
ip link show can0
ip link show can1

# 启动can0（如果LinkerTA连接到can0）
sudo ip link set can0 up type can bitrate 1000000

# 启动can1（如果LinkerTA连接到can1）
sudo ip link set can1 up type can bitrate 1000000

# 检查CAN设备状态
ip -details link show can0
```

### 3. 编译LinkerTA包（首次使用）

```bash
cd /home/ilex/Dev/VIST/ros2_ws

# 编译linkerta包
colcon build --packages-select linkerta

# Source工作空间
source install/setup.bash
```

## 🎯 启动方式

### 方法1：使用启动脚本（推荐）

```bash
./start_linkerta.sh

# 选择启动模式：
# 1. 单臂（左臂）
# 2. 单臂（右臂）
# 3. 双臂
# 4. 使用launch文件
```

### 方法2：手动启动单臂

```bash
# 激活环境
conda activate robot_env
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash

# 启动左臂
ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml

# 默认发布到话题：
# - /left_arm_joint_control (左臂)
# - /right_arm_joint_control (右臂)
```

### 方法3：使用launch文件

```bash
# 启动LinkerTA节点
ros2 launch linkerta run.launch.py

# 或使用bringup包
ros2 launch bringup exoskeleton.launch.py
```

### 方法4：启动双臂

```bash
# 终端1：左臂（can0）
ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml \
    -p arm_channel:=can0 \
    -r /joint_states:=/left_arm_joint_control

# 终端2：右臂（can1）
ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml \
    -p arm_channel:=can1 \
    -r /joint_states:=/right_arm_joint_control
```

## 🔧 配置文件

### 配置文件位置
```
ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml
```

### 配置参数说明

```yaml
linkerta_node:
  ros__parameters:
    calibration: 0          # 0=关闭标定, 1=开启标定
    arm_channel: "can1"     # CAN接口: can0 或 can1
    arm_id: 0x123          # 外骨骼ID
    arm_baudrate: 1000000  # CAN波特率
```

### 修改配置

```bash
# 编辑配置文件
nano ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml

# 修改后需要重新编译
cd ros2_ws
colcon build --packages-select linkerta
source install/setup.bash
```

## 📊 发布的话题

LinkerTA节点发布以下话题：

| 话题名称 | 类型 | 说明 |
|---------|------|------|
| `/left_arm_joint_control` | `sensor_msgs/JointState` | 左臂关节位置（7个关节，单位：度） |
| `/right_arm_joint_control` | `sensor_msgs/JointState` | 右臂关节位置（7个关节，单位：度） |
| `/joint_error_code` | - | 关节状态（1=故障，0=正常） |

## ✅ 验证启动成功

### 1. 查看话题列表
```bash
ros2 topic list | grep arm

# 应该看到：
# /left_arm_joint_control
# /right_arm_joint_control
```

### 2. 查看话题数据
```bash
# 查看左臂数据
ros2 topic echo /left_arm_joint_control

# 查看右臂数据
ros2 topic echo /right_arm_joint_control
```

### 3. 查看话题频率
```bash
# 检查发布频率（应该在50-100Hz）
ros2 topic hz /left_arm_joint_control
```

### 4. 使用监控脚本
```bash
# 实时监控LinkerTA数据
python3 monitor_linkerta_realtime.py /left_arm_joint_control
```

## 🐛 常见问题

### 问题1：找不到linkerta包

```bash
# 检查包是否已编译
ros2 pkg list | grep linkerta

# 如果没有，编译包
cd /home/ilex/Dev/VIST/ros2_ws
colcon build --packages-select linkerta
source install/setup.bash
```

### 问题2：CAN设备未找到

```bash
# 检查CAN设备
ip link show

# 如果没有can0/can1，检查CAN适配器驱动
lsusb | grep -i can

# 加载CAN驱动（根据实际硬件）
sudo modprobe can
sudo modprobe can_raw
sudo modprobe slcan
```

### 问题3：权限不足

```bash
# 添加用户到dialout组（用于串口/CAN访问）
sudo usermod -a -G dialout $USER

# 重新登录使权限生效
```

### 问题4：话题没有数据

```bash
# 1. 检查LinkerTA节点是否运行
ros2 node list | grep linkerta

# 2. 检查节点日志
ros2 node info /linkerta_node

# 3. 检查CAN设备状态
ip -s link show can0

# 4. 重启LinkerTA节点
```

### 问题5：数据全是0

```bash
# 可能需要标定LinkerTA
# 1. 将遥操臂关节转到刻度线位置
# 2. 修改配置文件 calibration: 1
# 3. 重新编译和启动
# 4. 标定完成后改回 calibration: 0
```

## 🔄 LinkerTA标定流程

如果LinkerTA数据不准确，需要进行标定：

```bash
# 1. 将每个遥操臂关节转动到刻度线位置

# 2. 修改配置文件
nano ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml
# 将 calibration: 0 改为 calibration: 1

# 3. 重新编译
cd ros2_ws
colcon build --packages-select linkerta
source install/setup.bash

# 4. 启动节点完成标定
ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml

# 5. 标定完成后，改回 calibration: 0
# 6. 再次编译和启动
```

## 📝 完整测试流程

```bash
# 1. 启动CAN设备
sudo ip link set can0 up type can bitrate 1000000

# 2. 启动LinkerTA
./start_linkerta.sh
# 选择选项1（单臂左臂）

# 3. 新开终端，验证话题
ros2 topic list | grep arm
ros2 topic hz /left_arm_joint_control

# 4. 监控数据
python3 monitor_linkerta_realtime.py /left_arm_joint_control

# 5. 移动遥操臂，观察数据变化
```

## 🎯 下一步：启动完整系统

LinkerTA启动成功后，可以启动完整的双臂遥操作系统：

```bash
# 1. LinkerTA已启动（本指南）

# 2. 启动双臂滤波节点
./test_dual_arm.sh
# 选择选项7（完整测试）

# 3. 在浏览器中查看
# http://127.0.0.1:7000/static/

# 4. 移动遥操臂，观察仿真中的双臂运动
```

---

**参考文档**：
- LinkerTA官方文档: `ros2_ws/src/external_sdk/arm_teleop/src/linkerta/README.md`
- 调试指南: `LINKERTA_DEBUG_GUIDE.md`
- 双臂系统: `DUAL_ARM_README.md`