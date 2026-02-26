#!/bin/bash
# VIST系统完整数据采集脚本

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== VIST数据采集 ===${NC}"
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
    source ~/Dev/VIST/install/setup.bash
fi

# 创建数据目录
DATA_DIR="$HOME/Dev/VIST/data/experiments"
mkdir -p "$DATA_DIR"

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 实验名称（可自定义）
EXPERIMENT_NAME="${1:-stacking_task}"
OUTPUT_DIR="${DATA_DIR}/${EXPERIMENT_NAME}_${TIMESTAMP}"

echo -e "${GREEN}实验名称: ${EXPERIMENT_NAME}${NC}"
echo -e "${GREEN}输出目录: ${OUTPUT_DIR}${NC}"
echo ""

# 记录的topic列表
TOPICS=(
    "/camera/color/image_raw"
    "/camera/color/camera_info"
    "/cb_left_hand_control_cmd"
    "/cb_left_hand_control_angle_cmd"
    "/filter_performance"
    "/filtered_joint_states"
    "/left_arm_joint_control"
    "/parameter_events"
    "/robot1/left_arm/joint_states"
    "/robot1/left_arm/joint_follow"
    "/robot1/left_arm/pose_states"
    
)

echo -e "${YELLOW}将记录以下topic:${NC}"
for topic in "${TOPICS[@]}"; do
    echo "  - $topic"
done
echo ""

echo -e "${GREEN}开始录制... (按Ctrl+C停止)${NC}"
echo ""

# 开始录制
ros2 bag record \
    --compression-mode file \
    --compression-format zstd \
    "${TOPICS[@]}" \
    -o "$OUTPUT_DIR"

echo ""
echo -e "${GREEN}录制完成！${NC}"
echo -e "数据保存在: ${OUTPUT_DIR}"