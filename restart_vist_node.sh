#!/bin/bash
# 重启VIST Filter Node并测试话题频率

echo "=== 重启 VIST Filter Node ==="

# 1. 停止现有节点
echo "1. 停止现有节点..."
pkill -f "vist_filter_node.py"
sleep 2

# 2. Source 工作空间
echo "2. Source 工作空间..."
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash

# 3. 启动节点（后台运行）
echo "3. 启动 VIST Filter Node..."
cd /home/ilex/Dev/VIST
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_filter_node.log 2>&1 &

VIST_PID=$!
echo "   节点已启动 (PID: $VIST_PID)"

# 4. 等待节点初始化
echo "4. 等待节点初始化..."
sleep 3

# 5. 检查节点是否运行
if ps -p $VIST_PID > /dev/null; then
    echo "   ✓ 节点运行正常"
else
    echo "   ✗ 节点启动失败，查看日志: /tmp/vist_filter_node.log"
    exit 1
fi

# 6. 测试话题频率
echo ""
echo "=== 测试话题频率 ==="

echo "6. 测试 /vist_intent_factors 频率..."
timeout 3 ros2 topic hz /vist_intent_factors 2>&1 | head -3 || echo "   ⚠ 无数据"

echo ""
echo "7. 测试 /vist_performance 频率..."
timeout 3 ros2 topic hz /vist_performance 2>&1 | head -3 || echo "   ⚠ 无数据"

echo ""
echo "8. 测试 /robot1/left_arm/joint_follow 频率..."
timeout 3 ros2 topic hz /robot1/left_arm/joint_follow 2>&1 | head -3 || echo "   ⚠ 无数据"

echo ""
echo "=== 完成 ==="
echo "节点日志: /tmp/vist_filter_node.log"
echo "查看实时日志: tail -f /tmp/vist_filter_node.log"
