#!/bin/bash
# 安装 PlotJuggler

echo "=========================================="
echo "安装 PlotJuggler"
echo "=========================================="
echo ""

sudo apt update
sudo apt install -y ros-humble-plotjuggler-ros

echo ""
echo "✓ 安装完成"
echo ""
echo "使用方法:"
echo "  ros2 run plotjuggler plotjuggler"
echo ""
echo "功能:"
echo "  - 实时绘制关节角度曲线"
echo "  - 对比原始数据和滤波后数据"
echo "  - 分析数据频率和延迟"
echo ""