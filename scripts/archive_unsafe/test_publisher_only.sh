#!/bin/bash
# 测试发布端数据流（不需要真机）
# 用法: bash scripts/test_publisher_only.sh exo|vision [时长秒数]

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

# 参数
MODE=${1:-exo}  # exo 或 vision
DURATION=${2:-10}  # 默认10秒
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_DIR="${PROJECT_ROOT}/data/test_publisher_${MODE}_${TIMESTAMP}"
mkdir -p "$TEST_DIR"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}发布端数据流测试 - ${MODE}${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  模式: ${MODE}"
echo -e "  时长: ${DURATION}秒"
echo -e "  测试目录: $TEST_DIR"
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止测试...${NC}"
    pkill -f "linkerta_node" || true
    pkill -f "vision_node_depth.py" || true
    pkill -f "vist_ros2_bridge.py" || true
    pkill -f "ros2 bag record" || true
    pkill -f "ros2 topic hz" || true
    echo -e "${GREEN}✓ 测试完成${NC}"
}

trap cleanup EXIT INT TERM

# 根据模式启动不同的节点
if [ "$MODE" = "exo" ]; then
    echo -e "${YELLOW}1. 检查ROS2环境...${NC}"

    # Source ROS2 工作空间
    if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
        source external_sdk/arm_teleop/install/setup.bash
        echo -e "${GREEN}✓ ROS2工作空间已加载${NC}"
    else
        echo -e "${RED}错误：找不到 external_sdk/arm_teleop/install/setup.bash${NC}"
        echo -e "${YELLOW}请先编译ROS2工作空间：${NC}"
        echo -e "  cd external_sdk/arm_teleop"
        echo -e "  colcon build"
        exit 1
    fi

    echo -e "${YELLOW}2. 启动遥操臂节点...${NC}"
    # 使用 launch 文件启动
    ros2 launch linkerta run.launch.py > "$TEST_DIR/linkerta.log" 2>&1 &
    sleep 5  # 增加等待时间
    echo -e "${GREEN}✓ 遥操臂节点已启动${NC}"
elif [ "$MODE" = "vision" ]; then
    echo -e "${YELLOW}1. 启动视觉节点...${NC}"
    python3 src/nodes/vision_node_depth.py > "$TEST_DIR/vision_node.log" 2>&1 &
    sleep 3
    echo -e "${GREEN}✓ 视觉节点已启动${NC}"

    echo -e "${YELLOW}2. 启动视觉桥接...${NC}"
    python3 scripts/vist_ros2_bridge.py > "$TEST_DIR/vision_bridge.log" 2>&1 &
    sleep 3
    echo -e "${GREEN}✓ 视觉桥接已启动${NC}"
else
    echo -e "${RED}错误：模式必须是 'exo' 或 'vision'${NC}"
    exit 1
fi

echo ""

# 列出所有话题
echo -e "${YELLOW}3. 列出所有ROS2话题...${NC}"
sleep 2
ros2 topic list > "$TEST_DIR/all_topics.txt" 2>&1
echo -e "${GREEN}✓ 话题列表保存到: all_topics.txt${NC}"
echo ""

# 查找关节相关话题
echo -e "${YELLOW}4. 查找关节相关话题...${NC}"
grep -E "joint|follow|arm|control" "$TEST_DIR/all_topics.txt" > "$TEST_DIR/joint_topics.txt" || true
echo -e "${CYAN}发现的话题：${NC}"
cat "$TEST_DIR/joint_topics.txt"
echo ""

# 录制所有相关话题
echo -e "${YELLOW}5. 开始录制所有相关话题...${NC}"
BAG_DIR="${TEST_DIR}/rosbag"

TOPICS=$(cat "$TEST_DIR/joint_topics.txt" | tr '\n' ' ')
if [ -z "$TOPICS" ]; then
    echo -e "${RED}错误：没有找到相关话题！${NC}"
    exit 1
fi

echo -e "${CYAN}录制话题：${NC}"
echo "$TOPICS"
echo ""

ros2 bag record -o "$BAG_DIR" $TOPICS > "$TEST_DIR/rosbag.log" 2>&1 &
RECORD_PID=$!
sleep 2

# 监控各个话题的频率
echo -e "${YELLOW}6. 监控话题频率...${NC}"
echo ""

for topic in $TOPICS; do
    echo -e "${CYAN}监控: $topic${NC}"
    timeout $DURATION ros2 topic hz "$topic" > "$TEST_DIR/hz_${topic//\//_}.txt" 2>&1 &
