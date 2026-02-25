#!/bin/bash
# 测试现有节点的数据流

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 测试现有节点数据流 ===${NC}"
echo ""

# 加载ROS2环境
source /opt/ros/humble/setup.bash
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash
fi

# 创建数据目录
mkdir -p data

echo -e "${YELLOW}可用的测试模式：${NC}"
echo "1. 纯视觉控制测试"
echo "2. 仿真节点测试"
echo "3. 遥操臂测试"
echo "4. 完整对比测试（所有节点）"
echo ""

read -p "选择测试模式 (1-4): " mode

case $mode in
    1)
        echo -e "${GREEN}启动纯视觉控制测试...${NC}"
        echo ""
        echo "步骤："
        echo "1. 终端1: python3 src/nodes/vision_node_depth.py"
        echo "2. 终端2: python3 scripts/ros2_adapters.py vision"
        echo "3. 终端3: ros2 topic echo /vision_control/joint_follow"
        ;;

    2)
        echo -e "${GREEN}启动仿真节点测试...${NC}"
        echo ""
        echo "步骤："
        echo "1. 终端1: python3 scripts/replay_in_simulation.py <rosbag_path>"
        echo "2. 终端2: python3 scripts/ros2_adapters.py simulation"
        echo "3. 终端3: ros2 topic echo /simulation/joint_follow"
        ;;

    3)
        echo -e "${GREEN}启动遥操臂测试...${NC}"
        echo ""
        echo "步骤："
        echo "1. 终端1: ./scripts/start_arm_teleop.sh"
        echo "2. 终端2: python3 scripts/ros2_adapters.py exo"
        echo "3. 终端3: ros2 topic echo /exo_control/joint_follow"
        ;;

    4)
        echo -e "${GREEN}启动完整对比测试...${NC}"
        echo ""
        echo "这将启动所有节点并记录数据"
        echo ""

        # 询问是否自动启动
        read -p "是否自动启动所有节点? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}启动数据记录...${NC}"

            # 启动rosbag记录
            ros2 bag record \
                /vision_control/joint_follow \
                /simulation/joint_follow \
                /exo_control/joint_follow \
                -o data/comparison_test &
            ROSBAG_PID=$!

            echo "rosbag记录已启动 (PID: $ROSBAG_PID)"
            echo "按Ctrl+C停止记录"

            # 等待用户停止
            trap "kill $ROSBAG_PID; echo '记录已停止'" INT
            wait $ROSBAG_PID
        fi
        ;;

    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}提示：${NC}"
echo "- 确保所有节点输出的数据单位一致（弧度）"
echo "- 使用 ros2 topic hz <topic> 检查频率"
echo "- 使用 ros2 topic echo <topic> 查看数据"