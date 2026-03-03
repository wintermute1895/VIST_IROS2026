#!/bin/bash
# 修复 joint_follow 话题通信问题
# 问题：can not get message class for type "lbot_arm_interfaces/msg/FollowJoint"
# 原因：ROS2 环境变量未正确设置，消息接口包未被加载

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  修复 joint_follow 通信问题${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Step 1: 检查 ROS2 基础环境
echo -e "${YELLOW}[1/5] 检查 ROS2 基础环境...${NC}"
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}✗ ROS2 环境未设置${NC}"
    echo -e "${YELLOW}修复方法: source /opt/ros/humble/setup.bash${NC}"
    exit 1
else
    echo -e "${GREEN}✓ ROS_DISTRO = $ROS_DISTRO${NC}"
fi

# Step 2: 检查工作空间是否构建
echo -e "${YELLOW}[2/5] 检查工作空间构建状态...${NC}"
if [ ! -f "${PROJECT_ROOT}/install/setup.bash" ]; then
    echo -e "${RED}✗ 工作空间未构建${NC}"
    echo -e "${YELLOW}开始构建工作空间...${NC}"

    # 构建消息接口包
    cd "${PROJECT_ROOT}"
    colcon build --packages-select lbot_arm_interfaces --symlink-install

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 工作空间构建成功${NC}"
    else
        echo -e "${RED}✗ 工作空间构建失败${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ 工作空间已构建${NC}"
fi

# Step 3: Source 工作空间
echo -e "${YELLOW}[3/5] 加载工作空间环境...${NC}"
source "${PROJECT_ROOT}/install/setup.bash"
echo -e "${GREEN}✓ 工作空间已加载${NC}"

# Step 4: 验证环境变量
echo -e "${YELLOW}[4/5] 验证环境变量...${NC}"
echo -e "  AMENT_PREFIX_PATH:"
echo "$AMENT_PREFIX_PATH" | tr ':' '\n' | sed 's/^/    /'

if echo "$AMENT_PREFIX_PATH" | grep -q "${PROJECT_ROOT}/install"; then
    echo -e "${GREEN}✓ 工作空间已在 AMENT_PREFIX_PATH 中${NC}"
else
    echo -e "${RED}✗ 工作空间不在 AMENT_PREFIX_PATH 中${NC}"
    exit 1
fi

# Step 5: 验证消息接口
echo -e "${YELLOW}[5/5] 验证消息接口...${NC}"
if ros2 interface show lbot_arm_interfaces/msg/FollowJoint &>/dev/null; then
    echo -e "${GREEN}✓ lbot_arm_interfaces/msg/FollowJoint 可用${NC}"
    echo ""
    echo -e "${BLUE}消息定义:${NC}"
    ros2 interface show lbot_arm_interfaces/msg/FollowJoint | head -20
else
    echo -e "${RED}✗ lbot_arm_interfaces/msg/FollowJoint 不可用${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 所有检查通过！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}下一步操作:${NC}"
echo -e "1. 在当前终端启动 VIST 滤波节点:"
echo -e "   ${GREEN}ros2 run vist_filter vist_filter_node --ros-args --params-file config/baseline_filters_config.yaml${NC}"
echo ""
echo -e "2. 或者使用修复后的启动脚本:"
echo -e "   ${GREEN}./scripts/archive_unsafe/start_vist_filter.sh${NC}"
echo ""
echo -e "${YELLOW}注意: 每次打开新终端都需要 source 工作空间:${NC}"
echo -e "   ${GREEN}source /opt/ros/humble/setup.bash${NC}"
echo -e "   ${GREEN}source ${PROJECT_ROOT}/install/setup.bash${NC}"
echo ""
