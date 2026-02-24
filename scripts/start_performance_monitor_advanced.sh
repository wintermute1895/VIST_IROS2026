#!/bin/bash

echo "=========================================="
echo "ROS2性能监控工具（扩展版）"
echo "=========================================="

# 进入工作空间
cd /home/ilex/Dev/VIST

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo "=========================================="
echo "启动扩展性能监控"
echo "=========================================="
echo ""
echo "监控指标："
echo "  ✓ 频率监控"
echo "  ✓ 延迟测量"
echo "  ✓ 速度计算"
echo "  ✓ 加速度计算"
echo "  ✓ Jerk计算"
echo "  ✓ 丢包检测"
echo "  ✓ 同步性评估"
echo "  ✓ 稳定性分析"
echo ""
echo "监控话题: /cb_left_hand_control_cmd"
echo "输出文件: performance_log_advanced.csv"
echo "统计间隔: 5秒"
echo ""
echo "按Ctrl+C停止监控"
echo ""

# 启动扩展性能监控节点
ros2 launch performance_monitor performance_monitor_advanced.launch.py \
    input_topic:=/cb_left_hand_control_cmd \
    output_file:=performance_log_advanced.csv
