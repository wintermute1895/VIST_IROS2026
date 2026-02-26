#!/bin/bash
# VIST系统诊断脚本
# 检查所有节点、话题和数据流是否正常

set +e  # 允许命令失败，继续执行

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VIST系统诊断${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}错误: ROS2环境未加载${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ROS2环境: $ROS_DISTRO${NC}"
echo ""

# ==========================================
# 1. 检查运行的节点
# ==========================================
echo -e "${BLUE}[1] 运行的ROS2节点${NC}"
echo "-----------------------------------"
NODE_LIST=$(ros2 node list 2>/dev/null)
if [ -z "$NODE_LIST" ]; then
    echo -e "${RED}❌ 没有检测到任何ROS2节点${NC}"
else
    echo "$NODE_LIST"
    NODE_COUNT=$(echo "$NODE_LIST" | wc -l)
    echo ""
    echo -e "${GREEN}总计: $NODE_COUNT 个节点${NC}"
fi
echo ""

# ==========================================
# 2. 检查关键节点是否运行
# ==========================================
echo -e "${BLUE}[2] 关键节点状态检查${NC}"
echo "-----------------------------------"

# 定义关键节点
CRITICAL_NODES=(
    "linkerta_node"           # 遥操臂
    "vist_filter_node"        # 滤波节点
    "teleop_bridge_node"      # 遥操桥接
    "lbot_driver_node"        # 机械臂驱动
)

for node in "${CRITICAL_NODES[@]}"; do
    if echo "$NODE_LIST" | grep -q "$node"; then
        echo -e "${GREEN}✓${NC} $node"
    else
        echo -e "${RED}❌${NC} $node ${RED}(未运行)${NC}"
    fi
done
echo ""

# ==========================================
# 3. 检查活跃的话题
# ==========================================
echo -e "${BLUE}[3] 活跃的话题列表${NC}"
echo "-----------------------------------"
TOPIC_LIST=$(ros2 topic list 2>/dev/null)
if [ -z "$TOPIC_LIST" ]; then
    echo -e "${RED}❌ 没有检测到任何话题${NC}"
else
    echo "$TOPIC_LIST"
    TOPIC_COUNT=$(echo "$TOPIC_LIST" | wc -l)
    echo ""
    echo -e "${GREEN}总计: $TOPIC_COUNT 个话题${NC}"
fi
echo ""

# ==========================================
# 4. 检查关键话题的发布频率
# ==========================================
echo -e "${BLUE}[4] 关键话题发布频率检查${NC}"
echo "-----------------------------------"

# 定义关键话题
CRITICAL_TOPICS=(
    "/left_arm_joint_control"           # 遥操臂输出
    "/filtered_left_joint_control"      # 滤波后输出
    "/robot1/left_arm/joint_follow"     # 机械臂控制指令
    "/robot1/left_arm/joint_states"     # 机械臂状态反馈
)

for topic in "${CRITICAL_TOPICS[@]}"; do
    if echo "$TOPIC_LIST" | grep -q "^${topic}$"; then
        echo -n "检查 $topic ... "
        # 使用timeout限制检查时间为3秒
        RATE=$(timeout 3 ros2 topic hz "$topic" 2>&1 | grep "average rate" | awk '{print $3}')
        if [ -n "$RATE" ]; then
            echo -e "${GREEN}✓ ${RATE} Hz${NC}"
        else
            echo -e "${RED}❌ 无数据${NC}"
        fi
    else
        echo -e "${RED}❌${NC} $topic ${RED}(话题不存在)${NC}"
    fi
done
echo ""

# ==========================================
# 5. 检查话题连接关系
# ==========================================
echo -e "${BLUE}[5] 话题连接关系${NC}"
echo "-----------------------------------"

for topic in "${CRITICAL_TOPICS[@]}"; do
    if echo "$TOPIC_LIST" | grep -q "^${topic}$"; then
        echo ""
        echo -e "${YELLOW}话题: $topic${NC}"

        # 检查发布者
        PUBLISHERS=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count:" | awk '{print $3}')
        echo "  发布者数量: $PUBLISHERS"

        # 检查订阅者
        SUBSCRIBERS=$(ros2 topic info "$topic" 2>/dev/null | grep "Subscription count:" | awk '{print $3}')
        echo "  订阅者数量: $SUBSCRIBERS"

        # 警告：没有发布者或订阅者
        if [ "$PUBLISHERS" = "0" ]; then
            echo -e "  ${RED}⚠️  警告: 没有发布者${NC}"
        fi
        if [ "$SUBSCRIBERS" = "0" ]; then
            echo -e "  ${YELLOW}⚠️  注意: 没有订阅者${NC}"
        fi
    fi
done
echo ""

# ==========================================
# 6. 检查数据流动情况
# ==========================================
echo -e "${BLUE}[6] 数据流动检查${NC}"
echo "-----------------------------------"

# 检查遥操臂 → 滤波节点
echo -n "遥操臂 → 滤波节点: "
if echo "$TOPIC_LIST" | grep -q "/left_arm_joint_control"; then
    RATE=$(timeout 2 ros2 topic hz "/left_arm_joint_control" 2>&1 | grep "average rate" | awk '{print $3}')
    if [ -n "$RATE" ]; then
        echo -e "${GREEN}✓ 数据流动 (${RATE} Hz)${NC}"
    else
        echo -e "${RED}❌ 无数据流动${NC}"
    fi
else
    echo -e "${RED}❌ 话题不存在${NC}"
fi

# 检查滤波节点 → teleop_bridge
echo -n "滤波节点 → teleop_bridge: "
if echo "$TOPIC_LIST" | grep -q "/filtered_left_joint_control"; then
    RATE=$(timeout 2 ros2 topic hz "/filtered_left_joint_control" 2>&1 | grep "average rate" | awk '{print $3}')
    if [ -n "$RATE" ]; then
        echo -e "${GREEN}✓ 数据流动 (${RATE} Hz)${NC}"
    else
        echo -e "${RED}❌ 无数据流动${NC}"
    fi
else
    echo -e "${RED}❌ 话题不存在${NC}"
fi

# 检查teleop_bridge → 机械臂
echo -n "teleop_bridge → 机械臂: "
if echo "$TOPIC_LIST" | grep -q "/robot1/left_arm/joint_follow"; then
    RATE=$(timeout 2 ros2 topic hz "/robot1/left_arm/joint_follow" 2>&1 | grep "average rate" | awk '{print $3}')
    if [ -n "$RATE" ]; then
        echo -e "${GREEN}✓ 数据流动 (${RATE} Hz)${NC}"
    else
        echo -e "${RED}❌ 无数据流动${NC}"
    fi
else
    echo -e "${RED}❌ 话题不存在${NC}"
fi

# 检查机械臂反馈
echo -n "机械臂状态反馈: "
if echo "$TOPIC_LIST" | grep -q "/robot1/left_arm/joint_states"; then
    RATE=$(timeout 2 ros2 topic hz "/robot1/left_arm/joint_states" 2>&1 | grep "average rate" | awk '{print $3}')
    if [ -n "$RATE" ]; then
        echo -e "${GREEN}✓ 数据流动 (${RATE} Hz)${NC}"
    else
        echo -e "${RED}❌ 无数据流动${NC}"
    fi
else
    echo -e "${RED}❌ 话题不存在${NC}"
fi
echo ""

# ==========================================
# 7. 数据流向图
# ==========================================
echo -e "${BLUE}[7] 数据流向图${NC}"
echo "-----------------------------------"
echo ""
echo "  遥操臂 (linkerta_node)"
echo "      ↓"
echo "  /left_arm_joint_control"
echo "      ↓"
echo "  滤波节点 (vist_filter_node)"
echo "      ↓"
echo "  /filtered_left_joint_control"
echo "      ↓"
echo "  遥操桥接 (teleop_bridge_node)"
echo "      ↓"
echo "  /robot1/left_arm/joint_follow"
echo "      ↓"
echo "  机械臂驱动 (lbot_driver_node)"
echo "      ↓"
echo "  /robot1/left_arm/joint_states"
echo ""

# ==========================================
# 8. 诊断建议
# ==========================================
echo -e "${BLUE}[8] 诊断建议${NC}"
echo "-----------------------------------"

# 检查是否所有关键节点都在运行
MISSING_NODES=()
for node in "${CRITICAL_NODES[@]}"; do
    if ! echo "$NODE_LIST" | grep -q "$node"; then
        MISSING_NODES+=("$node")
    fi
done

if [ ${#MISSING_NODES[@]} -gt 0 ]; then
    echo -e "${RED}❌ 发现缺失的关键节点:${NC}"
    for node in "${MISSING_NODES[@]}"; do
        echo "  - $node"
    done
    echo ""
    echo "建议启动顺序："
    echo "  1. ./scripts/start_left_arm_teleop.sh      # 遥操臂"
    echo "  2. ./scripts/startup/start_vist_filter.sh  # 滤波节点"
    echo "  3. ./scripts/start_teleop_bridge.sh        # 遥操桥接"
    echo "  4. 机械臂驱动（通过控制台或脚本启动）"
else
    echo -e "${GREEN}✓ 所有关键节点都在运行${NC}"
    echo ""
    echo "如果机械臂仍然不动，请检查："
    echo "  1. 机械臂是否已使能（控制台确认）"
    echo "  2. 数据是否在流动（查看上面的频率检查）"
    echo "  3. 话题名称是否匹配（检查配置文件）"
    echo "  4. 查看节点日志: ros2 node list 然后 ros2 topic echo [话题名]"
fi
echo ""

# ==========================================
# 9. 快速测试命令
# ==========================================
echo -e "${BLUE}[9] 快速测试命令${NC}"
echo "-----------------------------------"
echo "查看遥操臂输出:"
echo "  ros2 topic echo /left_arm_joint_control"
echo ""
echo "查看滤波后输出:"
echo "  ros2 topic echo /filtered_left_joint_control"
echo ""
echo "查看机械臂控制指令:"
echo "  ros2 topic echo /robot1/left_arm/joint_follow"
echo ""
echo "查看机械臂状态:"
echo "  ros2 topic echo /robot1/left_arm/joint_states"
echo ""
echo "查看节点日志:"
echo "  ros2 node list"
echo "  ros2 topic list"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}诊断完成${NC}"
echo -e "${BLUE}========================================${NC}"