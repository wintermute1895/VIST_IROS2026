#!/bin/bash
# 快速测试 VIST 话题发布

echo "=== 快速测试 VIST 话题 ==="

# Source 工作空间
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash

# 停止并重启节点
echo "1. 重启 VIST Filter Node..."
pkill -f "vist_filter_node.py"
sleep 2

cd /home/ilex/Dev/VIST
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_test.log 2>&1 &

echo "   等待节点启动..."
sleep 3

# 测试话题
echo ""
echo "2. 测试话题频率 (5秒采样)..."
echo ""

echo "   /vist_intent_factors:"
timeout 5 ros2 topic hz /vist_intent_factors 2>&1 | head -3 &
PID1=$!

echo "   /vist_performance:"
timeout 5 ros2 topic hz /vist_performance 2>&1 | head -3 &
PID2=$!

echo "   /robot1/left_arm/joint_follow:"
timeout 5 ros2 topic hz /robot1/left_arm/joint_follow 2>&1 | head -3 &
PID3=$!

# 等待所有测试完成
wait $PID1 $PID2 $PID3

echo ""
echo "3. 查看节点日志 (最后20行):"
echo "----------------------------------------"
tail -20 /tmp/vist_test.log

echo ""
echo "=== 测试完成 ==="
echo "完整日志: /tmp/vist_test.log"
