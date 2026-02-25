#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 参数：准备时间（秒）和操作时长（秒）
PREP_TIME=${1:-20}
OPERATION_TIME=${2:-60}

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}遥操臂控制系统 - 定时安全启动${NC}"
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

# 显示时间配置
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}时间配置${NC}"
echo -e "${CYAN}==========================================${NC}"
echo -e "准备时间: ${YELLOW}${PREP_TIME}${NC} 秒"
echo -e "操作时长: ${YELLOW}${OPERATION_TIME}${NC} 秒"
echo -e "总时间: ${YELLOW}$((PREP_TIME + OPERATION_TIME))${NC} 秒"
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
echo "请在准备倒计时结束前完成以下步骤："
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

# 准备倒计时
echo -e "${YELLOW}准备倒计时: ${PREP_TIME} 秒${NC}"
echo -e "${YELLOW}按 Ctrl+C 可以取消启动${NC}"
echo ""

for ((i=$PREP_TIME; i>0; i--)); do
    if [ $i -le 5 ]; then
        echo -e "${RED}⏰ 准备倒计时: $i 秒${NC}"
        tput bel 2>/dev/null || true
    elif [ $i -le 10 ]; then
        echo -e "${YELLOW}⏰ 准备倒计时: $i 秒 - 请准备就绪${NC}"
    else
        echo -e "${BLUE}⏰ 准备倒计时: $i 秒${NC}"
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
echo -e "${CYAN}操作时长: ${OPERATION_TIME} 秒${NC}"
echo -e "${CYAN}系统将在 ${OPERATION_TIME} 秒后自动停止${NC}"
echo ""
echo -e "${RED}⚠️  安全提示：${NC}"
echo "  - 随时准备按下急停按钮"
echo "  - 避免突然大幅度移动"
echo "  - 首次移动会以低速进行"
echo "  - 时间到后系统会自动停止"
echo "  - 机械臂将保持当前位置"
echo "  - 按 Ctrl+C 可以提前停止"
echo ""

# 创建临时文件存储进程ID
PID_FILE="/tmp/arm_teleop_$$.pid"

# 设置陷阱以捕获Ctrl+C和定时器
cleanup() {
    echo ""
    echo -e "${YELLOW}正在安全停止系统...${NC}"

    # 如果有进程ID，发送SIGTERM信号
    if [ -f "$PID_FILE" ]; then
        TELEOP_PID=$(cat "$PID_FILE")
        if ps -p $TELEOP_PID > /dev/null 2>&1; then
            echo "发送停止信号到遥操作节点..."
            kill -TERM $TELEOP_PID 2>/dev/null || true

            # 等待进程优雅停止
            echo "等待机器人停止运动..."
            for i in {1..5}; do
                if ! ps -p $TELEOP_PID > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done

            # 如果还没停止，强制停止
            if ps -p $TELEOP_PID > /dev/null 2>&1; then
                kill -KILL $TELEOP_PID 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    echo -e "${GREEN}✅ 系统已安全停止${NC}"
    echo ""
    echo -e "${CYAN}提示：${NC}"
    echo "  - 遥操作控制已停止"
    echo "  - 机械臂将保持当前位置"
    echo "  - 如需下使能，请在web控制器中操作"
    echo "  - 建议先将机械臂移到安全位置再下使能"
    echo ""
    exit 0
}

trap cleanup INT TERM

# 在后台启动遥操作系统
ros2 launch lbot_teleop teleop.launch.py &
TELEOP_PID=$!
echo $TELEOP_PID > "$PID_FILE"

echo -e "${GREEN}遥操作系统已启动 (PID: $TELEOP_PID)${NC}"
echo ""

# 等待系统完全启动（3秒）
echo "等待系统完全启动..."
sleep 3

# 检查进程是否成功启动
if ! ps -p $TELEOP_PID > /dev/null 2>&1; then
    echo -e "${RED}错误: 遥操作系统启动失败${NC}"
    rm -f "$PID_FILE"
    exit 1
fi

echo -e "${GREEN}✅ 系统启动完成${NC}"
echo ""

# 操作时长倒计时
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}操作计时开始${NC}"
echo -e "${CYAN}==========================================${NC}"
echo ""

for ((i=$OPERATION_TIME; i>0; i--)); do
    # 检查进程是否还在运行
    if ! ps -p $TELEOP_PID > /dev/null 2>&1; then
        echo -e "${RED}错误: 遥操作节点意外停止${NC}"
        rm -f "$PID_FILE"
        exit 1
    fi

    # 显示剩余时间
    if [ $i -le 10 ]; then
        echo -e "${RED}⏱️  剩余时间: $i 秒 - 准备停止，请将机械臂移到安全位置${NC}"
        tput bel 2>/dev/null || true
    elif [ $i -le 30 ]; then
        echo -e "${YELLOW}⏱️  剩余时间: $i 秒${NC}"
    elif [ $((i % 10)) -eq 0 ]; then
        # 每10秒显示一次
        echo -e "${CYAN}⏱️  剩余时间: $i 秒${NC}"
    fi

    sleep 1
done

echo ""
echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW}⏰ 操作时间已到${NC}"
echo -e "${YELLOW}==========================================${NC}"
echo ""

# 调用清理函数停止系统
cleanup
