#!/bin/bash
# 灵巧手数据手套测试脚本

echo "=========================================="
echo "测试数据手套控制灵巧手"
echo "=========================================="

# Source ROS2环境
echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash

# Source灵巧手工作空间
echo "正在加载灵巧手工作空间..."
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2
source install/setup.bash

echo ""
echo "✅ 环境已加载"
echo ""
echo "=========================================="
echo "启动灵巧手重定向节点"
echo "=========================================="
echo ""

# 启动灵巧手重定向（带校准）
ros2 launch linkerhand_retarget linkerhand_retarget.launch.py calibration:=True
