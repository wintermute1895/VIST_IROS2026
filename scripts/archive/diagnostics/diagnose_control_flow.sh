#!/bin/bash
# 安全测试脚本：完整控制流程诊断（不连接真机）
# 用于检测话题冲突和频率问题

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}完整控制流程诊断（安全模式）${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  注意：此脚本不会连接真实机械臂${NC}"
echo -e "${YELLOW}⚠️  使用mock节点代替真实驱动${NC}"
echo ""

# 工作目录
VIST_ROOT="/home/ilex/Dev/VIST"
ARM_TELEOP_ROOT="$VIST_ROOT/external_sdk/arm_teleop"

cd "$VIST_ROOT"

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}清理所有节点...${NC}"
    pkill -f "linkerta_node" || true
    pkill -f "teleop_bridge_node" || true
    pkill -f "high_freq_resampler_node" || true
    pkill -f "mock_lbot_driver" || true
    sleep 2
    echo -e "${GREEN}清理完成${NC}"
}

# 注册清理函数
trap cleanup EXIT INT TERM

# 步骤1: 清理现有进程
echo -e "${BLUE}步骤1: 清理现有ROS2进程${NC}"
echo "-------------------"
cleanup

# 步骤2: 检查初始状态
echo ""
echo -e "${BLUE}步骤2: 检查初始状态${NC}"
echo "-------------------"
echo "运行的ROS2节点:"
ros2 node list 2>/dev/null || echo "  无"
echo ""

# 步骤3: 启动mock驱动（代替真实lbot_driver）
echo -e "${BLUE}步骤3: 启动mock驱动（代替真实硬件）${NC}"
echo "-------------------"
python3 "$VIST_ROOT/scripts/mock_lbot_driver.py" > /tmp/mock_driver.log 2>&1 &
MOCK_DRIVER_PID=$!
echo -e "${GREEN}✓ mock_lbot_driver 已启动 (PID: $MOCK_DRIVER_PID)${NC}"
sleep 2

# 步骤4: 启动linkerta（外骨骼）
echo ""
echo -e "${BLUE}步骤4: 启动linkerta（外骨骼）${NC}"
echo "-------------------"
cd "$ARM_TELEOP_ROOT"
source install/setup.bash
ros2 run linkerta linkerta_node > /tmp/linkerta.log 2>&1 &
LINKERTA_PID=$!
echo -e "${GREEN}✓ linkerta_node 已启动 (PID: $LINKERTA_PID)${NC}"
sleep 3

# 步骤5: 检查linkerta发布的话题
echo ""
echo -e "${BLUE}步骤5: 检查linkerta发布的话题${NC}"
echo "-------------------"
echo "检查 /left_arm_joint_control:"
ros2 topic info /left_arm_joint_control 2>/dev/null || echo "  话题不存在"
echo ""
echo "检查 /right_arm_joint_control:"
ros2 topic info /right_arm_joint_control 2>/dev/null || echo "  话题不存在"
echo ""

# 步骤6: 启动teleop_bridge
echo -e "${BLUE}步骤6: 启动teleop_bridge${NC}"
echo "-------------------"
ros2 run lbot_teleop teleop_bridge_node \
    --ros-args \
    --params-file "$ARM_TELEOP_ROOT/src/lbot_teleop/config/teleop_bridge_params.yaml" \
    -p slave_namespaces:="['robot1']" \
    > /tmp/teleop_bridge.log 2>&1 &
BRIDGE_PID=$!
echo -e "${GREEN}✓ teleop_bridge_node 已启动 (PID: $BRIDGE_PID)${NC}"
sleep 3

# 步骤7: 检查关键话题的发布者数量
echo ""
echo -e "${BLUE}步骤7: 检查话题发布者数量（关键检查）${NC}"
echo "-------------------"

check_topic() {
    local topic=$1
    if ros2 topic info "$topic" &>/dev/null; then
        local pub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count" | awk '{print $3}')
        local sub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Subscription count" | awk '{print $3}')

        echo "话题: $topic"
        if [ "$pub_count" -gt 1 ]; then
            echo -e "  ${RED}⚠️  发布者数量: $pub_count (危险！多个发布者)${NC}"
            echo "  订阅者数量: $sub_count"
            echo "  发布者节点:"
            ros2 topic info "$topic" -v 2>/dev/null | grep -A 10 "Publishers:" | grep "Node name:" | sed 's/^/    /'
        elif [ "$pub_count" -eq 1 ]; then
            echo -e "  ${GREEN}✓ 发布者数量: $pub_count (正常)${NC}"
            echo "  订阅者数量: $sub_count"
        else
            echo -e "  ${YELLOW}○ 发布者数量: 0 (无发布者)${NC}"
            echo "  订阅者数量: $sub_count"
        fi
        echo ""
    else
        echo "话题: $topic (不存在)"
        echo ""
    fi
}

check_topic "/left_arm_joint_control"
check_topic "/right_arm_joint_control"
check_topic "/robot1/left_arm/joint_follow"
check_topic "/robot1/right_arm/joint_follow"

# 步骤8: 测量话题频率
echo -e "${BLUE}步骤8: 测量话题频率（10秒）${NC}"
echo "-------------------"

measure_frequency() {
    local topic=$1
    local duration=10

    if ros2 topic info "$topic" &>/dev/null; then
        local pub_count=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count" | awk '{print $3}')
        if [ "$pub_count" -gt 0 ]; then
            echo "测量 $topic 频率..."
            timeout ${duration}s ros2 topic hz "$topic" 2>/dev/null | grep "average rate" | tail -1
        else
            echo "$topic: 无发布者"
        fi
    else
        echo "$topic: 话题不存在"
    fi
}

measure_frequency "/left_arm_joint_control"
measure_frequency "/right_arm_joint_control"
measure_frequency "/robot1/left_arm/joint_follow"
measure_frequency "/robot1/right_arm/joint_follow"

# 步骤9: 列出所有运行的节点
echo ""
echo -e "${BLUE}步骤9: 当前运行的ROS2节点${NC}"
echo "-------------------"
ros2 node list 2>/dev/null

# 步骤10: 检查进程
echo ""
echo -e "${BLUE}步骤10: 检查相关进程${NC}"
echo "-------------------"
echo "linkerta 进程:"
ps aux | grep "linkerta_node" | grep -v grep || echo "  无"
echo ""
echo "teleop_bridge 进程:"
ps aux | grep "teleop_bridge_node" | grep -v grep || echo "  无"
echo ""
echo "high_freq_resampler 进程:"
ps aux | grep "high_freq_resampler_node" | grep -v grep || echo "  无"
echo ""

# 步骤11: 等待用户观察
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}诊断完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "节点将继续运行，你可以："
echo "1. 在另一个终端运行: ./scripts/check_topic_collision.sh"
echo "2. 观察日志: tail -f /tmp/linkerta.log"
echo "3. 观察日志: tail -f /tmp/teleop_bridge.log"
echo "4. 观察日志: tail -f /tmp/mock_driver.log"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有节点${NC}"
echo ""

# 保持运行
wait