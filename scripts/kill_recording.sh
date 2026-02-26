#!/bin/bash
# 清理卡住的数据采集进程

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}检查正在运行的数据采集进程...${NC}"
echo ""

# 查找 ros2 bag record 进程
PIDS=$(pgrep -f "ros2 bag record")

if [ -z "$PIDS" ]; then
    echo -e "${GREEN}✓ 没有发现正在运行的数据采集进程${NC}"
    exit 0
fi

echo -e "${RED}发现以下进程:${NC}"
ps aux | grep "ros2 bag record" | grep -v grep
echo ""

echo -e "${YELLOW}是否终止这些进程? (y/n)${NC}"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}正在终止进程...${NC}"

    # 先尝试温和的 SIGTERM
    pkill -SIGTERM -f "ros2 bag record"
    sleep 2

    # 检查是否还有进程
    REMAINING=$(pgrep -f "ros2 bag record")
    if [ -n "$REMAINING" ]; then
        echo -e "${YELLOW}进程未响应，使用 SIGKILL 强制终止...${NC}"
        pkill -9 -f "ros2 bag record"
        sleep 1
    fi

    # 最终检查
    FINAL_CHECK=$(pgrep -f "ros2 bag record")
    if [ -z "$FINAL_CHECK" ]; then
        echo -e "${GREEN}✓ 所有进程已终止${NC}"
    else
        echo -e "${RED}❌ 部分进程仍在运行，请手动检查${NC}"
        ps aux | grep "ros2 bag record" | grep -v grep
    fi
else
    echo "已取消"
fi