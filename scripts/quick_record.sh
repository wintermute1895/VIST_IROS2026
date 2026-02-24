#!/bin/bash
# 快速录制视觉数据（使用默认配置）
# 用法: bash scripts/quick_record.sh [时长秒数]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 默认配置
DURATION=${1:-30}  # 默认30秒
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="${PROJECT_ROOT}/data/vision_recordings/rec_${TIMESTAMP}"
mkdir -p "$DATA_DIR"

echo -e "${CYAN}开始录制视觉数据...${NC}"
echo -e "  时长: ${DURATION}秒"
echo -e "  数据目录: $DATA_DIR"
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止录制...${NC}"
    pkill -f "vision_node_depth.py" || true
    pkill -f "vist_ros2_bridge.py" || true
    pkill -f "high_freq_resampler" || true
    pkill -f "ros2 bag record" || true
    echo -e "${GREEN}✓ 录制完成${NC}"
    echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
}

trap cleanup EXIT INT TERM

# 启动视觉节点
echo -e "${YELLOW}启动视觉节点...${NC}"
python3 src/nodes/vision_node_depth.py > "$DATA_DIR/vision_node.log" 2>&1 &
sleep 3

# 启动视觉桥接
echo -e "${YELLOW}启动视觉桥接...${NC}"
python3 scripts/vist_ros2_bridge.py > "$DATA_DIR/vision_bridge.log" 2>&1 &
sleep 3

# 启动高频重采样节点（插值到200Hz）
echo -e "${YELLOW}启动高频重采样节点...${NC}"
ros2 launch lbot_teleop high_freq_resampler.launch.py > "$DATA_DIR/resampler.log" 2>&1 &
sleep 3

# 启动rosbag录制
echo -e "${YELLOW}启动数据录制...${NC}"
BAG_DIR="${DATA_DIR}/rosbag"
# 不要提前创建目录，让ros2 bag record自己创建
# 注意：录制实际发送给真机驱动的话题（经过插值后的200Hz指令）
ros2 bag record -o "$BAG_DIR" /robot1/right_arm/joint_follow > "$DATA_DIR/rosbag.log" 2>&1 &
sleep 2

echo ""
echo -e "${GREEN}录制进行中...${NC}"
echo -e "${CYAN}请在摄像头前做动作${NC}"
echo ""

# 倒计时
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"