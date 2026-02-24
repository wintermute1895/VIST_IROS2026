#!/bin/bash
# VIST完整系统集成测试脚本
# 测试外骨骼+视觉+VIST滤波的完整数据流

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  VIST 完整系统集成测试${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 测试模式选择
echo -e "${BLUE}请选择测试模式:${NC}"
echo "  1) 仅外骨骼 + EMA滤波"
echo "  2) 仅外骨骼 + One Euro滤波"
echo "  3) 仅外骨骼 + VIST卡尔曼滤波"
echo "  4) 外骨骼+视觉 + VIST完整融合 (推荐)"
echo "  5) 自定义配置"
echo ""
read -p "选择 (1-5): " MODE

case $MODE in
    1)
        FILTER_TYPE="ema"
        TEST_NAME="外骨骼_EMA滤波"
        ;;
    2)
        FILTER_TYPE="one_euro"
        TEST_NAME="外骨骼_OneEuro滤波"
        ;;
    3)
        FILTER_TYPE="vist_kalman"
        TEST_NAME="外骨骼_VIST卡尔曼"
        ENABLE_VISION=false
        ;;
    4)
        FILTER_TYPE="vist_kalman"
        TEST_NAME="完整VIST融合"
        ENABLE_VISION=true
        ;;
    5)
        read -p "滤波器类型 (vist_kalman/one_euro/ema): " FILTER_TYPE
        read -p "启用视觉? (y/n): " VISION_INPUT
        if [ "$VISION_INPUT" = "y" ]; then
            ENABLE_VISION=true
        else
            ENABLE_VISION=false
        fi
        TEST_NAME="自定义测试"
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}测试配置:${NC}"
echo -e "  测试名称: ${CYAN}$TEST_NAME${NC}"
echo -e "  滤波器: ${CYAN}$FILTER_TYPE${NC}"
echo -e "  视觉输入: ${CYAN}${ENABLE_VISION:-false}${NC}"
echo ""

# 询问是否记录数据
read -p "是否记录rosbag数据? (y/n): " RECORD_BAG
echo ""

# 创建日志目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="${PROJECT_ROOT}/logs/integration_test_${TIMESTAMP}"
mkdir -p "$LOG_DIR"

echo -e "${YELLOW}日志目录: $LOG_DIR${NC}"
echo ""

# 启动函数
start_component() {
    local name=$1
    local command=$2
    local log_file="${LOG_DIR}/${name}.log"

    echo -e "${YELLOW}启动 $name...${NC}"
    eval "$command" > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "${LOG_DIR}/${name}.pid"
    echo -e "${GREEN}✓ $name 已启动 (PID: $pid)${NC}"
    sleep 2
}

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止所有组件...${NC}"

    for pid_file in "${LOG_DIR}"/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            name=$(basename "$pid_file" .pid)
            echo -e "${YELLOW}停止 $name (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true
        fi
    done

    echo -e "${GREEN}✓ 所有组件已停止${NC}"
    echo -e "${CYAN}日志保存在: $LOG_DIR${NC}"
}

trap cleanup EXIT INT TERM

# 1. 启动外骨骼驱动
echo -e "${BLUE}========== 步骤 1: 启动外骨骼驱动 ==========${NC}"
start_component "exo_driver" "ros2 launch lbot_teleop teleop.launch.py"

# 2. 启动视觉节点 (如果启用)
if [ "$ENABLE_VISION" = true ]; then
    echo -e "${BLUE}========== 步骤 2: 启动视觉节点 ==========${NC}"
    start_component "vision_node" "python3 src/nodes/vision_node_depth.py"
    start_component "vision_bridge" "python3 scripts/vist_ros2_bridge.py"
fi

# 3. 启动VIST滤波节点
echo -e "${BLUE}========== 步骤 3: 启动VIST滤波节点 ==========${NC}"
start_component "vist_filter" "bash scripts/start_vist_filter.sh --filter $FILTER_TYPE"

# 4. 启动性能监控
echo -e "${BLUE}========== 步骤 4: 启动性能监控 ==========${NC}"
start_component "performance_monitor" "bash scripts/start_performance_monitor_advanced.sh"

# 5. 启动rosbag记录 (如果启用)
if [ "$RECORD_BAG" = "y" ]; then
    echo -e "${BLUE}========== 步骤 5: 启动数据记录 ==========${NC}"
    BAG_DIR="${LOG_DIR}/rosbag"
    mkdir -p "$BAG_DIR"
    start_component "rosbag" "ros2 bag record -o $BAG_DIR -a"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有组件已启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}测试信息:${NC}"
echo -e "  测试名称: ${TEST_NAME}"
echo -e "  滤波器: ${FILTER_TYPE}"
echo -e "  日志目录: ${LOG_DIR}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止测试${NC}"
echo ""

# 实时显示话题信息
echo -e "${BLUE}========== ROS2 话题监控 ==========${NC}"
echo ""

# 等待用户中断
while true; do
    sleep 5
    echo -e "${CYAN}[$(date +%H:%M:%S)] 系统运行中...${NC}"

    # 显示话题频率
    echo "  外骨骼频率: $(ros2 topic hz /exo_left_joint_control --window 10 2>/dev/null | grep 'average rate' || echo '未检测到')"
    if [ "$ENABLE_VISION" = true ]; then
        echo "  视觉频率: $(ros2 topic hz /vision_left_joint_control --window 10 2>/dev/null | grep 'average rate' || echo '未检测到')"
    fi
    echo "  滤波输出频率: $(ros2 topic hz /filtered_left_joint_control --window 10 2>/dev/null | grep 'average rate' || echo '未检测到')"
    echo ""
done
