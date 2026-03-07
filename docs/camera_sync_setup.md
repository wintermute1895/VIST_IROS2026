# RealSense 双相机全局时间戳同步配置指南

## 概述

本文档说明如何配置 RealSense 双相机系统以实现高精度时间戳同步，用于 Diffusion Policy 等机器学习任务的数据采集。

## 核心功能

### 1. 全局时间戳映射 (Global Time Enabled)
- **参数**: `global_time_enabled: true`
- **作用**: 强制驱动读取相机内部的 64 位硬件时钟，并通过系统 NTP 进行底层修正
- **效果**: `msg.header.stamp` 反映真实的快门时间，而非 USB 传输时间

### 2. 内部流同步 (Enable Sync)
- **参数**: `enable_sync: true`
- **作用**: 确保单个相机内部的深度流和彩色流严格对齐
- **效果**: 同一时刻的深度图和彩色图时间戳一致

### 3. 多相机硬件同步 (Inter-Camera Sync Mode)
- **参数**: `inter_cam_sync_mode`
  - `1` = Master（主相机，D435i）
  - `2` = Slave（从相机，D405）
- **作用**: 尝试在驱动层面协调多相机的采集时序
- **注意**: D405 无物理同步引脚，但软件层会尽力配合

## 系统级时间同步配置

### 前置要求

在运行 launch 文件之前，需要确保 Linux 系统的时间同步服务正常运行。

### 方案 1: 使用 Chrony（推荐）

Chrony 是现代 Linux 发行版推荐的 NTP 客户端，响应速度快、精度高。

#### 安装 Chrony

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install chrony

# 检查服务状态
sudo systemctl status chrony
```

#### 配置 Chrony

编辑配置文件：

```bash
sudo nano /etc/chrony/chrony.conf
```

添加或修改以下内容：

```conf
# 使用国内 NTP 服务器（更快）
server ntp.aliyun.com iburst
server ntp.tencent.com iburst
server ntp1.aliyun.com iburst

# 或使用全球 NTP 服务器
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server 2.pool.ntp.org iburst

# 允许系统时钟快速调整
makestep 1.0 3

# 启用内核时间同步
rtcsync
```

重启服务：

```bash
sudo systemctl restart chrony
```

#### 验证同步状态

```bash
# 查看时间源状态
chronyc sources -v

# 查看同步统计
chronyc tracking

# 期望输出示例：
# System time     : 0.000012345 seconds slow of NTP time
# RMS offset      : 0.000234567 seconds
```

### 方案 2: 使用 systemd-timesyncd（轻量级）

Ubuntu 默认自带的时间同步服务。

#### 启用服务

```bash
sudo systemctl enable systemd-timesyncd
sudo systemctl start systemd-timesyncd
```

#### 配置 NTP 服务器

编辑配置文件：

```bash
sudo nano /etc/systemd/timesyncd.conf
```

添加：

```conf
[Time]
NTP=ntp.aliyun.com ntp.tencent.com
FallbackNTP=0.pool.ntp.org 1.pool.ntp.org
```

重启服务：

```bash
sudo systemctl restart systemd-timesyncd
```

#### 验证同步状态

```bash
timedatectl status

# 期望输出：
# System clock synchronized: yes
# NTP service: active
```

### 方案 3: 使用传统 ntpd

```bash
# 安装
sudo apt install ntp

# 编辑配置
sudo nano /etc/ntp.conf

# 添加服务器
server ntp.aliyun.com iburst
server ntp.tencent.com iburst

# 重启服务
sudo systemctl restart ntp

# 查看状态
ntpq -p
```

## Launch 文件使用方法

### 基本启动

```bash
# 使用默认参数
ros2 launch bringup camera_sync.launch.py

# 指定序列号
ros2 launch bringup camera_sync.launch.py \
    d435i_serial:=348122071157 \
    d405_serial:=409122273357

# 自定义分辨率和帧率
ros2 launch bringup camera_sync.launch.py \
    color_width:=848 \
    color_height:=480 \
    fps:=30

# 关闭深度流（仅彩色）
ros2 launch bringup camera_sync.launch.py \
    enable_depth:=false
