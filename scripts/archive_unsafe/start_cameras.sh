#!/bin/bash
# 启动多相机系统的快速脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  多相机系统启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否在VIST目录
if [ ! -f "install/setup.bash" ]; then
    echo -e "${RED}错误: 请在VIST项目根目录运行此脚本${NC}"
    exit 1
fi

# Source ROS2环境
echo -e "${YELLOW}加载ROS2环境...${NC}"
source install/setup.bash

# 检查相机连接
echo -e "${YELLOW}检查相机连接...${NC}"
if ! command -v rs-enumerate-devices &> /dev/null; then
    echo -e "${RED}警告: 未找到rs-enumerate-devices命令${NC}"
    echo -e "${YELLOW}请确保已安装librealsense2${NC}"
else
    CAMERA_COUNT=$(rs-enumerate-devices | grep -c "Device info:")
    echo -e "${GREEN}检测到 $CAMERA_COUNT 个RealSense相机${NC}"

    if [ "$CAMERA_COUNT" -eq 0 ]; then
        echo -e "${RED}错误: 未检测到相机！${NC}"
        echo -e "${YELLOW}请检查：${NC}"
        echo "  1. 相机是否已连接"
        echo "  2. USB线缆是否正常"
        echo "  3. 是否有足够的USB供电"
        exit 1
    fi
fi

# 检查配置文件
CONFIG_FILE="src/camera_manager/config/camera_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件不存在: $CONFIG_FILE${NC}"
    exit 1
fi

# 检查是否配置了序列号
if grep -q "your_d435i_serial" "$CONFIG_FILE"; then
    echo -e "${YELLOW}警告: 配置文件中包含默认序列号${NC}"
    echo -e "${YELLOW}请先运行以下命令获取实际序列号：${NC}"
    echo "  ros2 run camera_manager list_cameras"
    echo -e "${YELLOW}然后编辑配置文件: $CONFIG_FILE${NC}"
    read -p "是否继续启动？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 启动多相机管理器
echo -e "${GREEN}启动多相机管理器...${NC}"
echo -e "${YELLOW}按Ctrl+C停止${NC}"
echo ""

ros2 launch camera_manager multi_realsense.launch.py
