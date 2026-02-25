#!/bin/bash
# 测试数据采集相机话题

echo "=========================================="
echo "数据采集相机话题测试"
echo "=========================================="
echo ""

echo "📋 检查相机话题..."
echo ""

# 检查话题列表
echo "1️⃣ 可用话题:"
ros2 topic list | grep data_collection

echo ""
echo "2️⃣ 彩色图像话题信息:"
ros2 topic info /data_collection/data_camera/color/image_raw

echo ""
echo "3️⃣ 深度图像话题信息:"
ros2 topic info /data_collection/data_camera/depth/image_rect_raw

echo ""
echo "4️⃣ 查看一帧彩色图像数据:"
ros2 topic echo /data_collection/data_camera/color/image_raw --once

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
