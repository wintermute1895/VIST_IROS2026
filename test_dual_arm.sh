#!/bin/bash
# 双臂遥操作测试脚本
# 用于快速启动和测试双臂系统

echo "=========================================="
echo "  双臂遥操作系统测试脚本"
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

echo ""
echo "=========================================="
echo "  启动选项"
echo "=========================================="
echo "1. 启动双臂滤波节点（手动）"
echo "2. 启动双臂滤波节点（launch文件）"
echo "3. 启动双臂可视化"
echo "4. 查看话题列表"
echo "5. 测试左臂话题"
echo "6. 测试右臂话题"
echo "7. 完整测试（滤波+可视化）"
echo ""
read -p "请选择 (1-7): " choice

case $choice in
    1)
        echo ""
        echo "启动左臂滤波节点..."
        python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
            --params-file config/baseline_filters_config.yaml \
            -p arm_side:=left &
        LEFT_PID=$!

        sleep 2

        echo "启动右臂滤波节点..."
        python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
            --params-file config/baseline_filters_config.yaml \
            -p arm_side:=right &
        RIGHT_PID=$!

        echo ""
        echo "双臂滤波节点已启动"
        echo "  左臂 PID: $LEFT_PID"
        echo "  右臂 PID: $RIGHT_PID"
        echo ""
        echo "按 Ctrl+C 停止"

        # 等待用户中断
        trap "kill $LEFT_PID $RIGHT_PID 2>/dev/null; exit" INT
        wait
        ;;

    2)
        echo ""
        echo "使用launch文件启动双臂滤波节点..."
        ros2 launch ros2_ws/launch/dual_arm_teleop.launch.py
        ;;

    3)
        echo ""
        echo "启动双臂可视化..."
        python3 visualize_dual_arm_realtime.py
        ;;

    4)
        echo ""
        echo "当前ROS2话题列表:"
        ros2 topic list
        echo ""
        echo "双臂相关话题:"
        ros2 topic list | grep -E "(left|right)_arm"
        ;;

    5)
        echo ""
        echo "测试左臂话题..."
        echo "发布测试数据到 /left_arm_joint_control"
        ros2 topic pub --once /left_arm_joint_control sensor_msgs/msg/JointState \
            "{position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

        echo ""
        echo "监听滤波后的左臂数据 (按 Ctrl+C 停止):"
        ros2 topic echo /filtered_left_joint_control
        ;;

    6)
        echo ""
        echo "测试右臂话题..."
        echo "发布测试数据到 /right_arm_joint_control"
        ros2 topic pub --once /right_arm_joint_control sensor_msgs/msg/JointState \
            "{position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

        echo ""
        echo "监听滤波后的右臂数据 (按 Ctrl+C 停止):"
        ros2 topic echo /filtered_right_joint_control
        ;;

    7)
        echo ""
        echo "=========================================="
        echo "  完整测试流程"
        echo "=========================================="
        echo ""
        echo "步骤1: 启动双臂滤波节点..."
        python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
            --params-file config/baseline_filters_config.yaml \
            -p arm_side:=left &
        LEFT_PID=$!

        python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \
            --params-file config/baseline_filters_config.yaml \
            -p arm_side:=right &
        RIGHT_PID=$!

        sleep 3

        echo ""
        echo "步骤2: 启动双臂可视化..."
        python3 visualize_dual_arm_realtime.py &
        VIZ_PID=$!

        sleep 2

        echo ""
        echo "=========================================="
        echo "  系统已启动"
        echo "=========================================="
        echo "  左臂滤波节点 PID: $LEFT_PID"
        echo "  右臂滤波节点 PID: $RIGHT_PID"
        echo "  可视化节点 PID: $VIZ_PID"
        echo ""
        echo "  在浏览器中打开 Meshcat 查看双臂运动"
        echo "  URL: http://127.0.0.1:7000/static/"
        echo ""
        echo "  按 Ctrl+C 停止所有节点"
        echo "=========================================="

        # 等待用户中断
        trap "kill $LEFT_PID $RIGHT_PID $VIZ_PID 2>/dev/null; exit" INT
        wait
        ;;

    *)
        echo "无效选择"
        exit 1
        ;;
esac