#!/bin/bash
# 启动LinkerTA节点（双臂数据源）

echo "=========================================="
echo "启动 LinkerTA 节点"
echo "=========================================="
echo ""
echo "发布话题:"
echo "  - /left_arm_joint_control"
echo "  - /right_arm_joint_control"
echo ""

cd /home/ilex/Dev/VIST

# 检查CAN接口
if ! ip link show can1 > /dev/null 2>&1; then
    echo "警告: CAN1未启动，LinkerTA可能无法读取硬件数据"
    echo "      但节点仍会启动（用于测试数据流）"
fi

ros2 run linkerta linkerta_node --ros-args \
    --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml