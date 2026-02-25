#!/bin/bash
# 启动数据采集相机 - 完整版本（自动激活环境）
# 相机序列号: 348122071157
# 用途: 模仿学习数据收集

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🎥 启动数据采集相机"
echo "=========================================="
echo "相机序列号: 348122071157"
echo "用途: 模仿学习数据收集"
echo ""

# 1. 激活conda环境
echo "📦 激活ros2_env环境..."
source ~/miniforge3/etc/profile.d/conda.sh
conda activate ros2_env

# 2. 激活ROS2环境
echo "🤖 激活ROS2 Humble环境..."
source /opt/ros/humble/setup.bash

# 3. 检查环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未设置"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"
echo "✅ Python: $(python3 --version)"
echo "✅ NumPy: $(python3 -c 'import numpy; print(numpy.__version__)')"
echo ""

# 4. 设置Python路径
export PYTHONPATH=/home/ilex/Dev/VIST/src/camera_manager:$PYTHONPATH

# 5. 启动相机节点
echo "🚀 启动相机节点..."
echo ""

python3 -c "
import sys
sys.path.insert(0, '/home/ilex/Dev/VIST/src/camera_manager')

import rclpy
from camera_manager.realsense_camera_node import RealSenseCameraNode

rclpy.init(args=sys.argv)
node = RealSenseCameraNode()

print('✅ 节点已启动')
print('📡 发布话题:')
print('  - /data_camera/color/image_raw')
print('  - /data_camera/depth/image_rect_raw')
print('  - /data_camera/camera_info')
print('')
print('💡 提示:')
print('  - 查看话题: ros2 topic list')
print('  - 查看图像: ros2 run rqt_image_view rqt_image_view')
print('  - 录制数据: ros2 bag record -a')
print('')
print('⏹️  按 Ctrl+C 停止')
print('')

try:
    rclpy.spin(node)
except KeyboardInterrupt:
    print('\n⏹️  停止节点...')
finally:
    node.destroy_node()
    rclpy.shutdown()
    print('✅ 节点已关闭')
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
