#!/bin/bash
# 启动数据采集相机 - 最终版本
# 使用Python直接运行，但保持完整的ROS2功能

echo "=========================================="
echo "启动数据采集相机"
echo "=========================================="
echo "相机序列号: 348122071157"
echo "用途: 模仿学习数据收集"
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未设置"
    echo "请先运行: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"
echo ""

# 设置Python路径
export PYTHONPATH=/home/ilex/Dev/VIST/src/camera_manager:$PYTHONPATH

# 运行节点，使用ros-args设置参数
python3 -c "
import sys
sys.path.insert(0, '/home/ilex/Dev/VIST/src/camera_manager')

import rclpy
from camera_manager.realsense_camera_node import RealSenseCameraNode

rclpy.init(args=sys.argv)
node = RealSenseCameraNode()

print('✅ 节点已启动')
print('发布话题:')
print('  - /data_camera/color/image_raw')
print('  - /data_camera/depth/image_rect_raw')
print('')
print('按 Ctrl+C 停止')
print('')

try:
    rclpy.spin(node)
except KeyboardInterrupt:
    print('\\n停止节点...')
finally:
    node.destroy_node()
    rclpy.shutdown()
" --ros-args \
    -p serial_number:=\"348122071157\" \
    -p camera_name:=\"data_camera\" \
    -p camera_id:=1 \
    -p color_width:=848 \
    -p color_height:=480 \
    -p color_fps:=30 \
    -p depth_width:=848 \
    -p depth_height:=480 \
    -p depth_fps:=30 \
    -p enable_color:=true \
    -p enable_depth:=true \
    -p enable_pointcloud:=false \
    -p enable_imu:=false \
    -p align_depth_to_color:=true
