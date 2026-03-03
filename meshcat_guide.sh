#!/bin/bash
# Meshcat机械臂可视化使用指南

echo "=========================================="
echo "Meshcat机械臂可视化测试"
echo "=========================================="
echo ""

echo "1. 基础可视化测试（静态+动画）"
echo "   python3 test_meshcat_visualization.py"
echo ""
echo "   功能："
echo "   - 加载URDF模型"
echo "   - 在Meshcat中显示机械臂"
echo "   - 播放关节运动动画"
echo "   - 在浏览器中查看（自动打开）"
echo ""

echo "2. 实时ROS2可视化"
echo "   python3 test_meshcat_realtime.py"
echo ""
echo "   功能："
echo "   - 订阅 /robot1/left_arm/joint_follow 话题"
echo "   - 实时显示机械臂状态"
echo "   - 显示更新频率"
echo ""

echo "3. 依赖安装"
echo "   pip install meshcat"
echo "   pip install pinocchio"
echo ""

echo "4. 使用提示"
echo "   - Meshcat会在浏览器中打开（通常是 http://127.0.0.1:7000/）"
echo "   - 鼠标左键：旋转视图"
echo "   - 鼠标右键：平移视图"
echo "   - 滚轮：缩放视图"
echo "   - 按Ctrl+C停止程序"
echo ""

echo "=========================================="