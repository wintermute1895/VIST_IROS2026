#!/bin/bash
# VIST 话题频率诊断脚本

echo "=========================================="
echo "VIST 话题频率诊断"
echo "=========================================="
echo ""

# Source 工作空间
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash

# 1. 检查节点状态
echo "1. 检查 ROS2 节点状态"
echo "----------------------------------------"
ros2 node list | grep -E "(vist|lbot)" || echo "未找到相关节点"
echo ""

# 2. 检查话题列表
echo "2. 检查话题列表"
echo "----------------------------------------"
echo "VIST 相关话题:"
ros2 topic list | grep -E "(vist|joint_follow)" || echo "未找到相关话题"
echo ""

# 3. 检查话题信息
echo "3. 检查话题详细信息"
echo "----------------------------------------"

echo "3.1 /vist_intent_factors:"
ros2 topic info /vist_intent_factors 2>&1 || echo "   话题不存在"
echo ""

echo "3.2 /vist_performance:"
ros2 topic info /vist_performance 2>&1 || echo "   话题不存在"
echo ""

echo "3.3 /robot1/left_arm/joint_follow:"
ros2 topic info /robot1/left_arm/joint_follow 2>&1 || echo "   话题不存在"
echo ""

# 4. 测试话题频率
echo "4. 测试话题频率 (3秒采样)"
echo "----------------------------------------"

echo "4.1 /vist_intent_factors 频率:"
timeout 3 ros2 topic hz /vist_intent_factors 2>&1 | head -2 || echo "   ⚠ 无数据发布"
echo ""

echo "4.2 /vist_performance 频率:"
timeout 3 ros2 topic hz /vist_performance 2>&1 | head -2 || echo "   ⚠ 无数据发布"
echo ""

echo "4.3 /robot1/left_arm/joint_follow 频率:"
timeout 3 ros2 topic hz /robot1/left_arm/joint_follow 2>&1 | head -2 || echo "   ⚠ 无数据发布"
echo ""

# 5. 检查消息内容
echo "5. 检查话题消息内容 (单次采样)"
echo "----------------------------------------"

echo "5.1 /vist_intent_factors 内容:"
timeout 2 ros2 topic echo /vist_intent_factors --once 2>&1 || echo "   ⚠ 无法获取消息"
echo ""

echo "5.2 /vist_performance 内容:"
timeout 2 ros2 topic echo /vist_performance --once 2>&1 || echo "   ⚠ 无法获取消息"
echo ""

# 6. 诊断建议
echo "=========================================="
echo "诊断建议"
echo "=========================================="
echo ""
echo "如果话题显示 'unknown' 频率:"
echo "  1. 确保已 source 工作空间: source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash"
echo "  2. 确保 VIST Filter Node 正在运行"
echo "  3. 确保使用 'vist' 滤波器类型（不是 'gello'）"
echo "  4. 重启 rqt: ./start_rqt.sh"
echo ""
echo "如果 joint_follow 显示 'invalid message type':"
echo "  1. 在启动 rqt 前 source 工作空间"
echo "  2. 使用提供的脚本: ./start_rqt.sh"
echo ""
