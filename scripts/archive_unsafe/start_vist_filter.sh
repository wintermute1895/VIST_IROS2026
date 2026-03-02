#!/bin/bash
# VIST Filter Node 启动脚本
# 将VIST算法集成到ROS2控制流中

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  VIST Filter Node Launcher${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}错误: ROS2环境未设置${NC}"
    echo -e "${YELLOW}请先运行: source /opt/ros/humble/setup.bash${NC}"
    exit 1
fi

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 配置文件路径
CONFIG_FILE="${PROJECT_ROOT}/config/baseline_filters_config.yaml"

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件不存在: $CONFIG_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 项目根目录: $PROJECT_ROOT${NC}"
echo -e "${GREEN}✓ 配置文件: $CONFIG_FILE${NC}"

# 解析命令行参数
ARM_SIDE="left"
FILTER_TYPE="vist_kalman"
OUTPUT_FREQ=100.0

while [[ $# -gt 0 ]]; do
    case $1 in
        --arm)
            ARM_SIDE="$2"
            shift 2
            ;;
        --filter)
            FILTER_TYPE="$2"
            shift 2
            ;;
        --freq)
            OUTPUT_FREQ="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --arm <left|right>     控制哪个臂 (默认: left)"
            echo "  --filter <type>        滤波器类型 (默认: vist_kalman)"
            echo "                         可选: vist_kalman, one_euro, ema, passthrough"
            echo "  --freq <hz>            输出频率 (默认: 100.0)"
            echo "  --help                 显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0 --arm left --filter vist_kalman --freq 100"
            echo "  $0 --arm right --filter one_euro --freq 200"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${BLUE}配置:${NC}"
echo -e "  臂侧: ${GREEN}$ARM_SIDE${NC}"
echo -e "  滤波器: ${GREEN}$FILTER_TYPE${NC}"
echo -e "  频率: ${GREEN}$OUTPUT_FREQ Hz${NC}"
echo ""

# 启动节点
echo -e "${YELLOW}启动 VIST Filter Node...${NC}"

ros2 run vist_nodes vist_filter_node \
    --ros-args \
    --params-file "$CONFIG_FILE" \
    -p arm_side:="$ARM_SIDE" \
    -p filter_type:="$FILTER_TYPE" \
    -p output_freq_hz:=$OUTPUT_FREQ

echo -e "${GREEN}✓ VIST Filter Node 已停止${NC}"
