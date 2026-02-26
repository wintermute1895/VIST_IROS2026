#!/bin/bash
# 检查话题连接和发布者数量
# Check Topic Connections and Publisher Count

echo "=========================================="
echo "检查数据流和话题碰撞"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查话题是否存在
check_topic() {
    local topic=$1
    if ros2 topic list | grep -q "^${topic}$"; then
        echo -e "${GREEN}✓${NC} 话题存在: ${topic}"
        return 0
    else
        echo -e "${RED}✗${NC} 话题不存在: ${topic}"
        return 1
    fi
}

# 检查发布者数量
check_publishers() {
    local topic=$1
    local expected=$2

    if ! check_topic "$topic"; then
        return 1
    fi

    local pub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count:" | awk '{print $3}')

    if [ -z "$pub_count" ]; then
        echo -e "${YELLOW}⚠${NC}  无法获取发布者数量: ${topic}"
        return 1
    fi

    if [ "$pub_count" -eq "$expected" ]; then
        echo -e "${GREEN}✓${NC} 发布者数量正常: ${topic} (${pub_count}个)"
        return 0
    else
        echo -e "${RED}✗${NC} 发布者数量异常: ${topic} (${pub_count}个，期望${expected}个)"
        echo -e "${RED}  警告: 可能存在话题碰撞！${NC}"
        return 1
    fi
}

# 检查话题频率
check_frequency() {
    local topic=$1
    local min_hz=$2
    local max_hz=$3

    if ! check_topic "$topic"; then
        return 1
    fi

    echo "  测量频率中 (5秒)..."
    local hz_output=$(timeout 5 ros2 topic hz "$topic" 2>/dev/null | grep "average rate:" | awk '{print $3}')

    if [ -z "$hz_output" ]; then
        echo -e "${YELLOW}⚠${NC}  无法测量频率: ${topic}"
        return 1
    fi

    local hz=$(echo "$hz_output" | cut -d'.' -f1)

    if [ "$hz" -ge "$min_hz" ] && [ "$hz" -le "$max_hz" ]; then
        echo -e "${GREEN}✓${NC} 频率正常: ${topic} (${hz} Hz)"
        return 0
    else
        echo -e "${RED}✗${NC} 频率异常: ${topic} (${hz} Hz，期望${min_hz}-${max_hz} Hz)"
        return 1
    fi
}

echo "1. 检查关键话题是否存在"
echo "----------------------------------------"
check_topic "/right_arm_joint_control"
check_topic "/filtered_right_joint_control"
check_topic "/robot1/right_arm/joint_follow"
check_topic "/robot1/right_arm/joint_states"
echo ""

echo "2. 检查发布者数量（防止话题碰撞）"
echo "----------------------------------------"
check_publishers "/right_arm_joint_control" 1
check_publishers "/filtered_right_joint_control" 1
check_publishers "/robot1/right_arm/joint_follow" 1
echo ""

echo "3. 检查数据流连接"
echo "----------------------------------------"

# 检查 linkerta -> unified_filter_node
echo "检查: linkerta → unified_filter_node"
if check_topic "/right_arm_joint_control"; then
    sub_count=$(ros2 topic info "/right_arm_joint_control" 2>/dev/null | grep "Subscription count:" | awk '{print $3}')
    if [ "$sub_count" -ge 1 ]; then
        echo -e "${GREEN}✓${NC} unified_filter_node 正在订阅"
    else
        echo -e "${RED}✗${NC} 没有节点订阅 /right_arm_joint_control"
    fi
fi
echo ""

# 检查 unified_filter_node -> teleop_bridge
echo "检查: unified_filter_node → teleop_bridge"
if check_topic "/filtered_right_joint_control"; then
    sub_count=$(ros2 topic info "/filtered_right_joint_control" 2>/dev/null | grep "Subscription count:" | awk '{print $3}')
    if [ "$sub_count" -ge 1 ]; then
        echo -e "${GREEN}✓${NC} teleop_bridge 正在订阅"
    else
        echo -e "${RED}✗${NC} 没有节点订阅 /filtered_right_joint_control"
    fi
fi
echo ""

# 检查 teleop_bridge -> lbot_driver
echo "检查: teleop_bridge → lbot_driver"
if check_topic "/robot1/right_arm/joint_follow"; then
    sub_count=$(ros2 topic info "/robot1/right_arm/joint_follow" 2>/dev/null | grep "Subscription count:" | awk '{print $3}')
    if [ "$sub_count" -ge 1 ]; then
        echo -e "${GREEN}✓${NC} lbot_driver 正在订阅"
    else
        echo -e "${RED}✗${NC} 没有节点订阅 /robot1/right_arm/joint_follow"
    fi
fi
echo ""

echo "4. 检查话题频率（可选，需要5秒）"
echo "----------------------------------------"
read -p "是否检查频率？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    check_frequency "/right_arm_joint_control" 70 90
    check_frequency "/filtered_right_joint_control" 70 90
    check_frequency "/robot1/right_arm/joint_follow" 70 90
fi
echo ""

echo "=========================================="
echo "检查完成"
echo "=========================================="
echo ""
echo "预期的数据流:"
echo "  linkerta (80Hz)"
echo "    ↓ /right_arm_joint_control"
echo "  unified_filter_node (80Hz)"
echo "    ↓ /filtered_right_joint_control"
echo "  teleop_bridge (80Hz)"
echo "    ↓ /robot1/right_arm/joint_follow"
echo "  lbot_driver (50Hz)"
echo "    ↓ 硬件"
echo ""
echo "关键安全检查:"
echo "  - 每个话题只有1个发布者 ✓"
echo "  - 频率在70-90 Hz范围内 ✓"
echo "  - 数据流连接完整 ✓"