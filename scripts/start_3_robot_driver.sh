#!/bin/bash
# Terminal 3: 启动机械臂驱动
# Start Robot Arm Driver

set -e

# 加载配置
ARM_TELEOP_ROOT="/home/ilex/Dev/VIST/external_sdk/arm_teleop"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terminal 3: 机械臂驱动${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入 arm_teleop 工作空间
cd "$ARM_TELEOP_ROOT"
source install/setup.bash

echo -e "${GREEN}启动机械臂驱动...${NC}"
echo "机械臂 IP: 192.168.10.21"
echo ""

# 启动 lbot_driver
ros2 run lbot_driver lbot_driver
