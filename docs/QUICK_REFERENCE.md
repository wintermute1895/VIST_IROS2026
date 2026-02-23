# 快速参考指南

## 分支管理

### 当前分支
```bash
git branch -v
# * feature/exo-hand-integration c539ec8
```

### 切换分支
```bash
git checkout develop                    # 主开发分支
git checkout feature/vision-perception  # 视觉感知分支
git checkout feature/exo-hand-integration  # 外骨骼集成分支
```

## 启动系统

### 1. 手套数据采集
```bash
cd ~/Dev/VIST/src/robot/sdk/linkerhand-ros-teleop-main/linkertelopsdk/ros2/src/linkerhand_retarget
export PYTHONPATH=$PWD:$PYTHONPATH
source /opt/ros/humble/setup.bash
python3 linkerhand_retarget/handretarget.py
```

### 2. 手部SDK（L10灵巧手）
```bash
./scripts/start_hand_sdk.sh
```

### 3. 外骨骼臂遥操作
```bash
python3 scripts/exo_baseline_1_raw.py      # 基线（无滤波）
python3 scripts/exo_ours_filtered.py       # 低通滤波
python3 scripts/exo_vist_full.py           # VIST完整版（待实现）
```

## 常用命令

### ROS2话题
```bash
ros2 topic list                           # 查看所有话题
ros2 topic echo /cb_left_hand_control_cmd # 手套数据
ros2 topic echo /right_arm_joint_control  # 外骨骼数据
```

### CAN接口
```bash
ip link show can0                         # 查看状态
sudo ip link set can0 up type can bitrate 1000000  # 启动
candump can0                              # 查看数据
```

### 硬件检查
```bash
lsusb                                     # USB设备
ls /dev/ttyUSB*                           # 串口设备
ping 192.168.10.21                        # 机械臂连接
```

## 配置文件

- 手套: `src/robot/sdk/linkerhand-ros-teleop-main/.../base_config.yml`
- 手部SDK: `~/Downloads/linkerhand-ros2-sdk-main/.../setting.yaml`
- 外骨骼: `src/robot/sdk/arm_teleop/src/lbot_teleop/config/teleop_config.yaml`

---
最后更新: 2026-02-23
