# VIST 环境配置指南

## 📋 环境复杂度分析

VIST项目的环境配置包含以下几个层次：

### 复杂度等级：⭐⭐⭐⭐ (中高)

**主要依赖**：
1. **ROS2 Humble** - 核心通信框架
2. **自定义ROS2消息** - lbot_arm_interfaces（需要编译）
3. **Python 3.10+** - 主要开发语言
4. **外部SDK** - 遥操臂和灵巧手SDK（需要编译）
5. **Python科学计算库** - numpy, scipy, matplotlib等

---

## 🚀 快速开始（推荐）

### 前置条件

- Ubuntu 22.04 LTS
- 至少 8GB RAM
- 20GB 可用磁盘空间

### 一键安装脚本（即将提供）

```bash
# 克隆仓库
git clone https://github.com/your-org/VIST.git
cd VIST

# 运行自动安装脚本
./scripts/setup_environment.sh

# 验证安装
./scripts/verify_installation.sh
```

---

## 📦 详细安装步骤

### 1. 安装ROS2 Humble

```bash
# 添加ROS2源
sudo apt update && sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install -y curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 安装ROS2 Humble
sudo apt update
sudo apt install -y ros-humble-desktop
sudo apt install -y ros-dev-tools

# 配置环境（添加到 ~/.bashrc）
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2. 安装Python依赖

```bash
cd /path/to/VIST

# 方式1：使用pip（推荐）
pip install -r requirements.txt

# 方式2：使用conda（如果你使用conda环境）
conda create -n vist_env python=3.10
conda activate vist_env
pip install -r requirements.txt
```

### 3. 编译自定义ROS2消息

```bash
cd external_sdk/arm_teleop

# 编译lbot_arm_interfaces
colcon build --packages-select lbot_arm_interfaces

# 加载编译结果
source install/setup.bash

# 验证消息类型
ros2 interface list | grep lbot_arm_interfaces
```

### 4. 编译外部SDK（可选）

```bash
# 编译灵巧手SDK（如果需要使用灵巧手）
cd external_sdk/linkerhand-ros2-sdk
colcon build
source install/setup.bash

# 编译灵巧手遥操SDK（如果需要手套控制）
cd ../linkerhand-ros-teleop
colcon build
source install/setup.bash
```

### 5. 配置环境变量

创建环境配置脚本 `~/.vist_env.sh`：

```bash
#!/bin/bash
# VIST 环境配置

# ROS2 Humble
source /opt/ros/humble/setup.bash

# VIST项目路径（修改为你的实际路径）
export VIST_ROOT="/home/your_username/Dev/VIST"

# 自定义消息类型
if [ -f "$VIST_ROOT/external_sdk/arm_teleop/install/setup.bash" ]; then
    source "$VIST_ROOT/external_sdk/arm_teleop/install/setup.bash"
fi

# 灵巧手SDK（可选）
if [ -f "$VIST_ROOT/external_sdk/linkerhand-ros2-sdk/install/setup.bash" ]; then
    source "$VIST_ROOT/external_sdk/linkerhand-ros2-sdk/install/setup.bash"
fi

# Python路径
export PYTHONPATH="$VIST_ROOT/src:$PYTHONPATH"

echo "✓ VIST环境已加载"
```

然后在 `~/.bashrc` 中添加：

```bash
# VIST环境
source ~/.vist_env.sh
```

---

## 🔍 验证安装

### 检查ROS2

```bash
# 检查ROS2版本
ros2 --version
# 应该输出: ros2 cli version: 0.18.x

# 检查ROS2节点
ros2 node list
```

### 检查Python依赖

```bash
python3 -c "import numpy, scipy, matplotlib, yaml; print('✓ Python依赖正常')"
```

### 检查自定义消息

```bash
# 检查lbot_arm_interfaces
ros2 interface list | grep lbot_arm_interfaces

# 应该看到类似输出：
# lbot_arm_interfaces/msg/ArmState
# lbot_arm_interfaces/msg/FollowJoint
# lbot_arm_interfaces/srv/MoveJ
# ...
```

### 运行测试脚本

```bash
cd $VIST_ROOT
python3 -c "from lbot_arm_interfaces.msg import FollowJoint; print('✓ 消息导入成功')"
```

---

## 🛠️ 常见问题

### 1. 找不到 lbot_arm_interfaces

**问题**：
```
ModuleNotFoundError: No module named 'lbot_arm_interfaces'
```

**解决方案**：
```bash
# 确保已编译并source
cd external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash

