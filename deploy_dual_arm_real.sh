#!/bin/bash
# 真机部署启动脚本（双臂版本）
# 基于 docs/WORKFLOW_ANALYSIS.md 的工作流程

set -e

echo "=========================================="
echo "VIST 双臂真机部署启动"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查函数
check_step() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        exit 1
    fi
}

# 步骤1: 检查CAN接口
echo "【步骤1】检查CAN接口..."
ip link show can0 > /dev/null 2>&1
check_step "CAN0 (灵巧手)"
ip link show can1 > /dev/null 2>&1
check_step "CAN1 (外骨骼)"
echo ""

# 步骤2: 启动滤波节点（双臂）
echo "【步骤2】启动VIST滤波节点（双臂）..."
echo -e "${YELLOW}提示: 请在新终端中运行以下命令${NC}"
echo ""
echo "  # 左臂滤波节点"
echo "  python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \\"
echo "      --params-file config/baseline_filters_config.yaml \\"
echo "      -p arm_side:=left"
echo ""
echo "  # 右臂滤波节点"
echo "  python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \\"
echo "      --params-file config/baseline_filters_config.yaml \\"
echo "      -p arm_side:=right"
echo ""
read -p "按Enter继续（确认滤波节点已启动）..."

# 步骤3: 启动机械臂驱动
echo ""
echo "【步骤3】启动LBot机械臂驱动..."
echo -e "${YELLOW}提示: 请在新终端中运行以下命令${NC}"
echo ""
echo "  ros2 launch lbot_driver lbot_start_driver.launch.py"
echo ""
read -p "按Enter继续（确认机械臂驱动已启动）..."

# 步骤4: 启动遥操桥接节点
echo ""
echo "【步骤4】启动遥操桥接节点..."
echo -e "${YELLOW}提示: 请在新终端中运行以下命令${NC}"
echo ""
echo "  ./scripts/start_teleop_bridge.sh"
echo ""
echo -e "${RED}注意: 检查桥接节点的关节方向配置！${NC}"
echo "  配置文件: external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml"
echo ""
read -p "按Enter继续（确认桥接节点已启动）..."

# 步骤5: 验证数据流
echo ""
echo "【步骤5】验证数据流..."
echo ""
echo "检查以下话题是否正常发布:"
echo "  1. /left_arm_joint_control (LinkerTA左臂)"
echo "  2. /right_arm_joint_control (LinkerTA右臂)"
echo "  3. /filtered_left_joint_control (滤波后左臂)"
echo "  4. /filtered_right_joint_control (滤波后右臂)"
echo "  5. /robot1/left_arm/joint_follow (机械臂左臂控制)"
echo "  6. /robot1/right_arm/joint_follow (机械臂右臂控制)"
echo "  7. /robot1/left_arm/joint_states (机械臂左臂反馈)"
echo "  8. /robot1/right_arm/joint_states (机械臂右臂反馈)"
echo ""

# 运行话题检查
echo "正在检查话题..."
ros2 topic list | grep -E "(left_arm|right_arm)" || echo -e "${RED}警告: 未找到预期话题${NC}"
echo ""

# 步骤6: 频率检查
echo "【步骤6】频率检查..."
echo "检查左臂原始数据频率（应为80Hz）:"
timeout 3 ros2 topic hz /left_arm_joint_control 2>/dev/null | grep "average rate" || echo "  无数据"
echo ""
echo "检查左臂滤波后频率（应为80Hz）:"
timeout 3 ros2 topic hz /filtered_left_joint_control 2>/dev/null | grep "average rate" || echo "  无数据"
echo ""

# 完成
echo "=========================================="
echo -e "${GREEN}✓ 真机部署准备完成${NC}"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 小心移动遥操臂，观察机械臂是否跟随"
echo "  2. 检查关节方向是否正确"
echo "  3. 如有问题，检查 config/joint_directions.yaml"
echo "  4. 准备好后，可以开始录制数据"
echo ""
echo "紧急停止: Ctrl+C 或按下急停按钮"
echo ""