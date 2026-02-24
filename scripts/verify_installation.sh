#!/bin/bash
# VIST 安装验证脚本
# 用途：验证VIST环境是否正确配置

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 计数器
PASSED=0
FAILED=0

# 测试函数
test_command() {
    local name="$1"
    local command="$2"

    echo -n "测试 $name... "
    if eval "$command" &> /dev/null; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        ((FAILED++))
        return 1
    fi
}

echo "========================================="
echo "VIST 环境验证"
echo "========================================="
echo ""

# 1. 系统检查
echo "1. 系统环境检查"
echo "-----------------------------------------"
test_command "Ubuntu版本" "[ -f /etc/os-release ]"
test_command "Python 3.10+" "python3 -c 'import sys; assert sys.version_info >= (3, 10)'"
test_command "pip可用" "command -v pip"
echo ""

# 2. ROS2检查
echo "2. ROS2环境检查"
echo "-----------------------------------------"
test_command "ROS2安装" "[ -f /opt/ros/humble/setup.bash ]"
test_command "ros2命令" "command -v ros2"
test_command "colcon命令" "command -v colcon"
test_command "rosbag2" "ros2 bag --help"
echo ""

# 3. Python依赖检查
echo "3. Python依赖检查"
echo "-----------------------------------------"
test_command "numpy" "python3 -c 'import numpy'"
test_command "scipy" "python3 -c 'import scipy'"
test_command "matplotlib" "python3 -c 'import matplotlib'"
test_command "yaml" "python3 -c 'import yaml'"
test_command "opencv" "python3 -c 'import cv2'"
test_command "rosbag2_py" "python3 -c 'from rosbag2_py import SequentialReader'"
echo ""

# 4. 自定义消息检查
echo "4. 自定义ROS2消息检查"
echo "-----------------------------------------"
test_command "lbot_arm_interfaces编译" "[ -d external_sdk/arm_teleop/install/lbot_arm_interfaces ]"
test_command "FollowJoint消息" "python3 -c 'from lbot_arm_interfaces.msg import FollowJoint'"
test_command "ArmState消息" "python3 -c 'from lbot_arm_interfaces.msg import ArmState'"
echo ""

# 5. 项目结构检查
echo "5. 项目结构检查"
echo "-----------------------------------------"
test_command "config目录" "[ -d config ]"
test_command "scripts目录" "[ -d scripts ]"
test_command "src目录" "[ -d src ]"
test_command "docs目录" "[ -d docs ]"
test_command "requirements.txt" "[ -f requirements.txt ]"
test_command "SETUP.md" "[ -f SETUP.md ]"
echo ""

# 6. 关键脚本检查
echo "6. 关键脚本检查"
echo "-----------------------------------------"
test_command "analyze_all_metrics.py" "[ -f scripts/analyze_all_metrics.py ]"
test_command "run_analysis.sh" "[ -f scripts/run_analysis.sh ]"
test_command "run_ablation_experiments.py" "[ -f scripts/run_ablation_experiments.py ]"
echo ""

# 7. 配置文件检查
echo "7. 配置文件检查"
echo "-----------------------------------------"
test_command "system_config.yaml" "[ -f config/system_config.yaml ]"
test_command "vist_filter_config.yaml" "[ -f config/vist_filter_config.yaml ]"
test_command "analysis_config.yaml" "[ -f config/analysis_config.yaml ]"
test_command "ablation_experiments.yaml" "[ -f config/ablation_experiments.yaml ]"
echo ""

# 8. 环境变量检查
echo "8. 环境变量检查"
echo "-----------------------------------------"
test_command "VIST_ROOT设置" "[ ! -z \"\$VIST_ROOT\" ]"
test_command "ROS_DISTRO设置" "[ \"\$ROS_DISTRO\" = \"humble\" ]"
echo ""

# 总结
echo "========================================="
echo "验证结果"
echo "========================================="
echo -e "通过: ${GREEN}$PASSED${NC}"
echo -e "失败: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！环境配置正确。${NC}"
    echo ""
    echo "下一步："
    echo "1. 查看文档: cat SETUP.md"
    echo "2. 运行数据分析: ./scripts/run_analysis.sh --help"
    echo "3. 查看配置: cat config/system_config.yaml"
    exit 0
else
    echo -e "${RED}✗ 部分检查失败，请检查环境配置。${NC}"
    echo ""
    echo "故障排查："
    echo "1. 查看安装文档: cat SETUP.md"
    echo "2. 重新运行安装: ./scripts/setup_environment.sh"
    echo "3. 手动source环境: source ~/.vist_env.sh"
    echo "4. 查看故障排查: cat TROUBLESHOOTING.md"
    exit 1
fi