#!/bin/bash
# 纯视觉数据录制脚本（不连接机器人）
# 功能：只录制视觉数据，可以后续在真机或仿真中回放

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  纯视觉数据录制（离线模式）${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 创建数据目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="${PROJECT_ROOT}/data/vision_recordings/rec_${TIMESTAMP}"
mkdir -p "$DATA_DIR"

echo -e "${GREEN}✓ 数据目录: $DATA_DIR${NC}"
echo ""

# 简化配置
echo -e "${BLUE}录制配置:${NC}"
echo ""

# 1. 录制时长
read -p "1. 录制时长（秒，默认30）: " DURATION
DURATION=${DURATION:-30}

# 2. 是否使用VIST滤波
echo "2. 是否使用VIST滤波?"
echo "   a) 不使用（只录原始视觉数据）"
echo "   b) 使用VIST滤波（录制滤波前后的数据）"
read -p "选择 (a/b): " FILTER_CHOICE

case $FILTER_CHOICE in
    a)
        USE_VIST=false
        REC_NAME="raw_vision"
        ;;
    b)
        USE_VIST=true
        REC_NAME="vist_filtered"
        ;;
    *)
        USE_VIST=false
        REC_NAME="raw_vision"
        ;;
esac

# 3. 录制描述
read -p "3. 录制描述（可选）: " DESCRIPTION
DESCRIPTION=${DESCRIPTION:-"vision_recording"}

# 生成录制ID
REC_ID="${REC_NAME}_${TIMESTAMP}"

echo ""
echo -e "${GREEN}录制配置:${NC}"
echo -e "  录制ID: ${CYAN}$REC_ID${NC}"
echo -e "  时长: ${CYAN}${DURATION}秒${NC}"
echo -e "  VIST滤波: ${CYAN}$([ "$USE_VIST" = true ] && echo "启用" || echo "禁用")${NC}"
echo -e "  描述: ${CYAN}$DESCRIPTION${NC}"
echo ""

read -p "确认开始录制? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "录制取消"
    exit 0
fi

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止录制...${NC}"

    # 停止所有后台进程
    for pid_file in "${DATA_DIR}"/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            name=$(basename "$pid_file" .pid)
            echo -e "${YELLOW}停止 $name (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true
            rm "$pid_file"
        fi
    done

    echo -e "${GREEN}✓ 录制完成${NC}"
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  数据已保存${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}数据位置: $DATA_DIR${NC}"
    echo ""
    echo -e "${BLUE}下一步:${NC}"
    echo -e "  1. 查看数据: ls -lh $DATA_DIR/rosbag"
    echo -e "  2. 回放数据: ros2 bag play $DATA_DIR/rosbag"
    echo -e "  3. 在真机回放: bash scripts/replay_to_robot.sh $DATA_DIR/rosbag"
}

trap cleanup EXIT INT TERM

# 启动函数
start_component() {
    local name=$1
    local command=$2
    local log_file="${DATA_DIR}/${name}.log"
    local pid_file="${DATA_DIR}/${name}.pid"

    echo -e "${YELLOW}启动 $name...${NC}"
    eval "$command" > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"
    echo -e "${GREEN}✓ $name 已启动 (PID: $pid)${NC}"
    sleep 2
}

# 保存录制配置
cat > "${DATA_DIR}/recording_config.yaml" <<EOF
recording_id: $REC_ID
timestamp: $TIMESTAMP
duration: $DURATION
use_vist: $USE_VIST
description: $DESCRIPTION
data_directory: $DATA_DIR
EOF

echo -e "${GREEN}✓ 录制配置已保存${NC}"
echo ""

# ========== 步骤 1: 启动视觉节点 ==========
echo -e "${BLUE}========== 步骤 1: 启动视觉节点 ==========${NC}"
start_component "vision_node" "python3 src/nodes/vision_node_depth.py"

# ========== 步骤 2: 启动视觉→ROS2桥接 ==========
echo -e "${BLUE}========== 步骤 2: 启动视觉→ROS2桥接 ==========${NC}"
start_component "vision_bridge" "python3 scripts/vist_ros2_bridge.py"

# ========== 步骤 3: 启动VIST滤波节点（如果启用）==========
if [ "$USE_VIST" = true ]; then
    echo -e "${BLUE}========== 步骤 3: 启动VIST滤波节点 ==========${NC}"
    start_component "vist_filter" "bash scripts/start_vist_filter.sh --filter vist_kalman --freq 30"
fi

# ========== 步骤 4: 启动rosbag记录 ==========
echo -e "${BLUE}========== 步骤 4: 启动数据记录 ==========${NC}"
BAG_DIR="${DATA_DIR}/rosbag"
mkdir -p "$BAG_DIR"

# 选择要记录的话题
if [ "$USE_VIST" = true ]; then
    TOPICS="/vision_left_joint_control /filtered_left_joint_control /vist_intent_factors"
else
    TOPICS="/vision_left_joint_control"
fi

start_component "rosbag" "ros2 bag record -o $BAG_DIR $TOPICS"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  录制进行中...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}录制信息:${NC}"
echo -e "  录制ID: $REC_ID"
echo -e "  剩余时间: ${DURATION}秒"
echo -e "  数据目录: $DATA_DIR"
echo ""
echo -e "${YELLOW}请在摄像头前做动作...${NC}"
echo ""

# 倒计时
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r${CYAN}剩余时间: ${i}秒  ${NC}"
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"