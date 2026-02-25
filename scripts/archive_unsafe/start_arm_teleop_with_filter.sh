#!/bin/bash
# 外骨骼遥操 + 滤波器集成启动脚本
# 支持切换不同滤波器类型进行对比实验

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 默认参数
FILTER_TYPE="passthrough"
ARM_SIDE="right"
OUTPUT_FREQ="100.0"
COUNTDOWN_TIME=15

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --filter)
            FILTER_TYPE="$2"
            shift 2
            ;;
        --arm)
            ARM_SIDE="$2"
            shift 2
            ;;
        --freq)
            OUTPUT_FREQ="$2"
            shift 2
            ;;
        --countdown)
            COUNTDOWN_TIME="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --filter <type>        滤波器类型 (默认: passthrough)"
            echo "                         可选: passthrough, one_euro, ema, vist_kalman"
            echo "  --arm <side>           控制哪个臂 (默认: right)"
            echo "                         可选: left, right"
            echo "  --freq <hz>            输出频率 (默认: 100.0)"
            echo "  --countdown <sec>      启动倒计时 (默认: 15)"
            echo "  --help                 显示此帮助信息"
            echo ""
            echo "滤波器说明:"
            echo "  passthrough   - 无滤波（Baseline对照组）"
            echo "  one_euro      - One-Euro滤波器（经典方法）"
            echo "  ema           - 指数移动平均滤波器（简单方法）"
            echo "  vist_kalman   - VIST卡尔曼滤波器（完整VIST算法）"
            echo ""
            echo "示例:"
            echo "  $0 --filter passthrough    # Baseline实验"
            echo "  $0 --filter one_euro       # One-Euro对比实验"
            echo "  $0 --filter ema            # EMA对比实验"
            echo "  $0 --filter vist_kalman    # VIST实验"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}外骨骼遥操 + 滤波器集成系统${NC}"
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
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}系统配置${NC}"
echo -e "${CYAN}==========================================${NC}"
echo "主臂（遥操臂）: Linkerta"
echo "从臂（机械臂）: LBot"
echo "滤波器类型: $FILTER_TYPE"
echo "控制臂侧: $ARM_SIDE"
echo "输出频率: $OUTPUT_FREQ Hz"
echo ""

# 显示滤波器说明
echo -e "${CYAN}滤波器说明:${NC}"
case $FILTER_TYPE in
    passthrough)
        echo -e "  ${YELLOW}Passthrough (无滤波)${NC}"
        echo "  - 直接透传外骨骼数据"
        echo "  - 用作Baseline对照组"
        echo "  - 预期: 高Jerk, 高震颤"
        ;;
    one_euro)
        echo -e "  ${YELLOW}One-Euro Filter${NC}"
        echo "  - 经典低延迟滤波算法"
        echo "  - 速度自适应截止频率"
        echo "  - 预期: 降低震颤, 保持响应性"
        ;;
    ema)
        echo -e "  ${YELLOW}EMA (指数移动平均)${NC}"
        echo "  - 简单低通滤波"
        echo "  - 固定平滑系数"
        echo "  - 预期: 降低震颤, 增加延迟"
        ;;
    vist_kalman)
        echo -e "  ${YELLOW}VIST Kalman Filter${NC}"
        echo "  - 完整VIST算法"
        echo "  - 自适应卡尔曼滤波 + 流形约束"
        echo "  - 意图驱动的权重调制"
        echo "  - 预期: 最低Jerk, 最高成功率"
        ;;
    *)
        echo -e "  ${RED}未知滤波器类型: $FILTER_TYPE${NC}"
        exit 1
        ;;
esac
echo ""

# 显示控制流程
echo -e "${CYAN}控制流程:${NC}"
echo "  Linkerta外骨骼 (230Hz)"
echo "       ↓"
echo "  linkerta_node"
echo "       ↓ /exo_${ARM_SIDE}_joint_control"
echo "  VIST Filter Node ($FILTER_TYPE)"
echo "       ↓ /filtered_${ARM_SIDE}_joint_control"
echo "  teleop_bridge_node"
echo "       ↓ /robot1/${ARM_SIDE}_arm/joint_follow"
echo "  lbot_driver"
echo "       ↓"
echo "  LinkerArm A7 (50Hz执行)"
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
echo -e "${GREEN}🚀 启动遥操作系统 + 滤波器${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "系统正在启动，请保持遥操臂在初始位置..."
echo ""
echo "启动顺序:"
echo "  1. lbot_driver (从臂驱动) - 立即启动"
echo "  2. linkerta (主臂驱动) - 1秒后启动"
echo "  3. VIST Filter Node ($FILTER_TYPE) - 2秒后启动"
echo "  4. teleop_bridge (桥接节点) - 3秒后启动"
echo ""
echo -e "${RED}⚠️  安全提示：${NC}"
echo "  - 随时准备按下急停按钮"
echo "  - 避免突然大幅度移动"
echo "  - 首次移动会以低速进行"
echo "  - 按 Ctrl+C 可以安全停止系统"
echo ""
echo -e "${CYAN}📊 性能监控：${NC}"
echo "  - 实时性能指标发布到: /vist_performance"
echo "  - 意图因子发布到: /vist_intent_factors"
echo "  - 使用 'ros2 topic echo /vist_performance' 查看"
echo ""

# 设置陷阱以捕获Ctrl+C
trap 'echo -e "\n${YELLOW}正在安全停止系统...${NC}"; echo "等待机器人停止运动..."; sleep 3; echo -e "${GREEN}系统已安全停止${NC}"; exit 0' INT TERM

# 启动遥操作系统 + 滤波器
ros2 launch lbot_teleop teleop_with_filter.launch.py \
    filter_type:=$FILTER_TYPE \
    arm_side:=$ARM_SIDE \
    output_freq:=$OUTPUT_FREQ
