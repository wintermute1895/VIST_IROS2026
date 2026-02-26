#!/bin/bash
# 启动机械臂驱动节点

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}启动机械臂驱动${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入外骨骼工作空间
EXO_WS="/home/ilex/Dev/VIST/external_sdk/arm_teleop"
if [ ! -d "$EXO_WS" ]; then
    echo -e "${RED}错误: 外骨骼工作空间不存在: $EXO_WS${NC}"
    exit 1
fi

cd "$EXO_WS"
source install/setup.bash

echo -e "${GREEN}启动机械臂驱动...${NC}"
echo -e "${YELLOW}注意: 请确保机械臂已上电并连接${NC}"
echo ""

# 启动机械臂驱动
ros2 launch lbot_driver lbot_start_driver.launch.py