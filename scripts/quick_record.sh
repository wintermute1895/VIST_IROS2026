#!/bin/bash
# 快速录制脚本（用于测试）
# 功能：快速录制控制数据，用于测试和调试
# 输出：data/collection/quick_test/session_*/episode_*/
#
# 用法: bash scripts/quick_record.sh [时长秒数]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 默认配置
DURATION=${1:-30}  # 默认30秒
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="${PROJECT_ROOT}/data/collection/quick_test/session_${TIMESTAMP}/episode_000000"
mkdir -p "$DATA_DIR"
ROSBAG_DIR="$DATA_DIR/rosbag"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}快速录制测试${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  时长: ${DURATION}秒"
echo -e "  数据目录: $DATA_DIR"
echo ""

# Source ROS2环境
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

if [ -f "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash" ]; then
    source "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash"
fi

# 检查控制节点
echo -e "${YELLOW}检查控制节点状态...${NC}"
if ros2 node list 2>/dev/null | grep -q "linkerta_node\|lbot_driver\|teleop_bridge"; then
    echo -e "${GREEN}✓ 检测到运行的控制节点${NC}"
else
    echo -e "${RED}错误：未检测到运行的控制节点！${NC}"
    echo -e "${YELLOW}请先启动控制系统${NC}"
    exit 1
fi
echo ""

# 默认录制话题
TOPICS="/robot1/right_arm/joint_states /right_arm_joint_control"

echo -e "${YELLOW}录制话题:${NC}"
echo "$TOPICS" | tr ' ' '\n' | sed 's/^/  - /'
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止录制...${NC}"
    pkill -f "ros2 bag record" || true

    # 生成元数据
    if [ -d "$ROSBAG_DIR" ] && [ -n "$(ls -A $ROSBAG_DIR 2>/dev/null)" ]; then
        echo -e "${YELLOW}生成元数据...${NC}"
        python3 scripts/generate_episode_metadata.py "$ROSBAG_DIR" \
            --task quick_test 2>/dev/null || echo -e "${YELLOW}  ⚠️  元数据生成失败${NC}"

        # 验证时间同步
        if [ -f "$ROSBAG_DIR/metadata.yaml" ]; then
            echo -e "${YELLOW}验证时间同步...${NC}"
            python3 scripts/validate_time_sync.py "$ROSBAG_DIR" 2>/dev/null || echo -e "${YELLOW}  ⚠️  时间同步验证失败${NC}"
        fi
    fi

    echo -e "${GREEN}✓ 录制完成${NC}"
    echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
}

trap cleanup EXIT INT TERM

# 开始rosbag录制
echo -e "${YELLOW}开始rosbag录制...${NC}"
ros2 bag record -o "$ROSBAG_DIR" $TOPICS > "$DATA_DIR/rosbag.log" 2>&1 &
RECORD_PID=$!

sleep 2

# 检查录制进程
if ! kill -0 $RECORD_PID 2>/dev/null; then
    echo -e "${RED}错误：rosbag录制启动失败${NC}"
    cat "$DATA_DIR/rosbag.log"
    exit 1
fi

echo -e "${GREEN}✓ 录制已启动 (PID: $RECORD_PID)${NC}"
echo ""

# 倒计时
echo -e "${CYAN}录制进行中...${NC}"
echo -e "${YELLOW}请操作机器人或遥操作设备${NC}"
echo ""

for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"

# 停止录制
pkill -f "ros2 bag record" || true
wait $RECORD_PID 2>/dev/null || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}快速录制完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}下一步:${NC}"
echo "  1. 查看数据: ls -lh $DATA_DIR"
echo "  2. 查看元数据: cat $DATA_DIR/metadata.json"
echo "  3. 查看同步报告: cat $DATA_DIR/sync_validation_report.json"
echo ""