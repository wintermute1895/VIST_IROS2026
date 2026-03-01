#!/bin/bash
# 调试脚本：检查话题数据格式

echo "========== 检查外骨骼输入话题 =========="
echo "话题: /left_arm_joint_control"
ros2 topic echo /left_arm_joint_control --once

echo ""
echo "========== 检查滤波输出话题 =========="
echo "话题: /filtered_left_joint_control"
timeout 2 ros2 topic echo /filtered_left_joint_control --once || echo "⚠️ 没有数据！"

echo ""
echo "========== 检查话题频率 =========="
echo "外骨骼输入频率:"
timeout 5 ros2 topic hz /left_arm_joint_control

echo ""
echo "滤波输出频率:"
timeout 5 ros2 topic hz /filtered_left_joint_control