#!/bin/bash

echo "=========================================="
echo "启动灵巧手GUI控制程序"
echo "=========================================="

# 进入灵巧手工作空间
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros2-sdk

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo "=========================================="
echo "启动GUI控制界面"
echo "=========================================="
echo ""
echo "提示："
echo "1. 可以在GUI中选择CAN端口（can0或can1）"
echo "2. 可以测试灵巧手是否正常响应"
echo ""

# 启动GUI控制程序
ros2 launch gui_control gui_control.launch.py
