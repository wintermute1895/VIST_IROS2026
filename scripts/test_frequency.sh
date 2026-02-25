#!/bin/bash
# 频率测试脚本 - 不连接真机
# 测试整个数据流的频率

echo "=========================================="
echo "频率测试 - 外骨骼数据流"
echo "=========================================="
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未加载"
    echo "请先运行: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"
echo ""

# 创建临时目录存储结果
RESULT_DIR="data/frequency_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULT_DIR"

echo "📁 结果将保存到: $RESULT_DIR"
echo ""

# 函数：检查话题频率
check_topic_frequency() {
    local topic=$1
    local duration=${2:-10}
    local output_file="$RESULT_DIR/$(echo $topic | tr '/' '_').txt"

    echo "正在检查话题: $topic (持续${duration}秒)..."

    # 使用timeout确保不会永久等待
    timeout ${duration}s ros2 topic hz $topic > "$output_file" 2>&1 &
    local pid=$!

    # 等待完成
    wait $pid 2>/dev/null

    # 提取平均频率
    if [ -f "$output_file" ]; then
        local avg_rate=$(grep "average rate:" "$output_file" | tail -1 | awk '{print $3}')
        if [ -n "$avg_rate" ]; then
            echo "  ✅ 平均频率: $avg_rate Hz"
        else
            echo "  ⚠️  未检测到数据"
        fi
    fi

    echo ""
}

# 函数：列出所有活跃话题
list_active_topics() {
    echo "当前活跃的话题:"
    ros2 topic list
    echo ""
}

echo "=========================================="
echo "步骤1: 检查初始状态"
echo "=========================================="
list_active_topics

echo "=========================================="
echo "步骤2: 启动linkerta节点"
echo "=========================================="
echo "请在另一个终端运行:"
echo "  cd /home/ilex/Dev/VIST/external_sdk/arm_teleop"
echo "  source install/setup.bash"
echo "  ros2 run linkerta linkerta_node"
echo ""
read -p "按Enter继续（确认linkerta已启动）..."

echo ""
echo "等待5秒让节点稳定..."
sleep 5

list_active_topics

echo "=========================================="
echo "步骤3: 测试linkerta原始数据频率"
echo "=========================================="
check_topic_frequency "/right_arm_joint_control" 15
check_topic_frequency "/left_arm_joint_control" 15

echo "=========================================="
echo "步骤4: 启动滤波节点"
echo "=========================================="
echo "请在另一个终端运行:"
echo "  cd /home/ilex/Dev/VIST"
echo "  source /opt/ros/humble/setup.bash"
echo "  python3 src/nodes/simple_filter_node.py \\"
echo "    --ros-args \\"
echo "    -p filter_type:=one_euro \\"
echo "    -p input_topic:=/right_arm_joint_control \\"
echo "    -p output_topic:=/filtered_right_joint_control"
echo ""
read -p "按Enter继续（确认滤波节点已启动）..."

echo ""
echo "等待5秒让节点稳定..."
sleep 5

list_active_topics

echo "=========================================="
echo "步骤5: 测试滤波后数据频率"
echo "=========================================="
check_topic_frequency "/filtered_right_joint_control" 15

echo "=========================================="
echo "步骤6: 同时监控所有话题"
echo "=========================================="
echo "正在同时监控所有话题（持续20秒）..."
echo ""

# 并行监控多个话题
check_topic_frequency "/right_arm_joint_control" 20 &
check_topic_frequency "/filtered_right_joint_control" 20 &

# 等待所有后台任务完成
wait

echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo ""
echo "结果摘要:"
echo ""

# 汇总结果
for file in "$RESULT_DIR"/*.txt; do
    if [ -f "$file" ]; then
        topic=$(basename "$file" .txt | tr '_' '/')
        avg_rate=$(grep "average rate:" "$file" | tail -1 | awk '{print $3}')
        min_rate=$(grep "min:" "$file" | tail -1 | awk '{print $2}')
        max_rate=$(grep "max:" "$file" | tail -1 | awk '{print $4}')

        if [ -n "$avg_rate" ]; then
            echo "话题: $topic"
            echo "  平均: $avg_rate Hz"
            echo "  最小: $min_rate Hz"
            echo "  最大: $max_rate Hz"
            echo ""
        fi
    fi
done

echo "详细结果保存在: $RESULT_DIR"
echo ""
echo "=========================================="