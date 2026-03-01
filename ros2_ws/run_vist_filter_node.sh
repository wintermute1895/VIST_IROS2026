#!/bin/bash
# VIST Filter Node 启动脚本
# 确保只有一个实例运行

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "VIST Filter Node 启动脚本"
echo "=========================================="

# 1. 检查并杀掉旧的进程
echo "1. 检查旧进程..."
OLD_PIDS=$(ps aux | grep "vist_filter_node.py" | grep -v grep | awk '{print $2}' || true)
if [ -n "$OLD_PIDS" ]; then
    echo "   发现旧进程: $OLD_PIDS"
    echo "   正在杀掉旧进程..."
    kill -9 $OLD_PIDS 2>/dev/null || true
    sleep 2
    echo "   ✅ 旧进程已清理"
else
    echo "   ✅ 没有旧进程"
fi

# 2. 等待 ROS2 清理节点
echo "2. 等待 ROS2 清理节点..."
sleep 2

# 3. 检查节点是否还在 ROS2 图中
NODE_COUNT=$(ros2 node list 2>/dev/null | grep -c "vist_filter_node" || echo "0")
if [ "$NODE_COUNT" != "0" ]; then
    echo "   ⚠️  警告: ROS2 图中仍有 $NODE_COUNT 个 vist_filter_node 节点"
    echo "   等待 5 秒让 ROS2 清理..."
    sleep 5
fi

# 4. 启动新节点
echo "3. 启动新节点..."
echo "   配置文件: ../config/baseline_filters_config.yaml"
echo "=========================================="
echo ""

python3 src/nodes/vist_filter_node.py --ros-args --params-file ../config/baseline_filters_config.yaml