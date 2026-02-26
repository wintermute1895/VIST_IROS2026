#!/bin/bash
# 启动VIST滤波器节点
# 支持多种滤波器类型：passthrough, ema, one_euro, vist_kalman

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}启动VIST滤波器节点${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "加载ROS2环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入项目目录
cd /home/ilex/Dev/VIST

# 加载VIST工作空间（如果存在）
if [ -f "install/setup.bash" ]; then
    echo "加载VIST工作空间..."
    source install/setup.bash
fi

# 读取当前配置
FILTER_TYPE=$(grep "filter_type:" config/vist_filter_config.yaml | awk '{print $2}')
echo -e "${YELLOW}当前滤波器类型: ${FILTER_TYPE}${NC}"
echo ""

# 启动VIST滤波节点
echo -e "${GREEN}启动VIST滤波节点（加载配置文件）...${NC}"
python3 src/nodes/vist_filter_node.py --ros-args --params-file config/vist_filter_config.yaml
