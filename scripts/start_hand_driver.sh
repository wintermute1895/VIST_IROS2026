#!/bin/bash

echo "=========================================="
echo "启动灵巧手驱动程序"
echo "=========================================="

# 检查CAN设备状态
if ! ip link show can0 &> /dev/null; then
    echo "❌ CAN设备不存在"
    exit 1
fi

CAN_STATE=$(ip link show can0 | grep -o "state [A-Z]*" | awk '{print $2}')
if [ "$CAN_STATE" != "UP" ]; then
    echo "⚠️  CAN设备未启动，正在启动..."
    sudo /usr/sbin/ip link set can0 up type can bitrate 1000000
    sleep 1
fi

echo "✅ CAN设备状态: $(ip link show can0 | grep -o 'state [A-Z]*')"
echo ""

# 进入灵巧手工作空间
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros2-sdk

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo "=========================================="
echo "启动灵巧手驱动 (左手, L10型号)"
echo "=========================================="
echo ""

# 启动灵巧手驱动
ros2 run linker_hand_ros2_sdk linker_hand_advanced_l10 \
    --hand_type left \
    --can can0 \
    --is_touch false
