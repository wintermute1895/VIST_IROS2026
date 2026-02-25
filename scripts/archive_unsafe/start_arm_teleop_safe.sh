#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认倒计时时间（秒）
COUNTDOWN_TIME=${1:-20}

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}遥操臂控制系统 - 安全启动${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 进入遥操臂工作空间
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo -e "${GREEN}✅ 环境已加载${NC}"
echo ""

# 显示系统配置
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}系统配置${NC}"
echo -e "${BLUE}==========================================${NC}"
echo "主臂（遥操臂）: Linkerta"
echo "从臂（机械臂）: LBot"
echo "配置文件: config/teleop_config.yaml"
echo ""

# 显示准备步骤
echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW}准备步骤清单${NC}"
echo -e "${YELLOW}==========================================${NC}"
echo ""
echo "请在倒计时结束前完成以下步骤："
echo ""
echo "  1. [ ] 确认机械臂已上电"
echo "  2. [ ] 确认网络连接正常（ping 192.168.10.21）"
echo "  3. [ ] 确认遥操臂已连接"
echo "  4. [ ] 确认遥操臂在安全初始位置"
echo "  5. [ ] 确认机械臂周围环境安全"
echo "  6. [ ] 清除机械臂工作空间内的障碍物"
echo "  7. [ ] 准备好急停按钮"
echo "  8. [ ] 穿戴好遥操臂设备"
echo ""
echo -e "${YELLOW}==========================================${NC}"
echo ""

# 倒计时
echo -e "${YELLOW}系统将在 ${COUNTDOWN_TIME} 秒后启动...${NC}"
echo -e "${YELLOW}按 Ctrl+C 可以取消启动${NC}"
echo ""

for ((i=$COUNTDOWN_TIME; i>0; i--)); do
    if [ $i -le 5 ]; then
        echo -e "${RED}⏰ 倒计时: $i 秒${NC}"
        # 发出提示音
        tput bel 2>/dev/null || true
    elif [ $i -le 10 ]; then
        echo -e "${YELLOW}⏰ 倒计时: $i 秒 - 请准备就绪${NC}"
    else
        echo -e "${BLUE}⏰ 倒计时: $i 秒${NC}"
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}🚀 启动遥操作系统${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "系统正在启动，请保持遥操臂在初始位置..."
echo ""
echo "启动顺序:"
echo "  1. lbot_driver (从臂驱动) - 立即启动"
echo "  2. linkerta (主臂驱动) - 1秒后启动"
echo "  3. teleop_bridge (桥接节点) - 2秒后启动"
echo ""
echo -e "${RED}⚠️  安全提示：${NC}"
echo "  - 随时准备按下急停按钮"
echo "  - 避免突然大幅度移动"
echo "  - 首次移动会以低速进行"
echo "  - 按 Ctrl+C 可以安全停止系统"
echo ""

# 设置陷阱以捕获Ctrl+C
trap 'echo -e "\n${YELLOW}正在安全停止系统...${NC}"; echo "等待机器人停止运动..."; sleep 3; echo -e "${GREEN}系统已安全停止${NC}"; exit 0' INT TERM

# 启动遥操作系统
ros2 launch lbot_teleop teleop.launch.py
