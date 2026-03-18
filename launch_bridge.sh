#!/bin/bash
# 启动遥操桥接节点

echo "=========================================="
echo "启动 遥操桥接节点"
echo "=========================================="
echo ""
echo "订阅话题:"
echo "  - /filtered_left_joint_control"
echo "  - /filtered_right_joint_control"
echo ""
echo "发布话题:"
echo "  - /robot1/left_arm/joint_follow"
echo "  - /robot1/right_arm/joint_follow"
echo ""

cd /home/ilex/Dev/VIST

# 先检查配置
BRIDGE_CONFIG="ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml"
ENABLE_RIGHT=$(grep "enable_right_arm:" "$BRIDGE_CONFIG" | awk '{print $2}')

if [ "$ENABLE_RIGHT" == "false" ]; then
    echo "警告: 右臂未启用 (enable_right_arm: false)"
    echo "      只会处理左臂数据"
fi

ros2 run lbot_teleop teleop_bridge_node --ros-args \
    --params-file "$BRIDGE_CONFIG"
