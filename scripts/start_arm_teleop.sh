#!/bin/bash

echo "=========================================="
echo "启动遥操臂控制系统"
echo "=========================================="

# 进入遥操臂工作空间
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo "=========================================="
echo "系统配置"
echo "=========================================="
echo "主臂（遥操臂）: Linkerta"
echo "从臂（机械臂）: LBot"
echo "配置文件: config/teleop_config.yaml"
echo ""
echo "启动顺序:"
echo "  1. lbot_driver (从臂驱动)"
echo "  2. linkerta (主臂驱动)"
echo "  3. teleop_bridge (桥接节点)"
echo ""
echo "按Ctrl+C停止所有节点"
echo ""

# 启动遥操作系统
ros2 launch lbot_teleop teleop.launch.py
