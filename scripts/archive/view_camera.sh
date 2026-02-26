#!/bin/bash
# 查看相机实时画面
# View Camera Real-time Feed

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}相机实时画面查看器${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 话题选择
TOPIC="${1:-/camera/color/image_raw}"

echo -e "${GREEN}启动图像查看器...${NC}"
echo "话题: $TOPIC"
echo ""
echo "可用话题:"
echo "  /camera/color/image_raw  - 彩色图像"
echo "  /camera/depth/image_raw  - 深度图像"
echo ""

# 启动图像查看器
ros2 run rqt_image_view rqt_image_view $TOPIC
