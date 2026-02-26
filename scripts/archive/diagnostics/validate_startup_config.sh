#!/bin/bash
# 启动前配置验证脚本
# Pre-Startup Configuration Validation Script

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

ERRORS=0

print_header "VIST 系统启动前检查"

# 1. 检查 ROS2 环境
print_header "1. ROS2 环境检查"
if [ -z "$ROS_DISTRO" ]; then
    print_error "ROS2 环境未设置"
    print_error "请运行: source /opt/ros/humble/setup.bash"
    ERRORS=$((ERRORS + 1))
else
    print_info "ROS2 版本: $ROS_DISTRO"
fi

# 2. 检查工作空间
print_header "2. 工作空间检查"
VIST_ROOT="/home/ilex/Dev/VIST"
ARM_TELEOP_ROOT="/home/ilex/Dev/VIST/external_sdk/arm_teleop"

if [ ! -d "$VIST_ROOT" ]; then
    print_error "VIST 工作空间不存在: $VIST_ROOT"
    ERRORS=$((ERRORS + 1))
else
    print_info "VIST 工作空间: $VIST_ROOT"
fi

if [ ! -d "$ARM_TELEOP_ROOT" ]; then
    print_error "arm_teleop 工作空间不存在: $ARM_TELEOP_ROOT"
    ERRORS=$((ERRORS + 1))
else
    print_info "arm_teleop 工作空间: $ARM_TELEOP_ROOT"
fi

# 3. 检查配置文件
print_header "3. 配置文件检查"
CONFIG_FILE="$VIST_ROOT/config/system_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "系统配置文件不存在: $CONFIG_FILE"
    ERRORS=$((ERRORS + 1))
else
    print_info "系统配置文件: $CONFIG_FILE"
fi

TELEOP_CONFIG="$ARM_TELEOP_ROOT/src/lbot_teleop/config/teleop_bridge_params.yaml"
if [ ! -f "$TELEOP_CONFIG" ]; then
    print_error "teleop_bridge 配置文件不存在: $TELEOP_CONFIG"
    ERRORS=$((ERRORS + 1))
else
    print_info "teleop_bridge 配置: $TELEOP_CONFIG"
fi

LBOT_CONFIG="$ARM_TELEOP_ROOT/src/lbot_driver/config/lbot_config.yaml"
if [ ! -f "$LBOT_CONFIG" ]; then
    print_error "lbot_driver 配置文件不存在: $LBOT_CONFIG"
    ERRORS=$((ERRORS + 1))
else
    print_info "lbot_driver 配置: $LBOT_CONFIG"
fi

# 4. 检查 Python 节点
print_header "4. Python 节点检查"
FILTER_NODE="$VIST_ROOT/src/nodes/unified_filter_node.py"
if [ ! -f "$FILTER_NODE" ]; then
    print_error "滤波节点不存在: $FILTER_NODE"
    ERRORS=$((ERRORS + 1))
else
    print_info "滤波节点: $FILTER_NODE"
fi

# 5. 检查机械臂连接（可选）
print_header "5. 机械臂连接检查"
ROBOT_IP="192.168.10.21"
if ping -c 1 -W 1 $ROBOT_IP > /dev/null 2>&1; then
    print_info "机械臂可达: $ROBOT_IP"
else
    print_warn "机械臂不可达: $ROBOT_IP (请确保机械臂已开机并连接)"
fi

# 6. 检查话题碰撞
print_header "6. 话题碰撞检查"
if command -v ros2 > /dev/null 2>&1; then
    CRITICAL_TOPICS=(
        "/right_arm_joint_control"
        "/filtered_right_joint_control"
        "/right_arm/joint_follow"
    )

    for topic in "${CRITICAL_TOPICS[@]}"; do
        if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
            PUB_COUNT=$(ros2 topic info "$topic" 2>/dev/null | grep "Publisher count:" | awk '{print $3}')
            if [ -n "$PUB_COUNT" ] && [ "$PUB_COUNT" -gt 1 ]; then
                print_error "话题 $topic 有多个发布者 ($PUB_COUNT)，可能存在碰撞"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
    print_info "话题碰撞检查完成"
else
    print_warn "无法检查话题碰撞（ros2 命令不可用）"
fi

# 7. 检查已运行的节点
print_header "7. 已运行节点检查"
if command -v ros2 > /dev/null 2>&1; then
    RUNNING_NODES=$(ros2 node list 2>/dev/null | wc -l)
    if [ "$RUNNING_NODES" -gt 0 ]; then
        print_warn "检测到 $RUNNING_NODES 个正在运行的 ROS2 节点"
        print_warn "如果要重新启动系统，请先停止所有节点"
        ros2 node list 2>/dev/null | while read node; do
            echo "  - $node"
        done
    else
        print_info "没有检测到正在运行的 ROS2 节点"
    fi
fi

# 总结
print_header "检查总结"
if [ $ERRORS -eq 0 ]; then
    print_info "所有检查通过！系统可以启动"
    exit 0
else
    print_error "发现 $ERRORS 个错误，请修复后再启动"
    exit 1
fi
