#!/bin/bash
# LinkerTA 遥操臂启动脚本
# 用于快速启动LinkerTA驱动节点

echo "=========================================="
echo "  LinkerTA 遥操臂启动工具"
echo "=========================================="
echo ""

# 项目根目录
PROJECT_ROOT="/home/ilex/Dev/VIST"
cd "$PROJECT_ROOT"

# 激活conda环境
echo "1. 激活conda环境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo "2. 设置ROS2环境..."
    source /opt/ros/humble/setup.bash
else
    echo "2. ROS2环境已设置: $ROS_DISTRO"
fi

# Source工作空间
echo "3. Source ROS2工作空间..."
if [ -f "ros2_ws/install/setup.bash" ]; then
    source ros2_ws/install/setup.bash
    echo "   ✓ 工作空间已source"
else
    echo "   ⚠️  工作空间未编译，尝试编译..."
    cd ros2_ws
    colcon build --packages-select linkerta
    source install/setup.bash
    cd ..
fi

echo ""
echo "=========================================="
echo "  启动前检查"
echo "=========================================="

# 检查CAN设备
echo ""
echo "4. 检查CAN设备..."
if ip link show can0 &>/dev/null || ip link show can1 &>/dev/null; then
    echo "   ✓ CAN设备已找到"
    ip link show can0 2>/dev/null || true
    ip link show can1 2>/dev/null || true
else
    echo "   ⚠️  未找到CAN设备"
    echo ""
    echo "   需要启动CAN设备，请选择："
    echo "   1. 启动 can0 (1000000 波特率)"
    echo "   2. 启动 can1 (1000000 波特率)"
    echo "   3. 跳过（已手动启动）"
    echo ""
    read -p "   请选择 (1-3): " can_choice

    case $can_choice in
        1)
            echo "   启动 can0..."
            sudo ip link set can0 up type can bitrate 1000000
            if [ $? -eq 0 ]; then
                echo "   ✓ can0 已启动"
            else
                echo "   ✗ can0 启动失败"
                exit 1
            fi
            ;;
        2)
            echo "   启动 can1..."
            sudo ip link set can1 up type can bitrate 1000000
            if [ $? -eq 0 ]; then
                echo "   ✓ can1 已启动"
            else
                echo "   ✗ can1 启动失败"
                exit 1
            fi
            ;;
        3)
            echo "   跳过CAN设备启动"
            ;;
        *)
            echo "   无效选择"
            exit 1
            ;;
    esac
fi

echo ""
echo "=========================================="
echo "  启动选项"
echo "=========================================="
echo "1. 启动LinkerTA (双臂一体设备)"
echo "2. 使用launch文件启动"
echo "3. 查看LinkerTA配置"
echo ""
read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo ""
        echo "=========================================="
        echo "  启动LinkerTA双臂遥操节点"
        echo "=========================================="
        echo ""
        echo "注意：LinkerTA是双臂一体设备"
        echo "一个节点会同时发布左右臂数据："
        echo "  - /left_arm_joint_control"
        echo "  - /right_arm_joint_control"
        echo ""
        echo "启动中..."
        ros2 run linkerta linkerta_node --ros-args \
            --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml
        ;;

    2)
        echo ""
        echo "使用launch文件启动..."
        ros2 launch linkerta run.launch.py
        ;;

    3)
        echo ""
        echo "LinkerTA配置文件:"
        echo "----------------------------------------"
        cat ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml
        echo ""
        echo "配置文件路径:"
        echo "  ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml"
        ;;

    *)
        echo "无效选择"
        exit 1
        ;;
esac