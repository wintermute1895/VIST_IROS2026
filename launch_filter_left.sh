#!/bin/bash
# 启动左臂滤波节点

echo "=========================================="
echo "启动 左臂滤波节点"
echo "=========================================="
echo ""
echo "订阅话题: /left_arm_joint_control"
echo "发布话题: /filtered_left_joint_control"
echo ""

cd /home/ilex/Dev/VIST

python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=left
