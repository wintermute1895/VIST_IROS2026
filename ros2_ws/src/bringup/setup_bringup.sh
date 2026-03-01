#!/bin/bash
# Bringup包完整安装脚本
# 自动完成所有必要的设置步骤

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VIST Bringup 包安装脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 检查工作空间
VIST_WS="/home/ilex/Dev/VIST/ros2_ws"
if [ ! -d "$VIST_WS" ]; then
    echo -e "${RED}错误: 工作空间不存在: $VIST_WS${NC}"
    exit 1
fi

cd "$VIST_WS"
echo -e "${GREEN}✓ 工作空间: $VIST_WS${NC}"

# 2. 安装camera_manager的Python包元数据
echo ""
echo -e "${BLUE}步骤 1/4: 安装camera_manager Python包元数据${NC}"
cd src/camera_manager
if pip3 install -e . --user; then
    echo -e "${GREEN}✓ camera_manager安装成功${NC}"
else
    echo -e "${YELLOW}⚠ camera_manager安装失败，但继续...${NC}"
fi

# 3. 编译bringup包
echo ""
echo -e "${BLUE}步骤 2/4: 编译bringup包${NC}"
cd "$VIST_WS"
if colcon build --packages-select bringup --symlink-install; then
    echo -e "${GREEN}✓ bringup包编译成功${NC}"
else
    echo -e "${RED}✗ bringup包编译失败${NC}"
    exit 1
fi

# 4. 编译外部工作空间
echo ""
echo -e "${BLUE}步骤 3/4: 编译外骨骼工作空间${NC}"
EXO_WS="$VIST_WS/src/external_sdk/arm_teleop"
if [ -d "$EXO_WS" ]; then
    cd "$EXO_WS"
    
    # 清理旧的构建
    echo "清理旧的构建文件..."
    rm -rf build install log
    
    # 编译
    if colcon build --allow-overriding lbot_driver lbot_teleop linkerta; then
        echo -e "${GREEN}✓ 外骨骼工作空间编译成功${NC}"
    else
        echo -e "${YELLOW}⚠ 外骨骼工作空间编译失败，但继续...${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 外骨骼工作空间不存在，跳过${NC}"
fi

# 5. 验证安装
echo ""
echo -e "${BLUE}步骤 4/4: 验证安装${NC}"
cd "$VIST_WS"
source install/setup.bash

# 检查bringup包
if ros2 pkg list | grep -q "^bringup$"; then
    echo -e "${GREEN}✓ bringup包已安装${NC}"
else
    echo -e "${RED}✗ bringup包未找到${NC}"
    exit 1
fi

# 检查launch文件
LAUNCH_DIR="$VIST_WS/install/bringup/share/bringup/launch"
if [ -d "$LAUNCH_DIR" ]; then
    LAUNCH_COUNT=$(ls -1 "$LAUNCH_DIR"/*.py 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ 找到 $LAUNCH_COUNT 个launch文件${NC}"
else
    echo -e "${RED}✗ Launch目录不存在${NC}"
    exit 1
fi

# 完成
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 安装完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "现在可以使用以下命令启动系统："
echo ""
echo -e "${YELLOW}# 启动完整系统${NC}"
echo "ros2 launch bringup teleop_system.launch.py"
echo ""
echo -e "${YELLOW}# 启动系统并启用相机${NC}"
echo "ros2 launch bringup teleop_system.launch.py enable_camera:=true"
echo ""
echo -e "${YELLOW}# 测试单个模块${NC}"
echo "ros2 launch bringup camera.launch.py"
echo ""
echo "详细文档请查看: $VIST_WS/src/bringup/README.md"
