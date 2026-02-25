#!/bin/bash
# 检查所有关键话题的频率

echo "=========================================="
echo "检查完整控制流程的频率"
echo "=========================================="
echo ""

# 加载ROS2环境
source /home/ilex/Dev/VIST/external_sdk/arm_teleop/install/setup.bash

echo "正在检查各个话题的频率（每个15秒）..."
echo ""

echo "1. linkerta原始数据:"
timeout 15s ros2 topic hz /right_arm_joint_control | grep "average rate" | tail -1
echo ""

echo "2. 左臂joint_follow命令:"
timeout 15s ros2 topic hz /robot1/left_arm/joint_follow | grep "average rate" | tail -1
echo ""

echo "3. 右臂joint_follow命令:"
timeout 15s ros2 topic hz /robot1/right_arm/joint_follow | grep "average rate" | tail -1
echo ""

echo "4. 模拟驱动状态反馈:"
timeout 15s ros2 topic hz /robot1/right_arm/joint_states | grep "average rate" | tail -1
echo ""

echo "=========================================="
echo "检查完成"
echo "=========================================="