#!/bin/bash
# 动态修改滤波节点的话题订阅

echo "修改滤波节点话题配置..."

# 修改输入话题
ros2 param set /vist_filter_node exo_left_topic /left_arm_joint_control
ros2 param set /vist_filter_node exo_right_topic /right_arm_joint_control

echo "✓ 配置已更新"
echo ""
echo "注意：某些节点可能需要重启才能应用新的话题订阅"
echo "建议重启滤波节点以确保配置生效"