#!/bin/bash
# 快速测试相机模块

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIST_ROOT="$(dirname "$SCRIPT_DIR")"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}相机模块快速测试${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    source /opt/ros/humble/setup.bash
fi

cd "$VIST_ROOT"
source install/setup.bash

# 启动相机（后台）
echo -e "${GREEN}[1/3] 启动相机节点...${NC}"
bash scripts/start_camera.sh &
CAMERA_PID=$!

# 等待启动
sleep 3

# 检查节点
echo -e "${GREEN}[2/3] 检查节点状态...${NC}"
if ros2 node list | grep -q "realsense_camera"; then
    echo -e "${GREEN}✓ 相机节点已启动${NC}"
else
    echo -e "${RED}✗ 相机节点未找到${NC}"
    kill $CAMERA_PID 2>/dev/null || true
    exit 1
fi

# 检查话题频率
echo -e "${GREEN}[3/3] 检查发布频率（10秒）...${NC}"
timeout 10 ros2 topic hz /camera/color/image_raw || true

echo ""
echo -e "${YELLOW}测试完成，按Ctrl+C停止相机节点${NC}"

# 等待用户中断
wait $CAMERA_PID