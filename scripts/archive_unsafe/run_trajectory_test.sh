#!/bin/bash
# 测试轨迹对比的启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 轨迹对比测试 ===${NC}"
echo ""

# 加载ROS2环境
source /opt/ros/humble/setup.bash
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash
fi

# 创建数据目录
mkdir -p data

echo -e "${YELLOW}步骤1: 启动轨迹发布节点${NC}"
echo "在新终端中运行: python3 scripts/test_trajectory_comparison.py publisher"
echo ""
echo -e "${YELLOW}步骤2: 启动轨迹对比节点${NC}"
echo "在另一个新终端中运行: python3 scripts/test_trajectory_comparison.py comparator"
echo ""
echo -e "${YELLOW}步骤3: 等待10秒后按Ctrl+C停止对比节点${NC}"
echo ""
echo -e "${YELLOW}步骤4: 可视化结果${NC}"
echo "运行: python3 scripts/visualize_trajectory_comparison.py data/test_trajectory_comparison.pkl"
echo ""

# 询问是否自动运行
read -p "是否自动运行测试? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}启动发布节点...${NC}"
    python3 scripts/test_trajectory_comparison.py publisher &
    PUBLISHER_PID=$!

    sleep 2

    echo -e "${GREEN}启动对比节点...${NC}"
    python3 scripts/test_trajectory_comparison.py comparator &
    COMPARATOR_PID=$!

    echo -e "${GREEN}运行10秒...${NC}"
    sleep 10

    echo -e "${GREEN}停止节点...${NC}"
    kill -INT $COMPARATOR_PID
    sleep 1
    kill $PUBLISHER_PID

    echo -e "${GREEN}可视化结果...${NC}"
    python3 scripts/visualize_trajectory_comparison.py data/test_trajectory_comparison.pkl

    echo ""
    echo -e "${GREEN}测试完成！${NC}"
    echo "结果保存在: data/trajectory_comparison.png"
fi