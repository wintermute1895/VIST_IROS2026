#!/bin/bash
# 启动右臂滤波节点（带唯一名称）

echo "=========================================="
echo "启动 右臂滤波节点（唯一名称）"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=right \
    -r __node:=vist_filter_node_right
