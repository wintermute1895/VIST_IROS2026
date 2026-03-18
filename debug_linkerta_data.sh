#!/bin/bash
# LinkerTA数据源调试工具
# 用于检查遥操臂数据是否正常发布

echo "=========================================="
echo "  LinkerTA 数据源调试工具"
echo "=========================================="
echo ""

# 激活环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env

echo "1. 检查ROS2话题列表..."
echo "----------------------------------------"
ros2 topic list | grep -E "(left|right|arm|joint|linkerta)" || echo "未找到相关话题"
echo ""

echo "2. 检查LinkerTA相关话题..."
echo "----------------------------------------"
echo "所有话题:"
ros2 topic list
echo ""

read -p "请输入要监听的话题名称 (例如: /left_arm_joint_control): " TOPIC_NAME

if [ -z "$TOPIC_NAME" ]; then
    echo "未输入话题名称，使用默认: /left_arm_joint_control"
    TOPIC_NAME="/left_arm_joint_control"
fi

echo ""
echo "=========================================="
echo "  选择调试模式"
echo "=========================================="
echo "1. 查看话题信息 (类型、发布者、订阅者)"
echo "2. 查看话题频率"
echo "3. 实时监听话题数据 (原始)"
echo "4. 实时监听话题数据 (格式化)"
echo "5. 录制话题数据到文件"
echo "6. 可视化关节角度 (实时图表)"
echo ""
read -p "请选择 (1-6): " MODE

case $MODE in
    1)
        echo ""
        echo "话题信息:"
        echo "----------------------------------------"
        ros2 topic info $TOPIC_NAME -v
        ;;

    2)
        echo ""
        echo "话题频率 (按 Ctrl+C 停止):"
        echo "----------------------------------------"
        ros2 topic hz $TOPIC_NAME
        ;;

    3)
        echo ""
        echo "实时数据 (按 Ctrl+C 停止):"
        echo "----------------------------------------"
        ros2 topic echo $TOPIC_NAME
        ;;

    4)
        echo ""
        echo "格式化数据 (按 Ctrl+C 停止):"
        echo "----------------------------------------"
        ros2 topic echo $TOPIC_NAME | while read line; do
            if [[ $line == *"position:"* ]]; then
                echo "关节角度: $line"
            fi
        done
        ;;

    5)
        FILENAME="linkerta_data_$(date +%Y%m%d_%H%M%S).bag"
        echo ""
        echo "录制数据到: $FILENAME"
        echo "按 Ctrl+C 停止录制"
        echo "----------------------------------------"
        ros2 bag record -o $FILENAME $TOPIC_NAME
        ;;

    6)
        echo ""
        echo "启动实时可视化..."
        echo "----------------------------------------"
        python3 /home/ilex/Dev/VIST/monitor_linkerta_realtime.py $TOPIC_NAME
        ;;

    *)
        echo "无效选择"
        exit 1
        ;;
esac