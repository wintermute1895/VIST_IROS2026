#!/bin/bash
# 快速测试：纯视觉控制 vs 遥操臂性能对比

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== VIST 性能对比测试 ===${NC}"
echo ""
echo "测试目标："
echo "  1. 纯视觉控制（通过simulate_full_flow）"
echo "  2. 遥操臂原始数据"
echo "  3. 对比插值效果和性能指标"
echo ""

# 加载ROS2环境
source /opt/ros/humble/setup.bash
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash
fi

# 创建数据目录
mkdir -p data/comparison_tests

echo -e "${YELLOW}选择测试模式：${NC}"
echo "1. 仅测试纯视觉控制（不连接真机）"
echo "2. 仅测试遥操臂（需要连接真机）"
echo "3. 完整对比测试（需要连接真机）"
echo ""

read -p "选择模式 (1-3): " mode

case $mode in
    1)
        echo -e "${GREEN}模式1: 测试纯视觉控制${NC}"
        echo ""
        echo "步骤："
        echo "1. 启动视觉节点: python3 src/nodes/vision_node_depth.py"
        echo "2. 启动仿真: python3 scripts/experiments/simulate_full_flow.py"
        echo "3. 查看数据: ros2 topic echo /vision_control/joint_follow"
        echo ""
        echo "提示：确保已按照 docs/ADD_ROS2_TO_SIMULATION.md 修改了 simulate_full_flow.py"
        ;;

    2)
        echo -e "${GREEN}模式2: 测试遥操臂${NC}"
        echo ""
        echo "步骤："
        echo "1. 启动遥操臂: ./scripts/start_arm_teleop.sh"
        echo "2. 查看数据: ros2 topic echo /left_joint_follow"
        echo "3. 检查频率: ros2 topic hz /left_joint_follow"
        ;;

    3)
        echo -e "${GREEN}模式3: 完整对比测试${NC}"
        echo ""
        echo "这将同时运行纯视觉控制和遥操臂，并记录数据进行对比"
        echo ""

        read -p "是否继续? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi

        # 生成时间戳
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        OUTPUT_DIR="data/comparison_tests/test_${TIMESTAMP}"
        mkdir -p "$OUTPUT_DIR"

        echo -e "${BLUE}开始记录数据...${NC}"
        echo "输出目录: $OUTPUT_DIR"
        echo ""

        # 启动rosbag记录
        echo "启动rosbag记录..."
        ros2 bag record \
            /vision_control/joint_follow \
            /left_joint_follow \
            -o "$OUTPUT_DIR/rosbag" &
        ROSBAG_PID=$!

        echo "rosbag记录已启动 (PID: $ROSBAG_PID)"
        echo ""
        echo -e "${YELLOW}请在其他终端启动：${NC}"
        echo "  终端1: python3 src/nodes/vision_node_depth.py"
        echo "  终端2: python3 scripts/experiments/simulate_full_flow.py"
        echo "  终端3: ./scripts/start_arm_teleop.sh"
        echo ""
        echo "按 Ctrl+C 停止记录"

        # 等待用户停止
        trap "kill $ROSBAG_PID 2>/dev/null; echo ''; echo '记录已停止'" INT
        wait $ROSBAG_PID

        echo ""
        echo -e "${GREEN}数据记录完成！${NC}"
        echo ""
        echo "下一步："
        echo "1. 分析数据:"
        echo "   ./scripts/run_analysis.sh --rosbag $OUTPUT_DIR/rosbag --output $OUTPUT_DIR/analysis"
        echo ""
        echo "2. 查看结果:"
        echo "   ls $OUTPUT_DIR/analysis/"
        ;;

    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}提示：${NC}"
echo "- 纯视觉控制频率: ~30 Hz"
echo "- 遥操臂频率: ~241.75 Hz"
echo "- 插值目标频率: 250 Hz"
echo ""
echo "相关文档："
echo "- docs/EXISTING_NODES_INTEGRATION.md"
echo "- docs/ADD_ROS2_TO_SIMULATION.md"
echo "- docs/TRAJECTORY_COMPARISON_TEST.md"