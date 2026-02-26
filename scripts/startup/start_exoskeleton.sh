#!/bin/bash
# 启动左臂外骨骼遥操
# Start Left Arm Teleoperation

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}左臂外骨骼遥操${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "加载ROS2环境..."
    source /opt/ros/humble/setup.bash
fi

# 加载外骨骼工作空间
EXO_WS="/home/ilex/Dev/VIST/external_sdk/arm_teleop"
if [ ! -d "$EXO_WS" ]; then
    echo -e "${RED}错误: 外骨骼工作空间不存在: $EXO_WS${NC}"
    exit 1
fi

cd "$EXO_WS"
source install/setup.bash

# 加载主工作空间（滤波器）
cd /home/ilex/Dev/VIST
source install/setup.bash

echo -e "${GREEN}启动左臂外骨骼...${NC}"
echo ""

# 启动外骨骼（不启动机器人驱动，只启动外骨骼）
# 使用linkerta包直接启动
ros2 run linkerta linkerta_node