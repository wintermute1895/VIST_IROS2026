#!/bin/bash
# 快速启动robot_state_publisher

echo "=========================================="
echo "启动 robot_state_publisher"
echo "=========================================="
echo ""

URDF_FILE="/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description.urdf"

if [ ! -f "$URDF_FILE" ]; then
    echo "✗ URDF文件不存在: $URDF_FILE"
    exit 1
fi

echo "✓ URDF文件存在"
echo ""
echo "正在启动 robot_state_publisher..."
echo ""

# 直接启动，不使用launch文件
ros2 run robot_state_publisher robot_state_publisher \
    --ros-args \
    -p robot_description:="$(cat $URDF_FILE)"