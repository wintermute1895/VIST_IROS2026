#!/bin/bash
# Terminal 6: 启动灵巧手驱动
# Start Dexterous Hand Driver

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terminal 6: 灵巧手驱动${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入灵巧手工作空间
HAND_WS="/home/ilex/Dev/VIST/external_sdk/linkerhand-ros2-sdk"
if [ ! -d "$HAND_WS" ]; then
    echo -e "${RED}错误: 灵巧手工作空间不存在: $HAND_WS${NC}"
    exit 1
fi

cd "$HAND_WS"

# 检查并激活 CAN 端口
echo -e "${GREEN}检查 CAN 端口...${NC}"
CAN_STATUS=$(ip link show can0 2>/dev/null | grep -o "state [A-Z]*" | awk '{print $2}')

if [ "$CAN_STATUS" != "UP" ]; then
    echo "激活 CAN 端口 (can0, 1Mbps)..."
    sudo /usr/sbin/ip link set can0 up type can bitrate 1000000
    sleep 1
    echo -e "${GREEN}CAN 端口已激活${NC}"
else
    echo -e "${GREEN}CAN 端口已经激活${NC}"
fi

# 验证 CAN 端口状态
ip -details link show can0

# 加载工作空间
source install/setup.bash

# 启动参数
HAND_TYPE="${1:-right}"
CAN_PORT="${2:-can0}"
ENABLE_TOUCH="${3:-false}"

echo -e "${GREEN}启动灵巧手驱动...${NC}"
echo "手部: $HAND_TYPE"
echo "CAN 端口: $CAN_PORT"
echo "触觉传感器: $ENABLE_TOUCH"
echo ""

# 启动灵巧手节点
ros2 run linker_hand_ros2_sdk linker_hand_advanced_l10 \
  --hand_type "$HAND_TYPE" \
  --can "$CAN_PORT" \
  --is_touch "$ENABLE_TOUCH"
