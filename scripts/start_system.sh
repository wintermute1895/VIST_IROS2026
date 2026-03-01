#!/bin/bash
# VIST 遥操作系统 - 完整启动脚本
# 自动化所有准备步骤和系统启动

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VIST 遥操作系统 - 完整启动${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================================================
# 1. 配置 CAN 接口
# ============================================================================
echo -e "${YELLOW}步骤 1/4: 配置 CAN 接口${NC}"
echo "需要 sudo 权限来配置 CAN 接口..."

# CAN0 - 灵巧手
if ip link show can0 &>/dev/null; then
    sudo ip link set can0 down 2>/dev/null || true
    sudo ip link set can0 up type can bitrate 1000000
    sudo ip link set can0 txqueuelen 1000
    echo -e "${GREEN}✓ CAN0 已配置 (灵巧手)${NC}"
else
    echo -e "${YELLOW}⚠️  CAN0 不存在，跳过${NC}"
fi

# CAN1 - 外骨骼
if ip link show can1 &>/dev/null; then
    sudo ip link set can1 down 2>/dev/null || true
    sudo ip link set can1 up type can bitrate 1000000
    sudo ip link set can1 txqueuelen 1000
    echo -e "${GREEN}✓ CAN1 已配置 (外骨骼)${NC}"
else
    echo -e "${YELLOW}⚠️  CAN1 不存在，跳过${NC}"
fi

echo ""

# ============================================================================
# 2. 检查网络连接
# ============================================================================
echo -e "${YELLOW}步骤 2/4: 检查机械臂网络连接${NC}"
if ping -c 1 -W 1 192.168.10.21 &>/dev/null; then
    echo -e "${GREEN}✓ 机械臂网络连接正常 (192.168.10.21)${NC}"
else
    echo -e "${RED}❌ 无法连接到机械臂 (192.168.10.21)${NC}"
    echo "请检查："
    echo "  1. 机械臂是否开机"
    echo "  2. 网络连接是否正常"
    echo "  3. IP 地址是否正确"
    read -p "是否继续启动？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# ============================================================================
# 3. 加载 ROS2 环境（级联顺序：系统 → 外部 → 主）
# ============================================================================
echo -e "${YELLOW}步骤 3/4: 级联加载 ROS2 环境${NC}"

# 第一层：加载 ROS2 基础环境
echo -e "${BLUE}[1/3] 加载系统 ROS2 环境...${NC}"
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo -e "${GREEN}✓ ROS2 Humble 环境已加载${NC}"
else
    echo -e "${RED}❌ 找不到 ROS2 Humble${NC}"
    exit 1
fi

# 第二层：加载外部工作空间（底层硬件驱动）
echo -e "${BLUE}[2/3] 加载外部工作空间 (arm_teleop)...${NC}"
EXTERNAL_WS="/home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop/install/setup.bash"
if [ -f "$EXTERNAL_WS" ]; then
    source "$EXTERNAL_WS"
    echo -e "${GREEN}✓ 外部工作空间已加载 (lbot_driver, lbot_teleop, linkerta)${NC}"
else
    echo -e "${RED}❌ 找不到外部工作空间: $EXTERNAL_WS${NC}"
    echo -e "${YELLOW}提示: 请先编译外部工作空间${NC}"
    echo "  cd ~/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop"
    echo "  colcon build --symlink-install"
    exit 1
fi

# 第三层：加载主工作空间（上层应用节点）
echo -e "${BLUE}[3/3] 加载主工作空间 (ros2_ws)...${NC}"
MAIN_WS="/home/ilex/Dev/VIST/ros2_ws/install/setup.bash"
if [ -f "$MAIN_WS" ]; then
    source "$MAIN_WS"
    echo -e "${GREEN}✓ 主工作空间已加载 (bringup, nodes)${NC}"
else
    echo -e "${RED}❌ 找不到主工作空间: $MAIN_WS${NC}"
    echo -e "${YELLOW}提示: 请先编译主工作空间${NC}"
    echo "  cd ~/Dev/VIST/ros2_ws"
    echo "  colcon build --symlink-install"
    exit 1
fi

# 验证环境变量
echo -e "${BLUE}验证环境变量...${NC}"
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}❌ ROS_DISTRO 未设置${NC}"
    exit 1
fi
echo -e "${GREEN}✓ ROS_DISTRO=$ROS_DISTRO${NC}"
echo -e "${GREEN}✓ 环境变量级联加载完成${NC}"

echo ""

# ============================================================================
# 4. 启动系统
# ============================================================================
echo -e "${YELLOW}步骤 4/4: 启动遥操作系统${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}准备启动 VIST 遥操作系统${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "系统将启动以下模块："
echo "  • 相机 (RealSense D435i)"
echo "  • 外骨骼 (Linkerta)"
echo "  • VIST 滤波器"
echo "  • 灵巧手 (Linker Hand L10)"
echo "  • 机械臂驱动"
echo "  • 遥操作桥接"
echo ""
echo "按 Ctrl+C 可以停止系统"
echo ""

sleep 2

# 启动系统
ros2 launch bringup teleop_system.launch.py