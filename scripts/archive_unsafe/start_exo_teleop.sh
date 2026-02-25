#!/bin/bash
# 外骨骼+数据手套遥操作启动脚本

echo "=========================================="
echo "启动外骨骼+数据手套遥操作系统"
echo "=========================================="

# Source ROS2环境
source /opt/ros/humble/setup.bash

# Source机械臂工作空间
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash

# Source灵巧手工作空间
cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2
source install/setup.bash

echo ""
echo "环境已加载，请在不同终端中运行："
echo ""
echo "终端1 - 机械臂外骨骼："
echo "  ros2 launch lbot_teleop teleop_exo.launch.py"
echo ""
echo "终端2 - 灵巧手数据手套："
echo "  ros2 launch linkerhand_retarget linkerhand_retarget.launch.py"
echo ""
echo "终端3 - 数据记录（可选）："
echo "  ros2 bag record -a"
echo ""
echo "=========================================="
