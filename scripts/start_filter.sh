#!/bin/bash
# 启动滤波器节点

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}启动滤波器${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "加载ROS2环境..."
    source /opt/ros/humble/setup.bash
fi

# 加载主工作空间
cd /home/ilex/Dev/VIST
source install/setup.bash

echo -e "${GREEN}启动One-Euro滤波器...${NC}"
ros2 run one_euro_filter filter_node