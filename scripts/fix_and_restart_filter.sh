#!/bin/bash
# 一键修复并重启滤波节点

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}修复并重启VIST滤波节点${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 检查当前滤波节点订阅的话题
echo -e "${YELLOW}[1] 检查当前滤波节点配置${NC}"
echo "当前订阅的话题:"
ros2 node info /vist_filter_node 2>/dev/null | grep -A 2 "Subscribers:" | grep "joint_control" || echo "  无法获取信息"
echo ""

# 2. 显示配置文件中的设置
echo -e "${YELLOW}[2] 配置文件设置${NC}"
echo "配置文件中的话题:"
grep "exo_left_topic:" config/vist_filter_config.yaml
echo ""

# 3. 询问是否重启
echo -e "${YELLOW}[3] 需要重启滤波节点以应用新配置${NC}"
echo ""
echo "请按照以下步骤操作："
echo ""
echo -e "${GREEN}步骤1:${NC} 找到运行滤波节点的终端"
echo -e "${GREEN}步骤2:${NC} 按 Ctrl+C 停止滤波节点"
echo -e "${GREEN}步骤3:${NC} 运行以下命令重启:"
echo ""
echo -e "  ${BLUE}./scripts/startup/start_vist_filter.sh${NC}"
echo ""
echo -e "${GREEN}步骤4:${NC} 重启后运行诊断验证:"
echo ""
echo -e "  ${BLUE}./scripts/diagnose_system.sh${NC}"
echo ""
echo "预期结果："
echo "  ✓ /left_arm_joint_control: 1个订阅者"
echo "  ✓ /filtered_left_joint_control: 有数据流动"
echo "  ✓ /robot1/left_arm/joint_follow: 有数据流动"
echo ""
echo -e "${BLUE}========================================${NC}"