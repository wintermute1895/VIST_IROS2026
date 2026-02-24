#!/bin/bash
# 测试遥操臂的真实数据流
# 用法: bash scripts/test_exo_data_flow.sh [时长秒数]

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
TEST_DIR="${PROJECT_ROOT}/data/test_exo_flow_${TIMESTAMP}"
mkdir -p "$TEST_DIR"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}遥操臂数据流测试${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  时长: ${DURATION}秒"
echo -e "  测试目录: $TEST_DIR"
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止测试...${NC}"
    pkill -f "linkerta_node" || true
    pkill -f "lbot_driver" || true
    pkill -f "ros2 bag record" || true
    pkill -f "ros2 topic hz" || true
    echo -e "${GREEN}✓ 测试完成${NC}"
}

trap cleanup EXIT INT TERM

# 1. 启动遥操臂节点
echo -e "${YELLOW}1. 启动遥操臂节点...${NC}"
ros2 run linkerta linkerta_node > "$TEST_DIR/linkerta.log" 2>&1 &
sleep 3
echo -e "${GREEN}✓ 遥操臂节点已启动${NC}"
echo ""

# 2. 启动机器人驱动（如果需要）
echo -e "${YELLOW}2. 检查是否需要启动机器人驱动...${NC}"
if ros2 node list | grep -q "lbot_driver"; then
    echo -e "${GREEN}✓ 机器人驱动已在运行${NC}"
else
    echo -e "${YELLOW}机器人驱动未运行，跳过...${NC}"
    echo -e "${CYAN}提示：如果要测试完整数据流，请先启动机器人驱动${NC}"
fi
echo ""

# 3. 列出所有话题
echo -e "${YELLOW}3. 列出所有ROS2话题...${NC}"
sleep 2
ros2 topic list > "$TEST_DIR/all_topics.txt" 2>&1
echo -e "${GREEN}✓ 话题列表保存到: all_topics.txt${NC}"
echo ""

# 4. 查找所有包含 "joint" 或 "follow" 或 "arm" 的话题
echo -e "${YELLOW}4. 查找关节相关话题...${NC}"
grep -E "joint|follow|arm" "$TEST_DIR/all_topics.txt" > "$TEST_DIR/joint_topics.txt" || true
echo -e "${CYAN}发现的话题：${NC}"
cat "$TEST_DIR/joint_topics.txt"
echo ""

# 5. 录制所有相关话题
echo -e "${YELLOW}5. 开始录制所有相关话题...${NC}"
BAG_DIR="${TEST_DIR}/rosbag"

# 读取话题列表并录制
TOPICS=$(cat "$TEST_DIR/joint_topics.txt" | tr '\n' ' ')
if [ -z "$TOPICS" ]; then
    echo -e "${RED}错误：没有找到相关话题！${NC}"
    echo -e "${YELLOW}请确保遥操臂节点正在运行${NC}"
    exit 1
fi

echo -e "${CYAN}录制话题：${NC}"
echo "$TOPICS"
echo ""

ros2 bag record -o "$BAG_DIR" $TOPICS > "$TEST_DIR/rosbag.log" 2>&1 &
RECORD_PID=$!
sleep 2

# 6. 同时监控各个话题的频率
echo -e "${YELLOW}6. 监控话题频率...${NC}"
echo ""

# 为每个话题启动频率监控
for topic in $TOPICS; do
    echo -e "${CYAN}监控: $topic${NC}"
    timeout $DURATION ros2 topic hz "$topic" > "$TEST_DIR/hz_${topic//\//_}.txt" 2>&1 &
done

# 7. 倒计时
echo ""
echo -e "${GREEN}录制进行中...${NC}"
echo -e "${CYAN}请用遥操臂控制机械臂${NC}"
echo ""
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"

# 8. 等待录制进程结束
sleep 2
pkill -f "ros2 bag record" || true
wait $RECORD_PID 2>/dev/null || true

# 9. 分析录制的数据
echo ""
echo -e "${YELLOW}7. 分析录制的数据...${NC}"
ros2 bag info "$BAG_DIR" > "$TEST_DIR/bag_info.txt" 2>&1
cat "$TEST_DIR/bag_info.txt"

# 10. 汇总频率信息
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

# 11. 提取每个话题的消息数量
echo ""
echo -e "${YELLOW}9. 统计消息数量...${NC}"
echo "========================================" > "$TEST_DIR/message_counts.txt"
echo "话题消息数量统计" >> "$TEST_DIR/message_counts.txt"
echo "========================================" >> "$TEST_DIR/message_counts.txt"
echo "" >> "$TEST_DIR/message_counts.txt"

grep -E "Topic:|Count:" "$TEST_DIR/bag_info.txt" | paste - - >> "$TEST_DIR/message_counts.txt"
cat "$TEST_DIR/message_counts.txt"

# 12. 生成报告
echo ""
echo -e "${YELLOW}10. 生成测试报告...${NC}"
cat > "$TEST_DIR/README.md" << EOF
# 遥操臂数据流测试报告

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

## 4. 消息数量统计

\`\`\`
$(cat "$TEST_DIR/message_counts.txt")
\`\`\`

## 5. 数据流分析

### 5.1 识别真正的驱动话题

根据以下标准判断：
1. **消息数量最多** → 说明这个话题一直在发送数据
2. **频率最高** → 说明这是高频控制指令
3. **话题名称包含 "follow"** → 通常是实时跟随控制

### 5.2 推荐录制的话题

请查看上述统计，选择：
- 消息数量最多的话题
- 频率最接近实际控制频率的话题
- 确认是机器人驱动实际订阅的话题

## 6. 下一步

1. 确认真正的驱动话题
2. 修改录制脚本，录制正确的话题
3. 重新采集数据用于性能评估

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
echo -e "  - message_counts.txt: 消息数量统计"
echo -e "  - README.md: 完整报告"
echo ""
echo -e "${CYAN}关键问题：${NC}"
echo -e "  1. 哪个话题的消息数量最多？"
echo -e "  2. 哪个话题的频率最高？"
echo -e "  3. 这个话题是否被机器人驱动订阅？"
echo ""