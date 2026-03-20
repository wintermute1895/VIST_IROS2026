#!/bin/bash
# 启动遥操桥接节点

cd /home/ilex/Dev/VIST
source install/setup.bash

echo "=========================================="
echo "启动遥操桥接节点"
echo "=========================================="
echo ""
echo "订阅: /filtered_left_joint_control"
echo "订阅: /filtered_right_joint_control"
echo "发布: /robot1/left_arm/joint_follow"
echo "发布: /robot1/right_arm/joint_follow"
echo ""

ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml