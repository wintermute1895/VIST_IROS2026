#!/bin/bash
# CAN 接口设置脚本

echo "正在设置 CAN 接口..."

# 启动 can0 接口
sudo ip link set can0 up type can bitrate 1000000

# 设置权限
sudo chmod 0666 /sys/class/net/can0/tx_queue_len

# 检查状态
ip link show can0

echo "CAN 接口设置完成！"