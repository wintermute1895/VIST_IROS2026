#!/bin/bash
# 完整数据采集脚本 - 同时启动相机、遥操作系统并记录数据

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认参数
PREP_TIME=20
RECORD_TIME=60
BAG_DIR="$HOME/teleop_data/$(date +%Y%m%d_%H%M%S)"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--prep)
            PREP_TIME="$2"
            shift 2
            ;;
        -t|--time)
            RECORD_TIME="$2"
            shift 2
            ;;
        -o|--output)
            BAG_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  -p, --prep TIME     准备时间（秒），默认20"
            echo "  -t, --time TIME     记录时间（秒），默认60"
            echo "  -o, --output DIR    输出目录，默认~/teleop_data/时间戳"
            echo "  -h, --help          显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  完整数据采集系统${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}准备时间: ${PREP_TIME}秒${NC}"
echo -e "${BLUE}记录时间: ${RECORD_TIME}秒${NC}"
echo -e "${BLUE}输出目录: ${BAG_DIR}${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查目录
if [ ! -f "install/setup.bash" ]; then
    echo -e "${RED}错误: 请在VIST项目根目录运行此脚本${NC}"
    exit 1
fi

# Source环境
source install/setup.bash

# 创建输出目录
mkdir -p "$BAG_DIR"
echo -e "${GREEN}创建输出目录: $BAG_DIR${NC}"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止所有进程...${NC}"
    kill $CAMERA_PID $ARM_PID $HAND_PID $BAG_PID 2>/dev/null
    wait $CAMERA_PID $ARM_PID $HAND_PID $BAG_PID 2>/dev/null
    echo -e "${GREEN}所有进程已停止${NC}"
    echo -e "${GREEN}数据已保存到: $BAG_DIR${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 1. 启动相机系统
echo -e "${YELLOW}[1/4] 启动相机系统...${NC}"
ros2 launch camera_manager multi_realsense.launch.py > "$BAG_DIR/camera.log" 2>&1 &
CAMERA_PID=$!
sleep 3

if ! kill -0 $CAMERA_PID 2>/dev/null; then
    echo -e "${RED}相机系统启动失败！${NC}"
    exit 1
fi
echo -e "${GREEN}相机系统已启动 (PID: $CAMERA_PID)${NC}"

# 2. 启动机械臂遥操作
echo -e "${YELLOW}[2/4] 启动机械臂遥操作...${NC}"
cd external_sdk/arm_teleop
bash start_arm_teleop.sh > "$BAG_DIR/arm_teleop.log" 2>&1 &
ARM_PID=$!
cd ../..
sleep 2

if ! kill -0 $ARM_PID 2>/dev/null; then
    echo -e "${RED}机械臂遥操作启动失败！${NC}"
    kill $CAMERA_PID
    exit 1
fi
echo -e "${GREEN}机械臂遥操作已启动 (PID: $ARM_PID)${NC}"

# 3. 启动手套控制
echo -e "${YELLOW}[3/4] 启动手套控制...${NC}"
cd external_sdk/hand_glove
bash start_hand_glove.sh > "$BAG_DIR/hand_glove.log" 2>&1 &
HAND_PID=$!
cd ../..
sleep 2

if ! kill -0 $HAND_PID 2>/dev/null; then
    echo -e "${RED}手套控制启动失败！${NC}"
    kill $CAMERA_PID $ARM_PID
    exit 1
fi
echo -e "${GREEN}手套控制已启动 (PID: $HAND_PID)${NC}"

# 准备倒计时
echo -e "\n${YELLOW}========================================${NC}"
echo -e "${YELLOW}  准备阶段 - 请做好操作准备${NC}"
echo -e "${YELLOW}========================================${NC}"
for ((i=$PREP_TIME; i>0; i--)); do
    echo -ne "${YELLOW}开始记录倒计时: ${i}秒\r${NC}"
    sleep 1
done
echo -e "\n"

# 4. 开始记录数据
echo -e "${GREEN}[4/4] 开始记录数据...${NC}"
cd "$BAG_DIR"
ros2 bag record -a -o teleop_data &
BAG_PID=$!
cd - > /dev/null

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  正在记录数据...${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}记录时间: ${RECORD_TIME}秒${NC}"
echo -e "${YELLOW}按Ctrl+C可提前停止${NC}"

# 记录倒计时
for ((i=$RECORD_TIME; i>0; i--)); do
    if [ $i -le 10 ]; then
        echo -ne "${RED}剩余时间: ${i}秒 - 准备结束操作\r${NC}"
    else
        echo -ne "${GREEN}剩余时间: ${i}秒\r${NC}"
    fi
    sleep 1
done

echo -e "\n${GREEN}记录完成！${NC}"
cleanup
