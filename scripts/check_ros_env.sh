#!/bin/bash
# 检查当前终端的ROS2环境和工作空间

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ROS2环境检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查ROS2环境
echo -e "${YELLOW}[1] ROS2基础环境${NC}"
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}❌ ROS2环境未加载${NC}"
    echo "请运行: source /opt/ros/humble/setup.bash"
else
    echo -e "${GREEN}✓ ROS_DISTRO: $ROS_DISTRO${NC}"
fi
echo ""

# 检查AMENT_PREFIX_PATH
echo -e "${YELLOW}[2] 已加载的工作空间${NC}"
if [ -z "$AMENT_PREFIX_PATH" ]; then
    echo -e "${RED}❌ 没有加载任何工作空间${NC}"
else
    echo "AMENT_PREFIX_PATH:"
    echo "$AMENT_PREFIX_PATH" | tr ':' '\n' | while read -r path; do
        if [[ "$path" == *"arm_teleop"* ]]; then
            echo -e "  ${GREEN}✓ $path (arm_teleop)${NC}"
        elif [[ "$path" == *"VIST"* ]]; then
            echo -e "  ${GREEN}✓ $path (VIST)${NC}"
        else
            echo "  - $path"
        fi
    done
fi
echo ""

# 检查可用的ROS2包
echo -e "${YELLOW}[3] 关键ROS2包${NC}"
PACKAGES=("linkerta" "lbot_teleop" "lbot_driver")
for pkg in "${PACKAGES[@]}"; do
    if ros2 pkg list 2>/dev/null | grep -q "^${pkg}$"; then
        echo -e "${GREEN}✓${NC} $pkg"
    else
        echo -e "${RED}❌${NC} $pkg ${RED}(未找到)${NC}"
    fi
done
echo ""

# 检查Python路径
echo -e "${YELLOW}[4] Python环境${NC}"
echo "Python版本: $(python3 --version)"
echo "Conda环境: ${CONDA_DEFAULT_ENV:-未激活}"
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo -e "${YELLOW}⚠️  注意: Conda环境可能影响ROS2${NC}"
fi
echo ""

# 检查当前目录
echo -e "${YELLOW}[5] 当前目录${NC}"
echo "PWD: $(pwd)"
echo ""

# 提供建议
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}建议${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "如果工作空间未正确加载，请按以下顺序执行："
echo ""
echo "1. 加载ROS2基础环境:"
echo "   source /opt/ros/humble/setup.bash"
echo ""
echo "2. 加载arm_teleop工作空间:"
echo "   cd ~/Dev/VIST/external_sdk/arm_teleop"
echo "   source install/setup.bash"
echo ""
echo "3. 加载VIST工作空间:"
echo "   cd ~/Dev/VIST"
echo "   source install/setup.bash"
echo ""
echo "4. 验证环境:"
echo "   ros2 pkg list | grep -E 'linkerta|lbot_teleop'"
echo ""