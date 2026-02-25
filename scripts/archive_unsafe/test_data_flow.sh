#!/bin/bash
# 测试真实的数据流 - 捕捉所有相关话题
# 用法: bash scripts/test_data_flow.sh [时长秒数]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/..)" && pwd)"
cd "$PROJECT_ROOT"

# 默认配置
DURATION=${1:-10}  # 默认10秒
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_DIR="${PROJECT_ROOT}/data/test_data_flow_${TIMESTAMP}"
mkdir -p "$TEST_DIR"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}数据流测试${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  时长: ${DURATION}秒"
echo -e "  测试目录: $TEST_DIR"
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止测试...${NC}"
    pkill -f "ros2 bag record" || true
    pkill -f "ros2 topic hz" || true
    echo -e "${GREEN}✓ 测试完成${NC}"
}

trap cleanup EXIT INT TERM

# 1. 列出所有话题
echo -e "${YELLOW}1. 列出所有ROS2话题...${NC}"
ros2 topic list > "$TEST_DIR/all_topics.txt" 2>&1
echo -e "${GREEN}✓ 话题列表保存到: all_topics.txt${NC}"
echo ""

# 2. 查找所有包含 "joint" 或 "follow" 的话题
echo -e "${YELLOW}2. 查找关节相关话题...${NC}"
grep -E "joint|follow|arm" "$TEST_DIR/all_topics.txt" > "$TEST_DIR/joint_topics.txt" || true
cat "$TEST_DIR/joint_topics.txt"
echo ""

# 3. 录制所有相关话题
echo -e "${YELLOW}3. 开始录制所有相关话题...${NC}"
BAG_DIR="${TEST_DIR}/rosbag"

# 读取话题列表并录制
TOPICS=$(cat "$TEST_DIR/joint_topics.txt" | tr '\n' ' ')
if [ -z "$TOPICS" ]; then
    echo -e "${RED}错误：没有找到相关话题！${NC}"
    echo -e "${YELLOW}请确保ROS2节点正在运行${NC}"
    exit 1
fi

echo -e "${CYAN}录制话题：${NC}"
echo "$TOPICS"
echo ""

ros2 bag record -o "$BAG_DIR" $TOPICS > "$TEST_DIR/rosbag.log" 2>&1 &
RECORD_PID=$!
sleep 2

# 4. 同时监控各个话题的频率
echo -e "${YELLOW}4. 监控话题频率...${NC}"
echo ""

# 为每个话题启动频率监控
for topic in $TOPICS; do
    echo -e "${CYAN}监控: $topic${NC}"
    timeout $DURATION ros2 topic hz "$topic" > "$TEST_DIR/hz_${topic//\//_}.txt" 2>&1 &
done

# 5. 倒计时
echo ""
echo -e "${GREEN}录制进行中...${NC}"
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"

# 6. 等待录制进程结束
sleep 2
pkill -f "ros2 bag record" || true
wait $RECORD_PID 2>/dev/null || true

# 7. 分析录制的数据
echo ""
echo -e "${YELLOW}5. 分析录制的数据...${NC}"
ros2 bag info "$BAG_DIR" > "$TEST_DIR/bag_info.txt" 2>&1
cat "$TEST_DIR/bag_info.txt"

# 8. 汇总频率信息
echo ""
echo -e "${YELLOW}6. 汇总频率信息...${NC}"
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

# 9. 生成报告
echo ""
echo -e "${YELLOW}7. 生成测试报告...${NC}"
cat > "$TEST_DIR/README.md" << EOF
# 数据流测试报告

**测试时间**: $(date)
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

## 4. 结论

请检查以下问题：

1. **哪个话题的消息数量最多？** → 这可能是真正驱动机器人的话题
2. **哪个话题的频率最高？** → 这可能是插值后的高频指令
3. **哪些话题有数据，哪些没有？** → 确认实际的数据流路径

## 5. 建议

根据上述分析，应该录制 **消息数量最多且频率最高** 的话题用于性能评估。

EOF

echo -e "${GREEN}✓ 报告保存到: $TEST_DIR/README.md${NC}"
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}测试完成！${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}测试结果保存在: $TEST_DIR${NC}"
echo ""
echo -e "${YELLOW}请查看以下文件：${NC}"
echo -e "  - all_topics.txt: 所有话题列表"
echo -e "  - joint_topics.txt: 关节相关话题"
echo -e "  - bag_info.txt: rosbag信息"
echo -e "  - frequency_summary.txt: 频率汇总"
echo -e "  - README.md: 完整报告"
echo ""