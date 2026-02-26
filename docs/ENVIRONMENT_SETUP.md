# VIST系统环境配置指南

**适用系统**: Ubuntu 22.04 LTS
**ROS版本**: ROS2 Humble
**最后更新**: 2026-02-26

---

## 目录

1. [系统要求](#系统要求)
2. [ROS2 Humble安装](#ros2-humble安装)
3. [依赖安装](#依赖安装)
4. [工作空间构建](#工作空间构建)
5. [硬件配置](#硬件配置)
6. [权限设置](#权限设置)
7. [验证安装](#验证安装)
8. [常见问题](#常见问题)

---

## 系统要求

### 硬件要求
- CPU: Intel i5或更高（推荐i7）
- RAM: 8GB以上（推荐16GB）
- 存储: 50GB可用空间
- USB 3.0接口: 至少3个
- 网络: 千兆以太网

### 硬件设备
- RealSense D435i相机
- Linkerta外骨骼（CAN接口）
- 数据手套（USB接口）
- Linker Hand L10灵巧手（CAN接口）
- LBot机械臂（网络连接）
- USB-CAN适配器 x2

---

## ROS2 Humble安装

### 1. 设置locale

```bash
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
```

### 2. 添加ROS2 apt源

```bash
# 添加ROS2 GPG密钥
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

# 添加仓库到sources list
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
```

### 3. 安装ROS2 Humble

```bash
sudo apt update
sudo apt upgrade
sudo apt install ros-humble-desktop
sudo apt install ros-dev-tools
```

### 4. 配置环境

```bash
# 添加到.bashrc
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 验证安装
ros2 --version
# 应该显示: ros2 cli version: 0.18.x
```

---

## 依赖安装

### 1. Python依赖

```bash
# 安装pip
sudo apt install python3-pip

# 安装ROS2 Python工具
sudo apt install python3-colcon-common-extensions
sudo apt install python3-rosdep python3-vcstool

# 初始化rosdep
sudo rosdep init
rosdep update
```

### 2. RealSense SDK

```bash
# 添加Intel RealSense仓库
sudo mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null

echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" | \
sudo tee /etc/apt/sources.list.d/librealsense.list

sudo apt update

# 安装RealSense SDK
sudo apt install librealsense2-dkms
sudo apt install librealsense2-utils
sudo apt install librealsense2-dev

# 验证安装
realsense-viewer
```

### 3. RealSense ROS2包

```bash
sudo apt install ros-humble-realsense2-camera
sudo apt install ros-humble-realsense2-description
```

### 4. CAN工具

```bash
sudo apt install can-utils
```

### 5. 其他依赖

```bash
# OpenCV
sudo apt install python3-opencv

# NumPy和SciPy
pip3 install numpy scipy

# 其他Python包
pip3 install pyserial
pip3 install pyyaml
```

---

## 工作空间构建

### 1. 获取VIST项目

**方式A: 从压缩包解压（推荐）**

```bash
cd ~
mkdir -p Dev
cd Dev

# 解压VIST项目压缩包
tar -xzf VIST.tar.gz
# 或
unzip VIST.zip

cd VIST
```

**方式B: 从Git仓库克隆（如果可用）**

```bash
cd ~
mkdir -p Dev
cd Dev
git clone <VIST_REPOSITORY_URL> VIST
cd VIST
```

**注意**: VIST项目包含修改过的源代码和配置文件，建议使用压缩包方式获取完整项目。

### 2. 安装工作空间依赖

```bash
cd ~/Dev/VIST
rosdep install --from-paths src --ignore-src -r -y
```

### 3. 构建主工作空间

```bash
cd ~/Dev/VIST
colcon build
source install/setup.bash
```

### 4. 构建外骨骼工作空间

```bash
cd ~/Dev/VIST/external_sdk/arm_teleop
colcon build
source install/setup.bash
```

### 5. 构建灵巧手工作空间

```bash
cd ~/Dev/VIST/external_sdk/linkerhand-ros2-sdk
colcon build
source install/setup.bash
```

### 6. 添加到.bashrc（可选）

```bash
echo "source ~/Dev/VIST/install/setup.bash" >> ~/.bashrc
```

---

## 硬件配置

### 1. CAN设备配置

#### 安装CAN驱动

```bash
# 加载CAN内核模块
sudo modprobe can
sudo modprobe can_raw
sudo modprobe slcan

# 添加到开机自动加载
echo "can" | sudo tee -a /etc/modules
echo "can_raw" | sudo tee -a /etc/modules
```

#### 配置CAN接口

创建CAN接口配置脚本：

```bash
sudo nano /usr/local/bin/setup-can.sh
```

添加以下内容：

```bash
#!/bin/bash
# 设置CAN0（灵巧手）
ip link set can0 down 2>/dev/null
ip link set can0 type can bitrate 1000000
ip link set can0 up

# 设置CAN1（外骨骼）
ip link set can1 down 2>/dev/null
ip link set can1 type can bitrate 1000000
ip link set can1 up

echo "CAN interfaces configured"
```

添加执行权限：

```bash
sudo chmod +x /usr/local/bin/setup-can.sh
```

### 2. USB设备权限

#### RealSense相机

```bash
# 添加udev规则
sudo cp /usr/share/librealsense2/99-realsense-libusb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

#### 数据手套（串口设备）

```bash
# 添加用户到dialout组
sudo usermod -a -G dialout $USER

# 创建udev规则
sudo nano /etc/udev/rules.d/99-dataglove.rules
```

添加以下内容：

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="<VENDOR_ID>", ATTRS{idProduct}=="<PRODUCT_ID>", MODE="0666", GROUP="dialout"
```

重新加载udev规则：

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**注意**: 需要注销并重新登录以使组权限生效。

### 3. 网络配置（机械臂）

配置静态IP以连接机械臂：

```bash
# 编辑网络配置
sudo nano /etc/netplan/01-network-manager-all.yaml
```

添加以下内容（根据实际网络接口名称调整）：

```yaml
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    eth0:  # 替换为实际的网络接口名称
      dhcp4: no
      addresses:
        - 192.168.10.100/24  # 本机IP
      routes:
        - to: 192.168.10.0/24
          via: 192.168.10.1
```

应用配置：

```bash
sudo netplan apply
```

验证连接：

```bash
ping 192.168.10.21  # 机械臂IP
```

---

## 权限设置

### 1. sudo权限（CAN接口）

为了避免每次启动CAN接口都输入密码，可以配置sudo免密：

```bash
sudo visudo
```

添加以下行（替换`<username>`为你的用户名）：

```
<username> ALL=(ALL) NOPASSWD: /usr/sbin/ip link set can0 *
<username> ALL=(ALL) NOPASSWD: /usr/sbin/ip link set can1 *
```

### 2. 实时优先级（可选）

为了提高系统性能，可以配置实时优先级：

```bash
sudo nano /etc/security/limits.conf
```

添加以下行：

```
<username> soft rtprio 99
<username> hard rtprio 99
```

---

## 验证安装

### 1. 验证ROS2

```bash
# 检查ROS2版本
ros2 --version

# 列出可用的包
ros2 pkg list | grep vist

# 运行demo节点
ros2 run demo_nodes_cpp talker
# 在另一个终端
ros2 run demo_nodes_cpp listener
```

### 2. 验证RealSense

```bash
# 启动RealSense viewer
realsense-viewer

# 或使用命令行工具
rs-enumerate-devices
```

### 3. 验证CAN接口

```bash
# 启动CAN接口
sudo /usr/local/bin/setup-can.sh

# 检查CAN接口状态
ip -details link show can0
ip -details link show can1

# 应该看到: state UP, can state ERROR-ACTIVE
```

### 4. 验证工作空间

```bash
cd ~/Dev/VIST
source install/setup.bash

# 列出VIST包
ros2 pkg list | grep -E "camera_manager|linkerta|linker_hand"
```

### 5. 快速功能测试

#### 测试相机

```bash
cd ~/Dev/VIST
source install/setup.bash
./scripts/start_camera.sh
```

在另一个终端：

```bash
ros2 topic list | grep camera
ros2 topic hz /camera/color/image_raw
```

---

## 常见问题

### 1. ROS2找不到包

**症状**: `Package 'xxx' not found`

**解决**:
```bash
cd ~/Dev/VIST
source /opt/ros/humble/setup.bash
source install/setup.bash
```

### 2. CAN接口无法启动

**症状**: `RTNETLINK answers: Operation not permitted`

**解决**:
- 检查是否有sudo权限
- 检查CAN驱动是否加载：`lsmod | grep can`
- 重新加载驱动：`sudo modprobe can && sudo modprobe can_raw`

### 3. RealSense相机无法识别

**症状**: `No device connected`

**解决**:
- 检查USB连接（使用USB 3.0接口）
- 检查udev规则：`ls /etc/udev/rules.d/ | grep realsense`
- 重新加载udev：`sudo udevadm control --reload-rules && sudo udevadm trigger`
- 检查相机固件版本：`rs-fw-update -l`

### 4. 串口设备权限不足

**症状**: `Permission denied: '/dev/ttyUSB0'`

**解决**:
```bash
# 添加用户到dialout组
sudo usermod -a -G dialout $USER
# 注销并重新登录

# 或临时修改权限
sudo chmod 666 /dev/ttyUSB0
```

### 5. Python模块找不到

**症状**: `ModuleNotFoundError: No module named 'xxx'`

**解决**:
```bash
# 确保使用正确的Python环境
which python3
# 应该是 /usr/bin/python3

# 重新安装缺失的模块
pip3 install <module_name>
```

### 6. colcon build失败

**症状**: 编译错误

**解决**:
```bash
# 清理构建文件
cd ~/Dev/VIST
rm -rf build install log

# 安装依赖
rosdep install --from-paths src --ignore-src -r -y

# 重新构建
colcon build
```

---

## 环境配置检查清单

完成以下检查清单以确保环境配置正确：

- [ ] Ubuntu 22.04 LTS已安装
- [ ] ROS2 Humble已安装并可用
- [ ] RealSense SDK已安装
- [ ] CAN工具已安装
- [ ] Python依赖已安装
- [ ] VIST工作空间已构建
- [ ] 外骨骼工作空间已构建
- [ ] 灵巧手工作空间已构建
- [ ] CAN接口可以启动
- [ ] RealSense相机可以识别
- [ ] USB设备权限已配置
- [ ] 网络连接到机械臂正常
- [ ] 所有ROS2包可以找到

---

## 下一步

环境配置完成后，请参考：

1. **[FINAL_STARTUP_GUIDE.md](FINAL_STARTUP_GUIDE.md)** - 系统启动指南
2. **[MODULE_TEST_GUIDE.md](MODULE_TEST_GUIDE.md)** - 模块测试指南
3. **[MONITORING_AND_RECORDING.md](MONITORING_AND_RECORDING.md)** - 监控与数据采集

---

## 技术支持

如遇到问题，请检查：
1. 系统日志：`journalctl -xe`
2. ROS2日志：`~/.ros/log/`
3. dmesg输出：`dmesg | tail -50`

---

**祝配置顺利！**