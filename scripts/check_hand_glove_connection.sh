#!/bin/bash
# 检查数据手套和灵巧手的连接状态

echo "=========================================="
echo "数据手套 <-> 灵巧手 连接检查"
echo "=========================================="
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    source /opt/ros/humble/setup.bash
fi

echo "1. 检查活跃的topic..."
ros2 topic list | grep -E "(hand|glove|retarget)" || echo "未找到相关topic"
echo ""

echo "2. 检查数据手套输出topic..."
ros2 topic info /hand_joint_states 2>/dev/null || echo "数据手套topic未发布"
echo ""

echo "3. 检查灵巧手输入topic..."
ros2 topic info /linker_hand/joint_command 2>/dev/null || echo "灵巧手命令topic未找到"
echo ""

echo "4. 检查topic频率..."
echo "数据手套频率:"
timeout 3 ros2 topic hz /hand_joint_states 2>/dev/null || echo "无数据"
echo ""

echo "5. 检查节点连接..."
ros2 node list | grep -E "(hand|glove|retarget)"
echo ""

echo "=========================================="
echo "检查完成"
echo "=========================================="