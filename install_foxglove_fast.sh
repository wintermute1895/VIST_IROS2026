#!/bin/bash
# 下载 Foxglove Studio AppImage（使用GitHub镜像）

echo "=========================================="
echo "下载 Foxglove Studio"
echo "=========================================="
echo ""

# 创建下载目录
mkdir -p ~/Applications
cd ~/Applications

# 使用GitHub镜像加速下载
echo "正在下载 Foxglove Studio..."
echo "使用镜像: ghproxy.com"
echo ""

# 获取最新版本
LATEST_VERSION="2.14.0"  # 如果失败，手动指定版本号

# 使用GitHub代理下载
wget -O foxglove-studio.AppImage \
    "https://mirror.ghproxy.com/https://github.com/foxglove/studio/releases/download/v${LATEST_VERSION}/foxglove-studio-${LATEST_VERSION}-linux-amd64.AppImage" \
    || wget -O foxglove-studio.AppImage \
    "https://ghproxy.net/https://github.com/foxglove/studio/releases/download/v${LATEST_VERSION}/foxglove-studio-${LATEST_VERSION}-linux-amd64.AppImage" \
    || wget -O foxglove-studio.AppImage \
    "https://github.com/foxglove/studio/releases/download/v${LATEST_VERSION}/foxglove-studio-${LATEST_VERSION}-linux-amd64.AppImage"

if [ $? -eq 0 ]; then
    chmod +x foxglove-studio.AppImage
    echo ""
    echo "✓ 下载完成"
    echo ""
    echo "安装位置: ~/Applications/foxglove-studio.AppImage"
    echo ""
    echo "启动命令:"
    echo "  ~/Applications/foxglove-studio.AppImage"
    echo ""
    echo "创建桌面快捷方式..."

    # 创建桌面快捷方式
    cat > ~/.local/share/applications/foxglove-studio.desktop << EOF
[Desktop Entry]
Name=Foxglove Studio
Comment=Robotics visualization and debugging
Exec=$HOME/Applications/foxglove-studio.AppImage
Icon=foxglove
Terminal=false
Type=Application
Categories=Development;
EOF

    echo "✓ 桌面快捷方式已创建"
else
    echo ""
    echo "✗ 下载失败"
    echo ""
    echo "备用方案："
    echo "1. 访问清华镜像: https://mirrors.tuna.tsinghua.edu.cn/"
    echo "2. 手动下载: https://foxglove.dev/download"
    echo "3. 使用Web版本: https://app.foxglove.dev/"
fi

echo ""
echo "=========================================="
echo "安装 Foxglove Bridge"
echo "=========================================="
echo ""

# 使用清华镜像
sudo sed -i 's|http://packages.ros.org|https://mirrors.tuna.tsinghua.edu.cn/ros2|g' /etc/apt/sources.list.d/ros2.list

sudo apt update
sudo apt install -y ros-humble-foxglove-bridge

echo ""
echo "✓ 安装完成"