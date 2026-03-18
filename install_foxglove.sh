#!/bin/bash
# 安装 Foxglove Studio

echo "=========================================="
echo "安装 Foxglove Studio"
echo "=========================================="
echo ""

# 方法1: 使用snap安装（推荐）
if command -v snap &> /dev/null; then
    echo "使用snap安装..."
    sudo snap install foxglove-studio
    echo "✓ 安装完成"
    echo ""
    echo "启动命令: foxglove-studio"
else
    echo "snap未安装，使用AppImage方式..."
    echo ""
    echo "请访问: https://foxglove.dev/download"
    echo "下载 Foxglove Studio AppImage"
    echo ""
    echo "或者使用以下命令下载:"
    echo "  wget https://github.com/foxglove/studio/releases/latest/download/foxglove-studio-linux-amd64.AppImage"
    echo "  chmod +x foxglove-studio-linux-amd64.AppImage"
    echo "  ./foxglove-studio-linux-amd64.AppImage"
fi

echo ""
echo "=========================================="
echo "安装 Foxglove Bridge (ROS2连接器)"
echo "=========================================="
echo ""

# 安装foxglove_bridge
sudo apt update
sudo apt install -y ros-humble-foxglove-bridge

echo ""
echo "✓ 安装完成"
echo ""
echo "使用方法:"
echo "  1. 启动bridge: ros2 launch foxglove_bridge foxglove_bridge_launch.xml"
echo "  2. 打开Foxglove Studio"
echo "  3. 连接到 ws://localhost:8765"
echo ""