# 或者使用包装脚本
source ~/.vist_env.sh
```

### 2. ROS2命令找不到

**问题**：
```
bash: ros2: command not found
```

**解决方案**：
```bash
# 确保已安装ROS2
source /opt/ros/humble/setup.bash

# 永久添加到bashrc
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### 3. Python版本不兼容

**问题**：
```
Python 3.8 不支持某些特性
```

**解决方案**：
```bash
# 使用conda创建Python 3.10环境
conda create -n vist_env python=3.10
conda activate vist_env
pip install -r requirements.txt
```

### 4. rosbag2_py导入失败

**问题**：
```
ModuleNotFoundError: No module named 'rosbag2_py'
```

**解决方案**：
```bash
# 安装rosbag2相关包
sudo apt install -y ros-humble-rosbag2-py
source /opt/ros/humble/setup.bash
```

---

## 📊 依赖关系图

```
VIST项目
├── ROS2 Humble (必需)
│   ├── ros-humble-desktop
│   ├── ros-dev-tools
│   └── ros-humble-rosbag2-py
│
├── Python 3.10+ (必需)
│   ├── numpy >= 1.26.4
│   ├── scipy >= 1.15.3
│   ├── matplotlib >= 3.10.8
│   ├── pyyaml >= 6.0.3
│   ├── opencv-python >= 4.8.0
│   ├── mediapipe >= 0.10.9
│   └── pinocchio >= 2.6.0
│
├── 自定义ROS2消息 (必需)
│   └── lbot_arm_interfaces
│
├── 遥操臂SDK (运行时必需)
│   └── external_sdk/arm_teleop
│
└── 灵巧手SDK (可选)
    ├── linkerhand-ros2-sdk
    └── linkerhand-ros-teleop
```

---

## 🎯 不同使用场景的安装建议

### 场景1：仅运行数据分析

**最小依赖**：
```bash
# 只需要Python依赖和ROS2消息
pip install numpy scipy matplotlib pyyaml
sudo apt install -y ros-humble-rosbag2-py

# 编译消息类型
cd external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
```

### 场景2：运行完整遥操系统

**完整依赖**：
```bash
# 安装所有依赖
pip install -r requirements.txt

# 编译所有SDK
cd external_sdk/arm_teleop && colcon build && cd ../..
cd external_sdk/linkerhand-ros2-sdk && colcon build && cd ../..
cd external_sdk/linkerhand-ros-teleop && colcon build && cd ../..

# 配置环境
source ~/.vist_env.sh
```

### 场景3：开发和调试

**开发依赖**：
```bash
# 基础依赖
pip install -r requirements.txt

# 开发工具
pip install pytest black flake8 mypy

# 配置开发环境
export VIST_DEV_MODE=1
```

---

## 📝 环境配置检查清单

使用以下清单确保环境配置正确：

- [ ] ROS2 Humble已安装并可用
- [ ] Python 3.10+已安装
- [ ] requirements.txt中的依赖已安装
- [ ] lbot_arm_interfaces已编译
- [ ] 环境变量已配置（~/.vist_env.sh）
- [ ] 可以导入lbot_arm_interfaces.msg
- [ ] rosbag2_py可用
- [ ] 测试脚本运行成功

---

## 🔄 更新环境

当项目更新时，运行以下命令更新环境：

```bash
cd $VIST_ROOT

# 更新代码
git pull

# 更新Python依赖
pip install -r requirements.txt --upgrade

# 重新编译ROS2包（如果消息定义有变化）
cd external_sdk/arm_teleop
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
```

---

## 💡 性能优化建议

### 1. 使用编译优化

```bash
# 使用Release模式编译
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
```

### 2. 配置Python环境

```bash
# 使用conda环境隔离
conda create -n vist_env python=3.10
conda activate vist_env

# 安装优化版numpy
conda install numpy scipy -c conda-forge
```

### 3. 系统优化

```bash
# 增加实时性能
sudo sysctl -w kernel.sched_rt_runtime_us=-1

# 禁用CPU频率缩放
sudo cpupower frequency-set -g performance
```

---

## 📞 获取帮助

如果遇到问题：

1. 查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. 查看 [常见问题](#常见问题)
3. 提交Issue: https://github.com/your-org/VIST/issues
4. 联系维护者

---

**最后更新**: 2026-02-24
**维护者**: VIST Research Team
**状态**: 活跃维护