done

# 倒计时
echo ""
echo -e "${GREEN}录制进行中...${NC}"
if [ "$MODE" = "exo" ]; then
    echo -e "${CYAN}请用遥操臂做动作${NC}"
else
    echo -e "${CYAN}请在摄像头前做动作${NC}"
fi
echo ""

for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"

# 等待录制进程结束
sleep 2
pkill -f "ros2 bag record" || true
wait $RECORD_PID 2>/dev/null || true

# 分析录制的数据
echo ""
echo -e "${YELLOW}7. 分析录制的数据...${NC}"
ros2 bag info "$BAG_DIR" > "$TEST_DIR/bag_info.txt" 2>&1
cat "$TEST_DIR/bag_info.txt"

# 汇总频率信息
echo ""
echo -e "${YELLOW}8. 汇总频率信息...${NC}"
echo "========================================" > "$TEST_DIR/frequency_summary.txt"
echo "话题频率汇总" >> "$TEST_DIR/frequency_summary.txt"
echo "========================================" >> "$TEST_DIR/frequency_summary.txt"
echo "" >> "$TEST_DIR/frequency_summary.txt"

for topic in $TOPICS; do
    hz_file="$TEST_DIR/hz_${topic//\//_}.txt"
    if [ -f "$hz_file" ]; then
        echo "话题: $topic" >> "$TEST_DIR/frequency_summary.txt"
        grep -E "average rate|min|max" "$hz_file" >> "$TEST_DIR/frequency_summary.txt" || echo "  无数据" >> "$TEST_DIR/frequency_summary.txt"
        echo "" >> "$TEST_DIR/frequency_summary.txt"
    fi
done

cat "$TEST_DIR/frequency_summary.txt"

# 提取消息数量
echo ""
echo -e "${YELLOW}9. 统计消息数量...${NC}"
echo "========================================" > "$TEST_DIR/message_counts.txt"
echo "话题消息数量统计" >> "$TEST_DIR/message_counts.txt"
echo "========================================" >> "$TEST_DIR/message_counts.txt"
echo "" >> "$TEST_DIR/message_counts.txt"

grep -E "Topic:|Count:" "$TEST_DIR/bag_info.txt" | paste - - >> "$TEST_DIR/message_counts.txt"
cat "$TEST_DIR/message_counts.txt"

# 生成报告
echo ""
echo -e "${YELLOW}10. 生成测试报告...${NC}"
cat > "$TEST_DIR/README.md" << EOF
# 发布端数据流测试报告 - ${MODE}

**测试时间**: $(date)
**测试模式**: ${MODE}
**测试时长**: ${DURATION}秒

## 1. 发现的话题

\`\`\`
$(cat "$TEST_DIR/joint_topics.txt")
\`\`\`

## 2. 录制的数据

\`\`\`
$(cat "$TEST_DIR/bag_info.txt")
\`\`\`

## 3. 频率分析

\`\`\`
$(cat "$TEST_DIR/frequency_summary.txt")
\`\`\`

## 4. 消息数量统计

\`\`\`
$(cat "$TEST_DIR/message_counts.txt")
\`\`\`

## 5. 结论

### 发布端分析

1. **哪个话题有数据？** → 这是发布端实际发布的话题
2. **实际频率是多少？** → 这是真实的发布频率
3. **消息数量是多少？** → 验证数据连续性

### 建议

根据上述分析：
- 如果要录制用于评估，应该录制 **消息数量最多** 的话题
- 确认这个话题是否会被机器人驱动订阅
- 如果需要插值，确认插值后的话题名称

EOF

echo -e "${GREEN}✓ 报告保存到: $TEST_DIR/README.md${NC}"
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}测试完成！${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}测试结果保存在: $TEST_DIR${NC}"
echo ""
echo -e "${YELLOW}关键发现：${NC}"
echo ""

# 显示关键信息
echo -e "${CYAN}发布的话题：${NC}"
cat "$TEST_DIR/joint_topics.txt"
echo ""

echo -e "${CYAN}消息数量最多的话题：${NC}"
grep "Count:" "$TEST_DIR/bag_info.txt" | sort -t: -k2 -nr | head -1
echo ""

echo -e "${YELLOW}下一步：${NC}"
echo "  1. 查看完整报告: cat $TEST_DIR/README.md"
echo "  2. 确认应该录制哪个话题"
echo "  3. 如果需要，测试另一个模式（exo/vision）"
echo ""