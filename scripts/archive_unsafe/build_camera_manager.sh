#!/bin/bash
# 构建camera_manager ROS2包

echo "=========================================="
echo "构建 camera_manager ROS2 包"
echo "=========================================="
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "❌ ROS2环境未设置"
    echo "请先运行: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo "✅ ROS2环境: $ROS_DISTRO"
echo ""

# 进入VIST目录
cd /home/ilex/Dev/VIST

# 创建ROS2工作空间（如果不存在）
if [ ! -d "ros2_ws" ]; then
    echo "📁 创建ROS2工作空间..."
    mkdir -p ros2_ws/src
fi

# 创建符号链接到camera_manager包
echo "🔗 创建符号链接..."
if [ ! -L "ros2_ws/src/camera_manager" ]; then
    ln -s /home/ilex/Dev/VIST/src/camera_manager ros2_ws/src/camera_manager
    echo "   ✅ 链接创建成功"
else
    echo "   ℹ️  链接已存在"
fi

# 进入工作空间
cd ros2_ws

# 构建包
echo ""
echo "🔨 构建包..."
colcon build --packages-select camera_manager --symlink-install

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ 构建成功！"
    echo "=========================================="
    echo ""
    echo "请运行以下命令设置环境:"
    echo "  source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash"
    echo ""
    echo "然后可以启动数据采集相机:"
    echo "  ./scripts/start_data_camera.sh"
else
    echo ""
    echo "=========================================="
    echo "❌ 构建失败"
    echo "=========================================="
    exit 1
fi
