#!/bin/bash
# Terminal 1: 启动外骨骼驱动
# Start Exoskeleton Driver

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIST_ROOT="$(dirname "$SCRIPT_DIR")"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terminal 1: 外骨骼驱动${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入工作空间
cd "$VIST_ROOT"
source install/setup.bash

echo -e "${GREEN}启动外骨骼驱动...${NC}"
echo "配置: 只发布右臂数据"
echo ""

# 启动外骨骼节点
ros2 run linkerta linkerta_node --ros-args \
  -p publish_left:=false \
  -p publish_right:=true
