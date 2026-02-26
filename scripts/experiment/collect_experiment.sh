#!/bin/bash
# 完整实验数据采集脚本
# 包含：相机、左臂外骨骼、数据手套、灵巧手、机械臂

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 清理函数 - 处理Ctrl+C信号
cleanup() {
    echo ""
    echo -e "${YELLOW}收到中断信号，正在停止录制...${NC}"

    # 杀死倒计时进程
    if [ ! -z "$COUNTDOWN_PID" ]; then
        kill $COUNTDOWN_PID 2>/dev/null || true
        wait $COUNTDOWN_PID 2>/dev/null || true
    fi

    # 杀死录制进程
    if [ ! -z "$RECORD_PID" ]; then
        kill $RECORD_PID 2>/dev/null || true
        wait $RECORD_PID 2>/dev/null || true
    fi

    echo -e "${GREEN}已停止录制${NC}"
    exit 0
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 实验参数
DURATION=${1:-60}  # 默认60秒
EXPERIMENT_NAME=${2:-"peg_in_hole_$(date +%Y%m%d_%H%M%S)"}
DATA_DIR="data/experiments/${EXPERIMENT_NAME}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}完整实验数据采集${NC}"
echo -e "${BLUE}========================================${NC}"
echo "实验名称: $EXPERIMENT_NAME"
echo "采集时长: ${DURATION}秒"
echo "数据目录: $DATA_DIR"
echo ""

# 创建父目录（但不创建实验目录本身，让ros2 bag record创建）
mkdir -p "data/experiments"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "加载ROS2环境..."
    source /opt/ros/humble/setup.bash
fi

# 加载arm_teleop工作空间（包含lbot_arm_interfaces）
EXO_WS="/home/ilex/Dev/VIST/external_sdk/arm_teleop"
if [ -f "$EXO_WS/install/setup.bash" ]; then
    source "$EXO_WS/install/setup.bash"
fi

# 加载主工作空间
if [ -f "/home/ilex/Dev/VIST/install/setup.bash" ]; then
    source /home/ilex/Dev/VIST/install/setup.bash
fi

# 检查所有必要的节点是否在运行
echo -e "${YELLOW}检查系统状态...${NC}"
REQUIRED_NODES=(
    "/realsense_camera"
    "/linker_hand_advanced_l10"
)

MISSING_NODES=()
for node in "${REQUIRED_NODES[@]}"; do
    if ! ros2 node list 2>/dev/null | grep -q "$node"; then
        MISSING_NODES+=("$node")
    fi
done

if [ ${#MISSING_NODES[@]} -gt 0 ]; then
    echo -e "${RED}错误: 以下节点未运行:${NC}"
    for node in "${MISSING_NODES[@]}"; do
        echo "  - $node"
    done
    echo ""
    echo "请按照以下顺序启动所有节点："
    echo "1. 机械臂使能（控制台）"
    echo "2. bash scripts/start_camera.sh"
    echo "3. bash scripts/start_left_arm_teleop.sh"
    echo "4. bash scripts/start_6_dexterous_hand.sh left"
    exit 1
fi

echo -e "${GREEN}所有节点已就绪${NC}"
echo ""

# 开始采集
echo -e "${YELLOW}准备开始采集...${NC}"
echo "3秒后开始，请准备好操作"
sleep 3

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}开始采集数据！录制 ${DURATION} 秒${NC}"
echo -e "${GREEN}按 Ctrl+C 可以提前停止${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 启动后台进程显示倒计时
(
    for i in $(seq $DURATION -1 1); do
        echo -ne "\r剩余时间: ${i} 秒   "
        sleep 1
    done
    echo -ne "\r录制完成！           \n"
) &
COUNTDOWN_PID=$!

# 录制数据（后台运行）
timeout ${DURATION}s ros2 bag record -o "$DATA_DIR" \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    /camera/color/camera_info \
    /left_arm_joint_control \
    /filtered_left_joint_control \
    /cb_left_hand_control_cmd \
    /cb_left_hand_state \
    /robot_joint_states \
    /filter_performance \
    /robot1/left_arm/joint_states \
    /robot1/left_arm/joint_follow \
    /robot1/left_arm/pose_states \
    /vist_performance &
RECORD_PID=$!

# 等待录制完成
wait $RECORD_PID
RECORD_EXIT_CODE=$?

# 停止倒计时进程
kill $COUNTDOWN_PID 2>/dev/null || true
wait $COUNTDOWN_PID 2>/dev/null || true

echo ""
if [ $RECORD_EXIT_CODE -eq 0 ] || [ $RECORD_EXIT_CODE -eq 124 ]; then
    echo -e "${GREEN}✓ 数据采集完成！${NC}"
else
    echo -e "${RED}❌ 数据采集失败 (退出码: $RECORD_EXIT_CODE)${NC}"
fi
echo "数据保存在: $DATA_DIR"
echo ""

# 生成实验元数据
cat > "$DATA_DIR/metadata.yaml" <<EOF
experiment:
  name: $EXPERIMENT_NAME
  type: peg_in_hole
  duration: ${DURATION}s
  timestamp: $(date -Iseconds)

components:
  - camera: RealSense D435i
  - left_arm: Linkerta Exoskeleton
  - dexterous_hand: Linker Hand L10 (Left)
  - robot: Controlled Robot Arm

topics:
  vision:
    - /camera/color/image_raw
    - /camera/depth/image_rect_raw
  teleoperation:
    - /left_arm_joint_control
    - /filtered_left_joint_control
  hand:
    - /cb_left_hand_control_cmd
    - /cb_left_hand_state
  robot:
    - /robot_joint_states
  else:
    - /filter_performance \
    - /robot1/left_arm/joint_states\
    - /robot1/left_arm/joint_follow\
    - /robot1/left_arm/pose_states\
EOF

echo "元数据已保存: $DATA_DIR/metadata.yaml"