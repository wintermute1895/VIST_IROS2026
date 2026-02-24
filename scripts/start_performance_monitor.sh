#!/bin/bash

echo "=========================================="
echo "ROS2性能监控工具"
echo "=========================================="

# 进入工作空间
cd /home/ilex/Dev/VIST

echo "正在加载ROS2环境..."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo ""
echo "=========================================="
echo "启动性能监控"
echo "=========================================="
echo ""
echo "监控话题: /cb_left_hand_control_cmd"
echo "输出文件: performance_log.csv"
echo "统计间隔: 5秒"
echo ""
echo "按Ctrl+C停止监控"
echo ""

# 启动性能监控节点
ros2 launch performance_monitor performance_monitor.launch.py \
    input_topic:=/cb_left_hand_control_cmd \
    output_file:=performance_log.csv \
    print_interval:=5.0
