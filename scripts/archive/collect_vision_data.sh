#!/bin/bash
# 纯视觉遥操作数据采集脚本
# 功能：录制摄像头看到的人的姿态，计算轨迹，存储数据，评估性能

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  纯视觉遥操作数据采集系统${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 创建数据目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="${PROJECT_ROOT}/data/vision_experiments/exp_${TIMESTAMP}"
mkdir -p "$DATA_DIR"

echo -e "${GREEN}✓ 数据目录: $DATA_DIR${NC}"
echo ""

# 询问实验配置
echo -e "${BLUE}实验配置:${NC}"
echo ""

# 1. 是否使用VIST滤波
echo "1. 是否使用VIST滤波?"
echo "   a) 不使用（纯视觉，基线）"
echo "   b) 使用EMA滤波"
echo "   c) 使用One Euro滤波"
echo "   d) 使用VIST Kalman滤波（完整）"
read -p "选择 (a/b/c/d): " FILTER_CHOICE

case $FILTER_CHOICE in
    a)
        USE_VIST=false
        FILTER_TYPE="passthrough"
        EXP_NAME="baseline_no_filter"
        ;;
    b)
        USE_VIST=true
        FILTER_TYPE="ema"
        EXP_NAME="ema_filter"
        ;;
    c)
        USE_VIST=true
        FILTER_TYPE="one_euro"
        EXP_NAME="one_euro_filter"
        ;;
    d)
        USE_VIST=true
        FILTER_TYPE="vist_kalman"
        EXP_NAME="vist_kalman_full"
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

# 2. 实验时长
read -p "2. 实验时长（秒，默认60）: " DURATION
DURATION=${DURATION:-60}

# 3. 任务类型
echo "3. 任务类型:"
echo "   a) 自由运动"
echo "   b) 目标到达"
echo "   c) 轨迹跟踪"
read -p "选择 (a/b/c): " TASK_TYPE

case $TASK_TYPE in
    a) TASK_NAME="free_motion" ;;
    b) TASK_NAME="reaching" ;;
    c) TASK_NAME="tracking" ;;
    *) TASK_NAME="free_motion" ;;
esac

# 4. 受试者ID
read -p "4. 受试者ID（默认user01）: " SUBJECT_ID
SUBJECT_ID=${SUBJECT_ID:-user01}

# 生成实验ID
EXP_ID="${EXP_NAME}_${TASK_NAME}_${SUBJECT_ID}_${TIMESTAMP}"

echo ""
echo -e "${GREEN}实验配置:${NC}"
echo -e "  实验ID: ${CYAN}$EXP_ID${NC}"
echo -e "  滤波器: ${CYAN}$FILTER_TYPE${NC}"
echo -e "  时长: ${CYAN}${DURATION}秒${NC}"
echo -e "  任务: ${CYAN}$TASK_NAME${NC}"
echo -e "  受试者: ${CYAN}$SUBJECT_ID${NC}"
echo ""

read -p "确认开始实验? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "实验取消"
    exit 0
fi

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止所有组件...${NC}"

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

    echo -e "${GREEN}✓ 所有组件已停止${NC}"
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  数据采集完成${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
    echo ""
    echo -e "${BLUE}下一步:${NC}"
    echo -e "  1. 查看数据: ls -lh $DATA_DIR"
    echo -e "  2. 评估性能: python scripts/evaluate_vision_performance.py $DATA_DIR"
    echo -e "  3. 可视化: python scripts/visualize_trajectory.py $DATA_DIR"
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

# 保存实验配置
cat > "${DATA_DIR}/experiment_config.yaml" <<EOF
experiment_id: $EXP_ID
timestamp: $TIMESTAMP
subject_id: $SUBJECT_ID
task_type: $TASK_NAME
duration: $DURATION
filter_type: $FILTER_TYPE
use_vist: $USE_VIST
data_directory: $DATA_DIR
EOF

echo -e "${GREEN}✓ 实验配置已保存${NC}"
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
    start_component "vist_filter" "bash scripts/start_vist_filter.sh --filter $FILTER_TYPE --freq 30"
fi

# ========== 步骤 4: 启动性能监控 ==========
echo -e "${BLUE}========== 步骤 4: 启动性能监控 ==========${NC}"
start_component "performance_monitor" "bash scripts/start_performance_monitor_advanced.sh"

# ========== 步骤 5: 启动rosbag记录 ==========
echo -e "${BLUE}========== 步骤 5: 启动数据记录 ==========${NC}"
BAG_DIR="${DATA_DIR}/rosbag"
mkdir -p "$BAG_DIR"

# 选择要记录的话题
if [ "$USE_VIST" = true ]; then
    TOPICS="/vision_left_joint_control /filtered_left_joint_control /vist_performance /vist_intent_factors"
else
    TOPICS="/vision_left_joint_control /vist_performance"
fi

start_component "rosbag" "ros2 bag record -o $BAG_DIR $TOPICS"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  数据采集进行中...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}实验信息:${NC}"
echo -e "  实验ID: $EXP_ID"
echo -e "  剩余时间: ${DURATION}秒"
echo -e "  数据目录: $DATA_DIR"
echo ""
echo -e "${YELLOW}请开始执行任务...${NC}"
echo ""

# 倒计时
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r${CYAN}剩余时间: ${i}秒  ${NC}"
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 数据采集完成！${NC}"
