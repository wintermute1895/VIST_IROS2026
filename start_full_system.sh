#!/bin/bash
# 双臂遥操作完整系统启动脚本
# 按顺序启动所有必要的节点

echo "=========================================="
echo "  双臂遥操作完整系统启动"
echo "=========================================="
echo ""

# 项目根目录
PROJECT_ROOT="/home/ilex/Dev/VIST"
cd "$PROJECT_ROOT"

# 激活环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
source /opt/ros/humble/setup.bash 2>/dev/null || true

# 检查LinkerTA是否已启动
echo "1. 检查LinkerTA节点..."
if ros2 node list 2>/dev/null | grep -q "linkerta_node"; then
    echo "   ✓ LinkerTA节点已运行"
else
    echo "   ✗ LinkerTA节点未运行"
    echo ""
    echo "   请先启动LinkerTA:"
    echo "   ./start_linkerta.sh"
    echo ""
    exit 1
fi

# 检查话题频率
echo ""
echo "2. 检查LinkerTA话题频率..."
LEFT_HZ=$(timeout 3 ros2 topic hz /left_arm_joint_control 2>&1 | grep "average rate" | awk '{print $3}')
if [ -n "$LEFT_HZ" ]; then
    echo "   ✓ /left_arm_joint_control: ${LEFT_HZ} Hz"
else
    echo "   ⚠️  无法检测到左臂数据"
fi

RIGHT_HZ=$(timeout 3 ros2 topic hz /right_arm_joint_control 2>&1 | grep "average rate" | awk '{print $3}')
if [ -n "$RIGHT_HZ" ]; then
    echo "   ✓ /right_arm_joint_control: ${RIGHT_HZ} Hz"
else
    echo "   ⚠️  无法检测到右臂数据"
fi

echo ""
echo "=========================================="
echo "  启动滤波节点和可视化"
echo "=========================================="
echo ""

# 启动左臂滤波节点
echo "3. 启动左臂滤波节点..."
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=left &
LEFT_FILTER_PID=$!
echo "   ✓ 左臂滤波节点已启动 (PID: $LEFT_FILTER_PID)"

sleep 2

# 启动右臂滤波节点
echo ""
echo "4. 启动右臂滤波节点..."
python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
    --params-file config/baseline_filters_config.yaml \
    -p arm_side:=right &
RIGHT_FILTER_PID=$!
echo "   ✓ 右臂滤波节点已启动 (PID: $RIGHT_FILTER_PID)"

sleep 3

# 检查滤波节点是否正常
echo ""
echo "5. 检查滤波节点状态..."
if ros2 node list 2>/dev/null | grep -q "vist_filter_node"; then
    echo "   ✓ 滤波节点运行正常"
    ros2 node list | grep vist_filter
else
    echo "   ✗ 滤波节点启动失败"
    kill $LEFT_FILTER_PID $RIGHT_FILTER_PID 2>/dev/null
    exit 1
fi

# 检查滤波后的话题
echo ""
echo "6. 检查滤波后的话题..."
if ros2 topic list 2>/dev/null | grep -q "filtered_left_joint_control"; then
    echo "   ✓ /filtered_left_joint_control"
fi
if ros2 topic list 2>/dev/null | grep -q "filtered_right_joint_control"; then
    echo "   ✓ /filtered_right_joint_control"
fi

# 启动双臂可视化
echo ""
echo "7. 启动双臂可视化..."
python3 visualize_dual_arm_realtime.py &
VIZ_PID=$!
echo "   ✓ 可视化节点已启动 (PID: $VIZ_PID)"

sleep 3

echo ""
echo "=========================================="
echo "  系统启动完成！"
echo "=========================================="
echo ""
echo "运行中的节点:"
echo "  - LinkerTA节点 (已存在)"
echo "  - 左臂滤波节点 (PID: $LEFT_FILTER_PID)"
echo "  - 右臂滤波节点 (PID: $RIGHT_FILTER_PID)"
echo "  - 双臂可视化 (PID: $VIZ_PID)"
echo ""
echo "话题数据流:"
echo "  LinkerTA → /left_arm_joint_control (80Hz)"
echo "           → /right_arm_joint_control (80Hz)"
echo "  滤波节点 → /filtered_left_joint_control (80Hz)"
echo "           → /filtered_right_joint_control (80Hz)"
echo "  可视化   ← 订阅滤波后的话题"
echo ""
echo "📊 在浏览器中查看双臂运动:"
echo "   http://127.0.0.1:7000/static/"
echo ""
echo "🎮 现在移动遥操臂，观察仿真中的双臂运动！"
echo ""
echo "按 Ctrl+C 停止所有节点"
echo "=========================================="

# 等待用户中断
trap "echo ''; echo '停止所有节点...'; kill $LEFT_FILTER_PID $RIGHT_FILTER_PID $VIZ_PID 2>/dev/null; echo '✓ 已停止'; exit" INT
wait