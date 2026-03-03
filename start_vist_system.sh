#!/bin/bash
# VIST 完整系统启动脚本
# 按正确顺序启动所有必需的节点

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  VIST 系统启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 1. Source ROS2 环境
echo -e "${YELLOW}[1/6] 加载 ROS2 环境...${NC}"
if [ -z "$ROS_DISTRO" ]; then
    source /opt/ros/humble/setup.bash
fi
echo -e "${GREEN}✓ ROS_DISTRO = $ROS_DISTRO${NC}"

# 2. Source 工作空间
echo -e "${YELLOW}[2/6] 加载工作空间...${NC}"
if [ -f "${PROJECT_ROOT}/install/setup.bash" ]; then
    source "${PROJECT_ROOT}/install/setup.bash"
    echo -e "${GREEN}✓ 工作空间已加载${NC}"
else
    echo -e "${RED}✗ 工作空间未构建${NC}"
    echo -e "${YELLOW}正在构建工作空间...${NC}"
    colcon build --packages-select lbot_arm_interfaces lbot_driver lbot_teleop
    source "${PROJECT_ROOT}/install/setup.bash"
    echo -e "${GREEN}✓ 工作空间构建完成${NC}"
fi

# 3. 验证消息接口
echo -e "${YELLOW}[3/6] 验证消息接口...${NC}"
if ros2 interface show lbot_arm_interfaces/msg/FollowJoint &>/dev/null; then
    echo -e "${GREEN}✓ 消息接口可用${NC}"
else
    echo -e "${RED}✗ 消息接口不可用${NC}"
    exit 1
fi

# 4. 检查机械臂连接
echo -e "${YELLOW}[4/6] 检查机械臂连接...${NC}"
ARM_IP="192.168.10.21"
if ping -c 1 -W 1 $ARM_IP &>/dev/null; then
    echo -e "${GREEN}✓ 机械臂可达 ($ARM_IP)${NC}"
else
    echo -e "${YELLOW}⚠ 机械臂不可达 ($ARM_IP)${NC}"
    echo -e "${YELLOW}  继续启动（仿真模式）${NC}"
fi

# 5. 启动节点（使用 tmux 多窗口）
echo -e "${YELLOW}[5/6] 启动 ROS2 节点...${NC}"

# 检查是否安装了 tmux
if ! command -v tmux &>/dev/null; then
    echo -e "${RED}✗ tmux 未安装${NC}"
    echo -e "${YELLOW}安装方法: sudo apt install tmux${NC}"
    echo ""
    echo -e "${YELLOW}手动启动方法:${NC}"
    echo ""
    echo -e "${BLUE}终端 1 - lbot_driver:${NC}"
    echo "  source /opt/ros/humble/setup.bash"
    echo "  source ${PROJECT_ROOT}/install/setup.bash"
    echo "  ros2 run lbot_driver lbot_driver"
    echo ""
    echo -e "${BLUE}终端 2 - teleop_bridge:${NC}"
    echo "  source /opt/ros/humble/setup.bash"
    echo "  source ${PROJECT_ROOT}/install/setup.bash"
    echo "  ros2 run lbot_teleop teleop_bridge_node"
    echo ""
    echo -e "${BLUE}终端 3 - VIST filter:${NC}"
    echo "  source /opt/ros/humble/setup.bash"
    echo "  source ${PROJECT_ROOT}/install/setup.bash"
    echo "  ros2 run vist_filter vist_filter_node --ros-args --params-file config/baseline_filters_config.yaml"
    exit 1
fi

# 创建 tmux 会话
SESSION_NAME="vist_system"

# 如果会话已存在，先关闭
tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME

# 创建新会话
tmux new-session -d -s $SESSION_NAME -n "lbot_driver"

# 窗口 1: lbot_driver
tmux send-keys -t $SESSION_NAME:0 "cd ${PROJECT_ROOT}" C-m
tmux send-keys -t $SESSION_NAME:0 "source /opt/ros/humble/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:0 "source ${PROJECT_ROOT}/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:0 "echo '启动 lbot_driver...'" C-m
tmux send-keys -t $SESSION_NAME:0 "ros2 run lbot_driver lbot_driver" C-m

# 等待 lbot_driver 启动
sleep 2

