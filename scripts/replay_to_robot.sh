#!/bin/bash
# 视觉数据回放到真机脚本
# 功能：将录制的视觉数据回放到真实机器人

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  视觉数据回放到真机${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查参数
if [ $# -lt 1 ]; then
    echo -e "${RED}用法: $0 <rosbag目录>${NC}"
    echo ""
    echo "示例:"
    echo "  $0 data/vision_recordings/rec_20260224_153045/rosbag"
    exit 1
fi

BAG_DIR=$1

# 检查rosbag目录
if [ ! -d "$BAG_DIR" ]; then
    echo -e "${RED}错误: rosbag目录不存在: $BAG_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ rosbag目录: $BAG_DIR${NC}"
echo ""

# 配置
echo -e "${BLUE}回放配置:${NC}"
echo ""

# 1. 回放速度
read -p "1. 回放速度（默认1.0）: " RATE
RATE=${RATE:-1.0}

# 2. 是否循环
read -p "2. 是否循环回放? (y/n): " LOOP
if [ "$LOOP" = "y" ]; then
    LOOP_FLAG="--loop"
else
    LOOP_FLAG=""
fi

echo ""
echo -e "${GREEN}回放配置:${NC}"
echo -e "  速度: ${CYAN}${RATE}x${NC}"
echo -e "  循环: ${CYAN}$([ "$LOOP" = "y" ] && echo "是" || echo "否")${NC}"
echo ""

read -p "确认开始回放? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "回放取消"
    exit 0
fi

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止回放...${NC}"

    # 停止所有后台进程
    pkill -f "ros2 bag play" || true
    pkill -f "lbot_driver" || true

    echo -e "${GREEN}✓ 回放已停止${NC}"
}

trap cleanup EXIT INT TERM

echo ""
echo -e "${BLUE}========== 步骤 1: 启动机器人驱动 ==========${NC}"
echo -e "${YELLOW}启动LBot驱动...${NC}"

# 启动机器人驱动（后台）
ros2 launch lbot_driver lbot_start_driver.launch.py > /tmp/lbot_driver.log 2>&1 &
DRIVER_PID=$!

echo -e "${GREEN}✓ 机器人驱动已启动 (PID: $DRIVER_PID)${NC}"
sleep 3

echo ""
echo -e "${BLUE}========== 步骤 2: 启动高频重采样器 ==========${NC}"
echo -e "${YELLOW}启动high_freq_resampler...${NC}"

# 启动高频重采样器（后台）
ros2 run lbot_teleop high_freq_resampler_node \
    --ros-args \
    --params-file external_sdk/arm_teleop/src/lbot_teleop/config/vision_resampler.yaml \
    > /tmp/resampler.log 2>&1 &
RESAMPLER_PID=$!

echo -e "${GREEN}✓ 重采样器已启动 (PID: $RESAMPLER_PID)${NC}"
sleep 2

echo ""
echo -e "${BLUE}========== 步骤 3: 回放rosbag ==========${NC}"
echo -e "${YELLOW}开始回放...${NC}"
echo ""

# 回放rosbag
ros2 bag play "$BAG_DIR" \
    --rate $RATE \
    $LOOP_FLAG \
    --remap /vision_left_joint_control:=/left_arm_joint_control

echo ""
echo -e "${GREEN}✓ 回放完成${NC}"