#!/bin/bash
# 启动数据采集相机（序列号: 348122071157）

echo "=========================================="
echo "启动数据采集相机"
echo "=========================================="
echo "相机序列号: 348122071157"
echo "用途: 模仿学习数据收集"
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未设置"
    echo "请先运行: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"

# Source工作空间
if [ -f "/home/ilex/Dev/VIST/ros2_ws/install/setup.bash" ]; then
    echo "✅ 加载camera_manager工作空间"
    source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
else
    echo "⚠️  camera_manager包未构建"
    echo "请先运行: ./scripts/build_camera_manager.sh"
    exit 1
fi

echo ""

# 启动相机节点
echo "🚀 启动相机节点..."
ros2 launch camera_manager data_collection_camera.launch.py
