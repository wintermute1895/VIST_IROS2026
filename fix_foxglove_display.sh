#!/bin/bash
# 修复Foxglove显示问题

echo "=========================================="
echo "修复 Foxglove 机器人模型显示"
echo "=========================================="
echo ""

# 1. 验证话题存在
echo "【1】验证 /robot_description 话题:"
if ros2 topic list | grep -q "/robot_description"; then
    echo "  ✓ 话题存在"

    # 查看话题类型
    echo ""
    echo "  话题类型:"
    ros2 topic info /robot_description

    # 查看话题内容（前200字符）
    echo ""
    echo "  话题内容预览:"
    timeout 2 ros2 topic echo /robot_description --once 2>/dev/null | head -c 200
    echo ""
    echo "  ..."
else
    echo "  ✗ 话题不存在"
    echo ""
    echo "  请先启动 robot_state_publisher:"
    echo "    ./start_robot_state_publisher.sh"
    exit 1
fi

echo ""
echo "=========================================="
echo "【2】检查 Foxglove Bridge 状态:"
echo "=========================================="
echo ""

if ros2 node list | grep -q "foxglove_bridge"; then
    echo "  ✓ Foxglove Bridge 正在运行"
    echo ""
    echo "  请在 Foxglove 中:"
    echo "    1. 断开连接（Disconnect）"
    echo "    2. 重新连接到 ws://localhost:8765"
    echo "    3. 打开 3D 面板"
    echo "    4. 在右侧设置中确认 URDF Topic 为 /robot_description"
else
    echo "  ✗ Foxglove Bridge 未运行"
    echo ""
    echo "  请启动 Foxglove Bridge:"
    echo "    ros2 launch foxglove_bridge foxglove_bridge_launch.xml"
fi

echo ""
echo "=========================================="
echo "【3】修复节点名称冲突:"
echo "=========================================="
echo ""

# 检查重复节点
DUPLICATE_NODES=$(ros2 node list 2>&1 | grep "WARNING.*share an exact name")
if [ -n "$DUPLICATE_NODES" ]; then
    echo "  ⚠ 发现重复节点名称"
    echo ""
    echo "  当前节点列表:"
    ros2 node list 2>/dev/null | grep -v "WARNING"
    echo ""
    echo "  建议: 停止其中一个 vist_filter_node，或者给它们不同的名称"
    echo ""
    echo "  修改方法（在启动滤波节点时）:"
    echo "    python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \\"
    echo "        --params-file config/baseline_filters_config.yaml \\"
    echo "        -p arm_side:=left \\"
    echo "        -r __node:=vist_filter_node_left  # ← 添加这行"
else
    echo "  ✓ 无节点名称冲突"
fi

echo ""
echo "=========================================="
echo "完成"
echo "=========================================="