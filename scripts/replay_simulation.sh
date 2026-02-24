#!/bin/bash
# 在仿真环境中回放录制的视觉数据

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -lt 1 ]; then
    echo -e "${RED}错误: 缺少rosbag路径${NC}"
    echo ""
    echo "使用方法:"
    echo "  $0 <rosbag_path> [speed]"
    echo ""
    echo "示例:"
    echo "  $0 data/vision_recordings/rec_20260224_094232/rosbag"
    echo "  $0 data/vision_recordings/rec_20260224_094232/rosbag 2.0  # 2倍速"
    exit 1
fi

BAG_PATH="$1"
SPEED="${2:-1.0}"  # 默认1.0倍速

# 检查路径是否存在
if [ ! -d "$BAG_PATH" ]; then
    echo -e "${RED}错误: rosbag路径不存在: $BAG_PATH${NC}"
    exit 1
fi

echo -e "${CYAN}================================${NC}"
echo -e "${CYAN}🎬 VIST 仿真回放${NC}"
echo -e "${CYAN}================================${NC}"
echo ""
echo -e "${YELLOW}📁 数据路径:${NC} $BAG_PATH"
echo -e "${YELLOW}⚡ 回放速度:${NC} ${SPEED}x"
echo ""

# 检查依赖
echo -e "${YELLOW}检查依赖...${NC}"

# 检查Python包
python3 -c "import meshcat" 2>/dev/null || {
    echo -e "${RED}❌ 未安装meshcat${NC}"
    echo "请运行: pip install meshcat"
    exit 1
}

python3 -c "import pinocchio" 2>/dev/null || {
    echo -e "${RED}❌ 未安装pinocchio${NC}"
    echo "请运行: pip install pin"
    exit 1
}

python3 -c "import rosbag2_py" 2>/dev/null || {
    echo -e "${RED}❌ 未安装rosbag2_py${NC}"
    echo "请确保已source ROS2环境"
    exit 1
}

echo -e "${GREEN}✅ 依赖检查通过${NC}"
echo ""

# 启动回放
echo -e "${GREEN}▶️  启动仿真回放...${NC}"
echo ""
python3 scripts/replay_in_simulation.py "$BAG_PATH" --speed "$SPEED"