#!/bin/bash
# LBot遥操作快速启动脚本

echo "=========================================="
echo "LBot遥操作系统启动"
echo "=========================================="

# 检查IP地址
echo "检查网络配置..."
IP=$(ip addr show enp3s0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d'/' -f1)

if [ "$IP" != "192.168.10.100" ]; then
    echo "⚠️  警告: 当前IP不是192.168.10.100"
    echo "当前IP: $IP"
    echo "请先设置IP地址："
    echo "sudo nmcli con add type ethernet ifname enp3s0 con-name lbot-network ip4 192.168.10.100/24"
    echo "sudo nmcli con up lbot-network"
    exit 1
fi

echo "✅ IP地址正确: $IP"

# 进入工作空间
cd /home/ilex/Dev/VIST/src/robot/sdk/arm_teleop

# Source环境
echo "加载ROS2环境..."
source install/setup.bash

# 启动
echo "启动遥操作系统..."
echo "=========================================="
ros2 launch lbot_teleop teleop.launch.py