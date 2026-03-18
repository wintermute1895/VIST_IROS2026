#!/bin/bash
# 最简单的连通性测试

echo "=========================================="
echo "  系统连通性测试"
echo "=========================================="
echo ""

echo "1. 检查ROS2节点"
echo "----------------------------------------"
NODES=$(ros2 node list 2>/dev/null)
echo "$NODES"
echo ""

if echo "$NODES" | grep -q "linkerta_node"; then
    echo "✓ LinkerTA节点运行中"
else
    echo "✗ LinkerTA节点未运行"
    echo ""
    echo "请先启动LinkerTA:"
    echo "  ./start_linkerta.sh"
    exit 1
fi

echo ""
echo "2. 检查话题列表"
echo "----------------------------------------"
TOPICS=$(ros2 topic list 2>/dev/null | grep -i "arm\|joint")
echo "$TOPICS"
echo ""

echo ""
echo "3. 检查话题频率（10秒）"
echo "----------------------------------------"
echo "检查 /left_arm_joint_control 频率..."
echo "（如果卡住超过5秒，按Ctrl+C）"
echo ""

timeout 10 ros2 topic hz /left_arm_joint_control 2>&1 | head -5

echo ""
echo "4. 尝试读取一条消息（10秒超时）"
echo "----------------------------------------"
echo "读取 /left_arm_joint_control ..."
echo ""

timeout 10 ros2 topic echo /left_arm_joint_control --once 2>&1 | head -20

echo ""
echo "=========================================="
echo "如果上面的命令都超时，说明LinkerTA没有发布数据"
echo "请检查："
echo "1. LinkerTA终端是否有错误"
echo "2. CAN设备是否正常: ip link show can0"
echo "3. 遥操臂是否正确连接"
echo "=========================================="
