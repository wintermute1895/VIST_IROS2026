#!/bin/bash
# 启动 LinkerHand 键盘控制程序

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LinkerHand L10 键盘控制${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入VIST工作空间
VIST_WS="/home/ilex/Dev/VIST"
if [ ! -d "$VIST_WS" ]; then
    echo -e "${RED}错误: VIST工作空间不存在: $VIST_WS${NC}"
    exit 1
fi

cd "$VIST_WS"

# 加载工作空间
if [ -f "install/setup.bash" ]; then
    source install/setup.bash
    echo -e "${GREEN}✅ 已加载 VIST 工作空间${NC}"
else
    echo -e "${YELLOW}⚠️  未找到 install/setup.bash，跳过工作空间加载${NC}"
fi

# 检查 ROS2 节点是否运行
echo ""
echo -e "${YELLOW}检查 LinkerHand ROS2 节点...${NC}"
if ros2 node list 2>/dev/null | grep -q "linker_hand_advanced_l10"; then
    echo -e "${GREEN}✅ LinkerHand ROS2 节点正在运行${NC}"
else
    echo -e "${RED}❌ LinkerHand ROS2 节点未运行${NC}"
    echo ""
    echo "请先启动 LinkerHand ROS2 节点:"
    echo "  ./scripts/start_6_dexterous_hand.sh"
    echo ""
    echo "或者手动启动:"
    echo "  ros2 run linker_hand_ros2_sdk linker_hand_advanced_l10 --hand_type left --can can0 --is_touch false"
    echo ""
    exit 1
fi

# 检查话题
echo ""
echo -e "${YELLOW}检查 ROS2 话题...${NC}"
HAND_TYPE="${1:-left}"
CMD_TOPIC="/cb_${HAND_TYPE}_hand_control_cmd"
STATE_TOPIC="/cb_${HAND_TYPE}_hand_state"

if ros2 topic list 2>/dev/null | grep -q "$STATE_TOPIC"; then
    echo -e "${GREEN}✅ 找到话题: $STATE_TOPIC${NC}"
else
    echo -e "${RED}❌ 未找到话题: $STATE_TOPIC${NC}"
    echo "请检查 ROS2 节点是否正确启动"
    exit 1
fi

# 启动参数
PRESET="${2:-medium}"

echo ""
echo -e "${GREEN}启动键盘控制程序...${NC}"
echo "手部类型: $HAND_TYPE"
echo "抓取预设: $PRESET"
echo "控制话题: $CMD_TOPIC"
echo "状态话题: $STATE_TOPIC"
echo ""

# 启动键盘控制
python3 scripts/hand_control.py --hand_type "$HAND_TYPE" --preset "$PRESET"