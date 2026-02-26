#!/bin/bash
# 可选: 启动数据采集相机
# Optional: Start Data Collection Camera

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIST_ROOT="$(dirname "$SCRIPT_DIR")"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}可选: 数据采集相机${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入工作空间
cd "$VIST_ROOT"
source install/setup.bash

echo -e "${GREEN}启动数据采集相机...${NC}"
echo -e "${YELLOW}注意: 这是可选组件，用于记录视觉数据${NC}"
echo ""

# 相机参数
# 用法: ./start_camera.sh [--with-viewer] [serial_number]
WITH_VIEWER=false
SERIAL_NUMBER=""

# 解析参数
for arg in "$@"; do
    if [ "$arg" == "--with-viewer" ]; then
        WITH_VIEWER=true
    elif [ -z "$SERIAL_NUMBER" ] && [ "$arg" != "--with-viewer" ]; then
        SERIAL_NUMBER="$arg"
    fi
done

# 如果没有指定序列号，使用配置文件中的默认值
if [ -z "$SERIAL_NUMBER" ]; then
    SERIAL_NUMBER="348122071157"  # 尾号7相机
fi

WIDTH=848
HEIGHT=480
FPS=30

echo "相机配置:"
echo "  序列号: $SERIAL_NUMBER"
echo "  分辨率: ${WIDTH}x${HEIGHT}"
echo "  帧率: ${FPS} fps"
if [ "$WITH_VIEWER" = true ]; then
    echo "  实时显示: 启用"
else
    echo "  实时显示: 禁用（使用 --with-viewer 启用）"
fi
echo ""

# 构建参数
CAMERA_PARAMS="-p width:=$WIDTH -p height:=$HEIGHT -p fps:=$FPS"

if [ -n "$SERIAL_NUMBER" ]; then
    # 序列号需要用引号包裹，确保作为字符串传递
    CAMERA_PARAMS="$CAMERA_PARAMS -p serial_number:=\\\"$SERIAL_NUMBER\\\""
fi

# 如果启用实时显示，在后台启动图像查看器
if [ "$WITH_VIEWER" = true ]; then
    echo -e "${GREEN}启动实时图像查看器...${NC}"
    sleep 2  # 等待相机节点启动
    ros2 run rqt_image_view rqt_image_view /camera/color/image_raw &
    VIEWER_PID=$!
    echo "图像查看器 PID: $VIEWER_PID"
fi

# 启动相机节点
echo -e "${GREEN}启动相机节点...${NC}"
# 使用当前环境的 Python 直接运行模块
# 注意：参数需要正确传递，序列号用引号包裹
python3 -m camera_manager.realsense_camera_node --ros-args \
  -p color_width:=$WIDTH \
  -p color_height:=$HEIGHT \
  -p color_fps:=$FPS \
  -p enable_depth:=false \
  -p serial_number:="$SERIAL_NUMBER"