# 窗口 2: teleop_bridge
tmux new-window -t $SESSION_NAME -n "teleop_bridge"
tmux send-keys -t $SESSION_NAME:1 "cd ${PROJECT_ROOT}" C-m
tmux send-keys -t $SESSION_NAME:1 "source /opt/ros/humble/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:1 "source ${PROJECT_ROOT}/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:1 "echo '启动 teleop_bridge...'" C-m
tmux send-keys -t $SESSION_NAME:1 "ros2 run lbot_teleop teleop_bridge_node" C-m

# 等待 teleop_bridge 启动
sleep 2

# 窗口 3: VIST filter
tmux new-window -t $SESSION_NAME -n "vist_filter"
tmux send-keys -t $SESSION_NAME:2 "cd ${PROJECT_ROOT}" C-m
tmux send-keys -t $SESSION_NAME:2 "source /opt/ros/humble/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:2 "source ${PROJECT_ROOT}/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:2 "echo '启动 VIST filter...'" C-m
tmux send-keys -t $SESSION_NAME:2 "ros2 run vist_filter vist_filter_node --ros-args --params-file config/baseline_filters_config.yaml" C-m

# 窗口 4: 监控
tmux new-window -t $SESSION_NAME -n "monitor"
tmux send-keys -t $SESSION_NAME:3 "cd ${PROJECT_ROOT}" C-m
tmux send-keys -t $SESSION_NAME:3 "source /opt/ros/humble/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:3 "source ${PROJECT_ROOT}/install/setup.bash" C-m
tmux send-keys -t $SESSION_NAME:3 "echo '等待节点启动...'" C-m
tmux send-keys -t $SESSION_NAME:3 "sleep 3" C-m
tmux send-keys -t $SESSION_NAME:3 "echo ''" C-m
tmux send-keys -t $SESSION_NAME:3 "echo '=== ROS2 节点列表 ==='" C-m
tmux send-keys -t $SESSION_NAME:3 "ros2 node list" C-m
tmux send-keys -t $SESSION_NAME:3 "echo ''" C-m
tmux send-keys -t $SESSION_NAME:3 "echo '=== joint_follow 话题 ==='" C-m
tmux send-keys -t $SESSION_NAME:3 "ros2 topic list | grep joint_follow" C-m
tmux send-keys -t $SESSION_NAME:3 "echo ''" C-m
tmux send-keys -t $SESSION_NAME:3 "echo '=== 监控 joint_follow 频率 ==='" C-m
tmux send-keys -t $SESSION_NAME:3 "ros2 topic hz /robot1/left_arm/joint_follow" C-m

echo -e "${GREEN}✓ 所有节点已在 tmux 会话中启动${NC}"
echo ""

# 6. 显示使用说明
echo -e "${YELLOW}[6/6] 使用说明${NC}"
echo ""
echo -e "${BLUE}tmux 会话管理:${NC}"
echo "  查看所有窗口:  ${GREEN}tmux attach -t $SESSION_NAME${NC}"
echo "  切换窗口:      ${GREEN}Ctrl+b 然后按数字键 (0-3)${NC}"
echo "  退出会话:      ${GREEN}Ctrl+b 然后按 d${NC}"
echo "  关闭会话:      ${GREEN}tmux kill-session -t $SESSION_NAME${NC}"
echo ""
echo -e "${BLUE}窗口说明:${NC}"
echo "  窗口 0: lbot_driver      - 机械臂驱动"
echo "  窗口 1: teleop_bridge    - 遥操作桥接"
echo "  窗口 2: vist_filter      - VIST 滤波器"
echo "  窗口 3: monitor          - 系统监控"
echo ""
echo -e "${BLUE}验证系统状态:${NC}"
echo "  检查节点:      ${GREEN}ros2 node list${NC}"
echo "  检查话题:      ${GREEN}ros2 topic list | grep joint_follow${NC}"
echo "  监控频率:      ${GREEN}ros2 topic hz /robot1/left_arm/joint_follow${NC}"
echo ""
echo -e "${GREEN}✓ VIST 系统启动完成！${NC}"
echo ""
echo -e "${YELLOW}按 Enter 进入 tmux 会话查看节点状态...${NC}"
read

# 进入 tmux 会话
tmux attach -t $SESSION_NAME