```

### 查看相机序列号

如果不知道相机序列号，可以使用以下命令查询：

```bash
# 方法 1: 使用 realsense-viewer
realsense-viewer

# 方法 2: 使用 rs-enumerate-devices
rs-enumerate-devices | grep "Serial Number"

# 方法 3: 使用 Python
python3 -c "import pyrealsense2 as rs; ctx = rs.context(); \
    [print(f'{dev.get_info(rs.camera_info.name)}: {dev.get_info(rs.camera_info.serial_number)}') \
    for dev in ctx.devices]"
```

### 验证话题发布

启动后，检查话题是否正常发布：

```bash
# 查看所有相机话题
ros2 topic list | grep camera

# 期望输出：
# /camera_global/color/image_raw
# /camera_global/color/camera_info
# /camera_global/depth/image_raw
# /camera_wrist/color/image_raw
# /camera_wrist/color/camera_info
# /camera_wrist/depth/image_raw

# 查看话题频率
ros2 topic hz /camera_global/color/image_raw
ros2 topic hz /camera_wrist/color/image_raw

# 查看消息内容（验证时间戳）
ros2 topic echo /camera_global/color/image_raw --field header.stamp
```

## 时间戳验证

使用之前创建的分析脚本验证时间戳同步质量：

```bash
# 录制一段测试数据
ros2 bag record -o test_sync \
    /camera_global/color/image_raw \
    /camera_wrist/color/image_raw

# 运行时间戳分析
python3 scripts/analysis/analyze_camera_sync.py --bag test_sync

# 期望结果：
# - 平均时间差 < 10ms（良好）
# - 最大时间差 < 20ms（可接受）
```

## 常见问题排查

### 1. 时间戳仍然不准确

**可能原因**：
- 系统时间未同步
- USB 带宽不足
- 相机固件版本过旧

**解决方案**：
```bash
# 检查系统时间同步
timedatectl status

# 更新相机固件
# 访问 https://www.intelrealsense.com/developers/
# 下载最新固件并使用 realsense-viewer 更新

# 检查 USB 连接
lsusb -t
# 确保相机连接到 USB 3.0 端口（5000M）
```

### 2. 相机启动失败

**可能原因**：
- 序列号错误
- USB 权限问题
- 相机被其他进程占用

**解决方案**：
```bash
# 检查相机是否被识别
rs-enumerate-devices

# 设置 USB 权限
sudo usermod -aG video $USER
sudo udevadm control --reload-rules && sudo udevadm trigger

# 重启 udev 服务
sudo systemctl restart udev
```

### 3. 帧率不稳定

**可能原因**：
- USB 带宽限制
- 系统负载过高
- 分辨率/帧率组合不支持

**解决方案**：
```bash
# 降低分辨率或帧率
ros2 launch bringup camera_sync.launch.py \
    color_width:=640 \
    color_height:=480 \
    fps:=15

# 关闭不需要的流
ros2 launch bringup camera_sync.launch.py \
    enable_depth:=false

# 检查系统负载
htop
```

## 性能优化建议

### 1. USB 带宽优化

```bash
# 增加 USB 缓冲区大小
echo 1000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
```

### 2. 实时性优化

```bash
# 设置进程优先级
sudo chrt -f 99 -p $(pgrep realsense2_camera_node)

# 或在 launch 文件中添加：
# 'priority': 99,
# 'policy': 'SCHED_FIFO',
```

### 3. 网络时间同步优化

```bash
# 使用本地 NTP 服务器（如果有）
# 编辑 /etc/chrony/chrony.conf
server 192.168.1.1 iburst prefer

# 或使用 GPS 时间源（最高精度）
```

## 参考资料

- [RealSense ROS2 Wrapper 文档](https://github.com/IntelRealSense/realsense-ros)
- [Chrony 官方文档](https://chrony.tuxfamily.org/documentation.html)
- [RealSense 全局时间戳说明](https://dev.intelrealsense.com/docs/api-how-to#section-global-timestamps)

## 联系方式

如有问题，请联系 VIST 团队或提交 Issue。