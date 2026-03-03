#!/bin/bash
# 全面诊断 joint_follow 话题通信问题

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  joint_follow 话题诊断工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 检查当前运行的 ROS2 节点
echo -e "${YELLOW}[1/8] 检查运行中的 ROS2 节点...${NC}"
NODES=$(ros2 node list 2>&1)
if [ -z "$NODES" ] || [ "$NODES" == "/rqt_gui_py_node_"* ]; then
    echo -e "${RED}✗ 没有相关节点在运行（只有 rqt_gui）${NC}"
    echo -e "${YELLOW}  提示: 需要先启动 lbot_driver 和 teleop_bridge${NC}"
else
    echo -e "${GREEN}✓ 运行中的节点:${NC}"
    echo "$NODES" | sed 's/^/  /'
fi
echo ""

# 2. 检查当前话题列表
echo -e "${YELLOW}[2/8] 检查当前话题列表...${NC}"
TOPICS=$(ros2 topic list 2>&1 | grep -v "parameter_events\|rosout" || true)
if [ -z "$TOPICS" ]; then
    echo -e "${RED}✗ 没有找到相关话题${NC}"
else
    echo -e "${GREEN}✓ 当前话题:${NC}"
    echo "$TOPICS" | sed 's/^/  /'
fi
echo ""

# 3. 检查 joint_follow 相关话题
echo -e "${YELLOW}[3/8] 搜索 joint_follow 相关话题...${NC}"
JOINT_FOLLOW_TOPICS=$(ros2 topic list 2>&1 | grep "joint_follow" || true)
if [ -z "$JOINT_FOLLOW_TOPICS" ]; then
    echo -e "${RED}✗ 没有找到 joint_follow 话题${NC}"
    echo -e "${YELLOW}  原因: lbot_driver 或 teleop_bridge 未启动${NC}"
else
    echo -e "${GREEN}✓ 找到 joint_follow 话题:${NC}"
    echo "$JOINT_FOLLOW_TOPICS" | sed 's/^/  /'

    # 检查话题详细信息
    for topic in $JOINT_FOLLOW_TOPICS; do
        echo ""
        echo -e "${BLUE}  话题: $topic${NC}"
        ros2 topic info $topic 2>&1 | sed 's/^/    /'
    done
fi
echo ""

# 4. 检查消息接口是否可用
echo -e "${YELLOW}[4/8] 检查消息接口...${NC}"
if ros2 interface show lbot_arm_interfaces/msg/FollowJoint &>/dev/null; then
    echo -e "${GREEN}✓ lbot_arm_interfaces/msg/FollowJoint 可用${NC}"
    ros2 interface show lbot_arm_interfaces/msg/FollowJoint | sed 's/^/  /'
else
    echo -e "${RED}✗ lbot_arm_interfaces/msg/FollowJoint 不可用${NC}"
    echo -e "${YELLOW}  修复: source /home/ilex/Dev/VIST/install/setup.bash${NC}"
fi
echo ""

# 5. 检查 lbot_driver 进程
echo -e "${YELLOW}[5/8] 检查 lbot_driver 进程...${NC}"
LBOT_PROCESS=$(ps aux | grep lbot_driver | grep -v grep || true)
if [ -z "$LBOT_PROCESS" ]; then
    echo -e "${RED}✗ lbot_driver 未运行${NC}"
else
    echo -e "${GREEN}✓ lbot_driver 正在运行:${NC}"
    echo "$LBOT_PROCESS" | sed 's/^/  /'
fi
echo ""

# 6. 检查 teleop_bridge 进程
echo -e "${YELLOW}[6/8] 检查 teleop_bridge 进程...${NC}"
TELEOP_PROCESS=$(ps aux | grep teleop_bridge | grep -v grep || true)
if [ -z "$TELEOP_PROCESS" ]; then
    echo -e "${RED}✗ teleop_bridge 未运行${NC}"
else
    echo -e "${GREEN}✓ teleop_bridge 正在运行:${NC}"
    echo "$TELEOP_PROCESS" | sed 's/^/  /'
fi
echo ""

# 7. 检查 ROS_DOMAIN_ID
echo -e "${YELLOW}[7/8] 检查 ROS_DOMAIN_ID...${NC}"
if [ -z "$ROS_DOMAIN_ID" ]; then
    echo -e "${YELLOW}⚠ ROS_DOMAIN_ID 未设置（使用默认值 0）${NC}"
else
    echo -e "${GREEN}✓ ROS_DOMAIN_ID = $ROS_DOMAIN_ID${NC}"
fi
echo ""

# 8. 检查 DDS 配置
echo -e "${YELLOW}[8/8] 检查 DDS 配置...${NC}"
if [ -z "$RMW_IMPLEMENTATION" ]; then
    echo -e "${YELLOW}⚠ RMW_IMPLEMENTATION 未设置（使用默认）${NC}"
else
    echo -e "${GREEN}✓ RMW_IMPLEMENTATION = $RMW_IMPLEMENTATION${NC}"
fi
echo ""

# 总结
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  诊断总结${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 判断问题类型
if [ -z "$JOINT_FOLLOW_TOPICS" ]; then
    echo -e "${RED}问题类型: 话题不存在${NC}"
    echo ""
    echo -e "${YELLOW}可能原因:${NC}"
    echo "  1. lbot_driver 未启动"
    echo "  2. teleop_bridge 未启动"
    echo "  3. 节点启动失败"
    echo ""
    echo -e "${YELLOW}解决方案:${NC}"
    echo "  1. 启动 lbot_driver:"
    echo "     ${GREEN}ros2 run lbot_driver lbot_driver${NC}"
    echo ""
    echo "  2. 启动 teleop_bridge:"
    echo "     ${GREEN}ros2 run lbot_teleop teleop_bridge_node${NC}"
    echo ""
    echo "  3. 检查节点日志:"
    echo "     ${GREEN}ros2 run lbot_driver lbot_driver --ros-args --log-level debug${NC}"
else
    echo -e "${GREEN}话题存在，检查通信质量...${NC}"
    echo ""
    echo -e "${YELLOW}建议操作:${NC}"
    echo "  1. 监控话题频率:"
    echo "     ${GREEN}ros2 topic hz /robot1/left_arm/joint_follow${NC}"
    echo ""
    echo "  2. 查看话题内容:"
    echo "     ${GREEN}ros2 topic echo /robot1/left_arm/joint_follow${NC}"
    echo ""
    echo "  3. 检查话题延迟:"
    echo "     ${GREEN}ros2 topic delay /robot1/left_arm/joint_follow${NC}"
fi
echo ""
