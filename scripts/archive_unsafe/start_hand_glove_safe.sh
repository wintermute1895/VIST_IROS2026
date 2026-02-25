#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认倒计时时间（秒）
COUNTDOWN_TIME=${1:-15}

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}数据手套遥操作系统 - 安全启动${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 退出conda环境
conda deactivate 2>/dev/null || true

# Source ROS2环境
echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash

# Source灵巧手工作空间
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2
source install/setup.bash

echo ""
echo -e "${GREEN}✅ 环境已加载${NC}"
echo ""

# 显示准备步骤
echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW}准备步骤清单${NC}"
echo -e "${YELLOW}==========================================${NC}"
echo ""
echo "请在倒计时结束前完成以下步骤："
echo ""
echo "  1. [ ] 穿戴数据手套"
echo "  2. [ ] 确认手套电源已开启"
echo "  3. [ ] 确认手套USB已连接"
echo "  4. [ ] 确认灵巧手已上电"
echo "  5. [ ] 确认CAN设备已配置（can0）"
echo "  6. [ ] 确认周围环境安全"
echo "  7. [ ] 准备好急停按钮"
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
        # 发出提示音（如果系统支持）
        tput bel 2>/dev/null || true
    else
        echo -e "${YELLOW}⏰ 倒计时: $i 秒${NC}"
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}🚀 启动遥操作系统${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "系统正在启动，请保持手套在初始位置..."
echo ""
echo -e "${RED}⚠️  安全提示：${NC}"
echo "  - 随时准备按下急停按钮"
echo "  - 避免突然大幅度移动"
echo "  - 按 Ctrl+C 可以安全停止系统"
echo ""

# 设置陷阱以捕获Ctrl+C
trap 'echo -e "\n${YELLOW}正在安全停止系统...${NC}"; sleep 2; echo -e "${GREEN}系统已安全停止${NC}"; exit 0' INT TERM

# 启动灵巧手重定向节点
ros2 launch linkerhand_retarget linkerhand_retarget.launch.py calibration:=True
