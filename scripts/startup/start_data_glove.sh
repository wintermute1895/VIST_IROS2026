#!/bin/bash
# Terminal 5: 启动数据手套驱动
# Start Data Glove Driver

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terminal 5: 数据手套驱动${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入手套工作空间
GLOVE_WS="/home/ilex/Dev/VIST/external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2"
if [ ! -d "$GLOVE_WS" ]; then
    echo -e "${RED}错误: 手套工作空间不存在: $GLOVE_WS${NC}"
    exit 1
fi

cd "$GLOVE_WS"
source install/setup.bash

# 检查 USB 设备
echo -e "${GREEN}检查手套 USB 连接...${NC}"
USB_DEVICE=$(ls /dev/ttyUSB* 2>/dev/null | head -1)

if [ -z "$USB_DEVICE" ]; then
    echo -e "${RED}错误: 未找到手套 USB 设备${NC}"
    echo "请检查手套是否已连接"
    exit 1
fi

echo "找到 USB 设备: $USB_DEVICE"

# 设置权限
echo "设置 USB 权限..."
sudo chmod 777 "$USB_DEVICE"

# 启动参数
CALIBRATION="${1:-false}"

echo -e "${GREEN}启动数据手套驱动...${NC}"
if [ "$CALIBRATION" = "true" ]; then
    echo "模式: 强制标定"
    ros2 run linkerhand_retarget handretarget --ros-args -p calibration:=True
else
    echo "模式: 正常运行（不标定）"
    ros2 run linkerhand_retarget handretarget
fi
