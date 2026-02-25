#!/bin/bash
# 话题冲突检测脚本
# 用于检测是否有多个节点同时发布到同一个话题

echo "========================================="
echo "话题冲突检测工具"
echo "========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查关键话题
TOPICS=(
    "/robot1/left_arm/joint_follow"
    "/robot1/right_arm/joint_follow"
    "/left_arm_joint_control"
    "/right_arm_joint_control"
    "/vision_left_joint_control"
    "/vision_right_joint_control"
)

echo "1. 检查ROS2节点"
echo "-------------------"
NODES=$(ros2 node list 2>/dev/null)
if [ -z "$NODES" ]; then
    echo -e "${YELLOW}⚠️  没有运行的ROS2节点${NC}"
else
    echo "$NODES"

    # 检查关键节点
    echo ""
    echo "关键节点检查:"
    echo "$NODES" | grep -q "teleop_bridge" && echo -e "${GREEN}✓ teleop_bridge_node 运行中${NC}" || echo "  teleop_bridge_node 未运行"
    echo "$NODES" | grep -q "high_freq_resampler" && echo -e "${RED}⚠️  high_freq_resampler_node 运行中${NC}" || echo "  high_freq_resampler_node 未运行"
    echo "$NODES" | grep -q "linkerta" && echo -e "${GREEN}✓ linkerta_node 运行中${NC}" || echo "  linkerta_node 未运行"
    echo "$NODES" | grep -q "lbot_driver" && echo -e "${GREEN}✓ lbot_driver 运行中${NC}" || echo "  lbot_driver 未运行"
fi

echo ""
echo "2. 检查话题发布者数量"
echo "-------------------"

for topic in "${TOPICS[@]}"; do
    # 检查话题是否存在
    if ros2 topic info "$topic" &>/dev/null; then
        # 获取发布者数量
        pub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count" | awk '{print $3}')
        sub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Subscription count" | awk '{print $3}')

        if [ "$pub_count" -gt 1 ]; then
            echo -e "${RED}⚠️  $topic${NC}"
            echo -e "   ${RED}发布者: $pub_count (危险！多个发布者)${NC}"
            echo -e "   订阅者: $sub_count"

            # 显示发布者节点
            echo "   发布者节点:"
            ros2 topic info "$topic" -v 2>/dev/null | grep -A 10 "Publishers:" | grep "Node name:" | sed 's/^/     /'
        elif [ "$pub_count" -eq 1 ]; then
            echo -e "${GREEN}✓ $topic${NC}"
            echo "   发布者: $pub_count"
            echo "   订阅者: $sub_count"
        else
            echo -e "${YELLOW}○ $topic${NC}"
            echo "   发布者: 0 (无发布者)"
            echo "   订阅者: $sub_count"
        fi
    else
        echo -e "  $topic (不存在)"
    fi
    echo ""
done

echo "3. 检查进程"
echo "-------------------"
echo "teleop_bridge 进程:"
ps aux | grep "teleop_bridge_node" | grep -v grep || echo "  无"
echo ""
echo "high_freq_resampler 进程:"
ps aux | grep "high_freq_resampler_node" | grep -v grep || echo "  无"
echo ""

echo "4. 检查话题频率（如果有发布者）"
echo "-------------------"
for topic in "${TOPICS[@]}"; do
    if ros2 topic info "$topic" &>/dev/null; then
        pub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count" | awk '{print $3}')
        if [ "$pub_count" -gt 0 ]; then
            echo "检查 $topic 频率（10秒）..."
            timeout 10s ros2 topic hz "$topic" 2>/dev/null | grep "average rate" | tail -1
        fi
    fi
done

echo ""
echo "========================================="
echo "检测完成"
echo "========================================="
echo ""
echo "⚠️  如果发现多个发布者，请执行以下命令清理："
echo "   pkill -f teleop_bridge_node"
echo "   pkill -f high_freq_resampler_node"
echo ""