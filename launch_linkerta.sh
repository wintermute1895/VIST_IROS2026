#!/bin/bash
# 启动LinkerTA外骨骼节点

cd /home/ilex/Dev/VIST
source install/setup.bash

echo "=========================================="
echo "启动LinkerTA外骨骼节点"
echo "=========================================="
echo ""
echo "发布话题:"
echo "  /left_arm_joint_control"
echo "  /right_arm_joint_control"
echo ""

ros2 run linkerta linkerta_node