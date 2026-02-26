#!/bin/bash
# 启动意图计算节点
# 用法: ./start_intent_calculation.sh [--with-viewer]

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 获取VIST根目录
VIST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 设置ROS2环境
cd "$VIST_ROOT"
source install/setup.bash

echo -e "${GREEN}启动意图计算节点...${NC}"
echo -e "${YELLOW}注意: 需要先启动相机节点${NC}"
echo ""

# 解析参数
WITH_VIEWER=false
for arg in "$@"; do
    if [ "$arg" == "--with-viewer" ]; then
        WITH_VIEWER=true
    fi
done

# 从配置文件读取参数
CONFIG_FILE="$VIST_ROOT/config/system_config.yaml"

# 如果启用实时显示，在后台启动图像查看器
if [ "$WITH_VIEWER" = true ]; then
    echo -e "${GREEN}启动实时图像查看器...${NC}"
    sleep 2  # 等待节点启动
    ros2 run rqt_image_view rqt_image_view /intent_debug_image &
    VIEWER_PID=$!
    echo "图像查看器 PID: $VIEWER_PID"
fi

# 启动意图计算节点（参数从配置文件读取）
echo -e "${GREEN}启动意图计算节点...${NC}"
python3 src/nodes/intent_calculation_node.py
