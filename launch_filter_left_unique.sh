#!/bin/bash
# 启动左臂滤波节点

cd /home/ilex/Dev/VIST/ros2_ws
source install/setup.bash

echo "=========================================="
echo "启动左臂滤波节点"
echo "=========================================="
echo ""
echo "订阅: /left_arm_joint_control"
echo "发布: /filtered_left_joint_control"
echo ""

ros2 run vist_filter vist_filter_node --ros-args \
  -r __node:=vist_filter_node_left \
  -p arm_side:=left \
  -p config_file:=/home/ilex/Dev/VIST/config/baseline_filters_config.yaml