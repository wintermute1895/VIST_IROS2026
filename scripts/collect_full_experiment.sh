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

# 创建数据目录
mkdir -p "$DATA_DIR"

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "加载ROS2环境..."
    source /opt/ros/humble/setup.bash
fi

# 检查所有必要的节点是否在运行
echo -e "${YELLOW}检查系统状态...${NC}"
REQUIRED_NODES=(
    "/realsense_camera"
    "/linker_hand_advanced_l10"
    "/handretarget_node"
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
    echo "4. bash scripts/start_5_data_glove.sh"
    echo "5. bash scripts/start_6_dexterous_hand.sh left"
    exit 1
fi

echo -e "${GREEN}所有节点已就绪${NC}"
echo ""

# 开始采集
echo -e "${YELLOW}准备开始采集...${NC}"
echo "3秒后开始，请准备好操作"
sleep 3

echo -e "${GREEN}开始采集数据！${NC}"
ros2 bag record -o "$DATA_DIR" \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    /camera/color/camera_info \
    /left_arm_joint_control \
    /filtered_left_joint_control \
    /cb_left_hand_control_cmd \
    /cb_left_hand_state \
    /robot_joint_states \
    /filter_performance \
    --duration $DURATION

echo ""
echo -e "${GREEN}数据采集完成！${NC}"
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
  - data_glove: Linker Data Glove (Left)
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
EOF

echo "元数据已保存: $DATA_DIR/metadata.yaml"