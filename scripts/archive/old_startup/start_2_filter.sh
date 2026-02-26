#!/bin/bash
# Terminal 2: 启动滤波节点
# Start Filter Node

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
echo -e "${BLUE}Terminal 2: 滤波节点${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
fi

# 进入工作空间
cd "$VIST_ROOT"

# 默认滤波器类型
FILTER_TYPE="${1:-one_euro}"

echo -e "${GREEN}启动滤波节点...${NC}"
echo "滤波器类型: $FILTER_TYPE"
echo ""

# 根据滤波器类型设置参数
case $FILTER_TYPE in
    none)
        echo "使用无滤波模式（直通）"
        FILTER_PARAMS="-p filter_type:=none"
        ;;
    ema)
        ALPHA="${2:-0.3}"
        echo "使用 EMA 滤波，alpha=$ALPHA"
        FILTER_PARAMS="-p filter_type:=ema -p ema_alpha:=$ALPHA"
        ;;
    one_euro)
        MIN_CUTOFF="${2:-1.0}"
        BETA="${3:-0.007}"
        echo "使用 One-Euro 滤波，min_cutoff=$MIN_CUTOFF, beta=$BETA"
        FILTER_PARAMS="-p filter_type:=one_euro -p one_euro_min_cutoff:=$MIN_CUTOFF -p one_euro_beta:=$BETA"
        ;;
    vist_kalman)
        echo "使用 VIST Kalman 滤波"
        FILTER_PARAMS="-p filter_type:=vist_kalman"
        ;;
    *)
        echo -e "${YELLOW}未知的滤波器类型: $FILTER_TYPE，使用 one_euro${NC}"
        FILTER_PARAMS="-p filter_type:=one_euro -p one_euro_min_cutoff:=1.0 -p one_euro_beta:=0.007"
        ;;
esac

# 启动滤波节点
python3 src/nodes/unified_filter_node.py --ros-args \
  $FILTER_PARAMS \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true \
  -p performance_topic:=/filter_performance
