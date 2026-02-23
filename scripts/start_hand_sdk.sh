#!/bin/bash
# 启动L10灵巧手SDK脚本

# 设置CAN接口
echo "设置CAN接口..."
echo "39778552" | sudo -S ip link set can0 up type can bitrate 1000000

# 检查CAN接口状态
if ip link show can0 | grep -q "state UP"; then
    echo "✓ CAN接口已启动"
else
    echo "✗ CAN接口启动失败"
    exit 1
fi

# 启动手部SDK
echo "启动手部SDK..."
cd ~/Downloads/linkerhand-ros2-sdk-main
source install/setup.bash
ros2 launch linker_hand_ros2_sdk linker_hand.launch.py