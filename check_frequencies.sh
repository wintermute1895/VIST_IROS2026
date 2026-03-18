#!/bin/bash
# 对比LinkerTA原始频率和滤波后频率

echo "=========================================="
echo "  频率对比监控"
echo "=========================================="
echo ""

echo "监控LinkerTA原始输出频率..."
echo "话题: /left_arm_joint_control"
echo "预期: ~160 Hz"
echo ""
ros2 topic hz /left_arm_joint_control &
PID1=$!

sleep 2

echo ""
echo "=========================================="
echo ""
echo "监控滤波节点输出频率..."
echo "话题: /filtered_left_joint_control"
echo "预期: ~80 Hz"
echo ""
ros2 topic hz /filtered_left_joint_control &
PID2=$!

echo ""
echo "按 Ctrl+C 停止监控"
trap "kill $PID1 $PID2 2>/dev/null; exit" INT
wait