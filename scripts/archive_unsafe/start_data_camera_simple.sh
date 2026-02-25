#!/bin/bash
# 启动数据采集相机（Python直接运行方式）

echo "=========================================="
echo "启动数据采集相机"
echo "=========================================="
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未设置"
    echo "请先运行: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"
echo ""

# 直接运行Python脚本
python3 /home/ilex/Dev/VIST/scripts/run_data_camera.py
