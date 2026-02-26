#!/bin/bash
# Terminal 4: 启动遥操作桥接
# Start Teleop Bridge

set -e

# 加载配置
ARM_TELEOP_ROOT="/home/ilex/Dev/VIST/external_sdk/arm_teleop"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terminal 4: 遥操作桥接${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入 arm_teleop 工作空间
cd "$ARM_TELEOP_ROOT"
source install/setup.bash

echo -e "${GREEN}启动遥操作桥接...${NC}"
echo -e "${YELLOW}重要: 包含话题和服务重映射${NC}"
echo ""

# 启动 teleop_bridge 并进行话题和服务重映射
ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file src/lbot_teleop/config/teleop_bridge_params.yaml \
  -r /robot1/right_arm/joint_follow:=/right_arm/joint_follow \
  -r /robot1/right_arm/move_joint:=/right_arm/move_joint
