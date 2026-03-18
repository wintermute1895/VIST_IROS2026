#!/bin/bash
# 真机双臂完整部署脚本
# 包含所有必要的配置检查和启动步骤

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  VIST 真机双臂部署向导${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ==================== 步骤1: 配置检查 ====================
echo -e "${YELLOW}【步骤1】配置文件检查${NC}"
echo ""

# 检查1.1: joint_directions.yaml
echo "1.1 检查关节方向配置..."
if [ -f "config/joint_directions.yaml" ]; then
    echo -e "${GREEN}✓${NC} config/joint_directions.yaml 存在"
    echo "   左臂方向: $(grep -A 7 'left_arm_joint_directions:' config/joint_directions.yaml | tail -7 | tr '\n' ' ')"
    echo "   右臂方向: $(grep -A 7 'right_arm_joint_directions:' config/joint_directions.yaml | tail -7 | tr '\n' ' ')"
else
    echo -e "${RED}✗${NC} config/joint_directions.yaml 不存在"
    exit 1
fi
echo ""

# 检查1.2: baseline_filters_config.yaml
echo "1.2 检查滤波器配置..."
if [ -f "config/baseline_filters_config.yaml" ]; then
    echo -e "${GREEN}✓${NC} config/baseline_filters_config.yaml 存在"
    FILTER_TYPE=$(grep "filter_type:" config/baseline_filters_config.yaml | head -1 | awk '{print $2}' | tr -d "'\"")
    echo "   当前滤波器: $FILTER_TYPE"

    if [ "$FILTER_TYPE" == "gello" ]; then
        echo -e "${YELLOW}   警告: GELLO是直通模式，建议切换到 'oneeuro' 用于真机${NC}"
        read -p "   是否继续? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo -e "${RED}✗${NC} config/baseline_filters_config.yaml 不存在"
    exit 1
fi
echo ""

# 检查1.3: teleop_bridge_params.yaml
echo "1.3 检查桥接节点配置..."
BRIDGE_CONFIG="ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml"
if [ -f "$BRIDGE_CONFIG" ]; then
    echo -e "${GREEN}✓${NC} teleop_bridge_params.yaml 存在"

    # 检查右臂是否启用
    ENABLE_RIGHT=$(grep "enable_right_arm:" "$BRIDGE_CONFIG" | awk '{print $2}')
    RIGHT_TOPIC=$(grep "master_right_topic:" "$BRIDGE_CONFIG" | awk '{print $2}' | tr -d '"')

    echo "   enable_right_arm: $ENABLE_RIGHT"
    echo "   master_right_topic: $RIGHT_TOPIC"

    if [ "$ENABLE_RIGHT" == "false" ] || [ "$RIGHT_TOPIC" == "/right_arm_disabled" ]; then
        echo -e "${RED}   ✗ 右臂未启用！${NC}"
        echo -e "${YELLOW}   需要修改配置:${NC}"
        echo "     enable_right_arm: true"
        echo "     master_right_topic: \"/filtered_right_joint_control\""
        read -p "   是否自动修改? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # 备份原文件
            cp "$BRIDGE_CONFIG" "${BRIDGE_CONFIG}.backup"
            # 修改配置
            sed -i 's/enable_right_arm: false/enable_right_arm: true/' "$BRIDGE_CONFIG"
            sed -i 's|master_right_topic: "/right_arm_disabled"|master_right_topic: "/filtered_right_joint_control"|' "$BRIDGE_CONFIG"
            echo -e "${GREEN}   ✓ 配置已修改（原文件已备份）${NC}"
        else
            echo -e "${RED}   请手动修改配置后重新运行${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}   ✓ 右臂已启用${NC}"
    fi
else
    echo -e "${RED}✗${NC} teleop_bridge_params.yaml 不存在"
    exit 1
fi
echo ""

# ==================== 步骤2: 硬件检查 ====================
echo -e "${YELLOW}【步骤2】硬件连接检查${NC}"
echo ""

# 检查2.1: CAN接口
echo "2.1 检查CAN接口..."
if ip link show can0 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} CAN0 (灵巧手) 已启动"
else
    echo -e "${RED}✗${NC} CAN0 未启动"
    echo "   运行: sudo ip link set can0 up type can bitrate 1000000"
fi

if ip link show can1 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} CAN1 (LinkerTA) 已启动"
else
    echo -e "${RED}✗${NC} CAN1 未启动"
    echo "   运行: sudo ip link set can1 up type can bitrate 1000000"
fi
echo ""

# 检查2.2: 网络连接
echo "2.2 检查机械臂网络连接..."
ROBOT_IP="192.168.10.21"
if ping -c 1 -W 1 $ROBOT_IP > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 机械臂 ($ROBOT_IP) 网络连通"
else
    echo -e "${RED}✗${NC} 机械臂 ($ROBOT_IP) 网络不通"
    echo "   请检查网络连接"
fi
echo ""

# ==================== 步骤3: 启动指南 ====================
echo -e "${YELLOW}【步骤3】节点启动指南${NC}"
echo ""
echo "请按照以下顺序在不同终端中启动节点:"
echo ""

echo -e "${BLUE}终端1: LinkerTA节点${NC}"
echo "  cd $PROJECT_ROOT"
echo "  ros2 run linkerta linkerta_node --ros-args --params-file ros2_ws/src/external_sdk/arm_teleop/src/linkerta/config/lta.yaml"
echo ""

echo -e "${BLUE}终端2: 左臂滤波节点${NC}"
echo "  cd $PROJECT_ROOT"
echo "  python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \\"
echo "      --params-file config/baseline_filters_config.yaml \\"
echo "      -p arm_side:=left"
echo ""

echo -e "${BLUE}终端3: 右臂滤波节点${NC}"
echo "  cd $PROJECT_ROOT"
echo "  python3 ros2_ws/src/nodes/vist_filter_node.py --ros-args \\"
echo "      --params-file config/baseline_filters_config.yaml \\"
echo "      -p arm_side:=right"
echo ""

echo -e "${BLUE}终端4: 机械臂驱动${NC}"
echo "  cd $PROJECT_ROOT"
echo "  ros2 launch lbot_driver lbot_start_driver.launch.py"
echo ""

echo -e "${BLUE}终端5: 遥操桥接节点${NC}"
echo "  cd $PROJECT_ROOT"
echo "  ros2 run lbot_teleop teleop_bridge_node --ros-args \\"
echo "      --params-file ros2_ws/src/external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml"
echo ""

# ==================== 步骤4: 验证命令 ====================
echo -e "${YELLOW}【步骤4】系统验证命令${NC}"
echo ""
echo "启动所有节点后，运行以下命令验证:"
echo ""
echo "4.1 检查所有节点:"
echo "  ros2 node list"
echo ""
echo "4.2 检查话题列表:"
echo "  ros2 topic list | grep -E '(left_arm|right_arm)'"
echo ""
echo "4.3 检查话题频率:"
echo "  ros2 topic hz /left_arm_joint_control"
echo "  ros2 topic hz /filtered_left_joint_control"
echo "  ros2 topic hz /robot1/left_arm/joint_follow"
echo ""
echo "4.4 运行完整诊断:"
echo "  python3 diagnose_data_flow.py"
echo ""

# ==================== 步骤5: 数据流图 ====================
echo -e "${YELLOW}【步骤5】完整数据流${NC}"
echo ""
cat << 'EOF'
LinkerTA硬件 (CAN1)
  ↓ 80Hz
linkerta_node
  ├─> /left_arm_joint_control
  │     ↓
  │   vist_filter_node (左臂)
  │     ↓ 应用 joint_directions
  │   /filtered_left_joint_control
  │     ↓
  │   teleop_bridge_node
  │     ↓ 应用 negation + 角度→弧度
  │   /robot1/left_arm/joint_follow
  │     ↓
  │   lbot_driver
  │     ↓ 网络 (192.168.10.21)
  │   真机左臂
  │
  └─> /right_arm_joint_control
        ↓
      vist_filter_node (右臂)
        ↓ 应用 joint_directions
      /filtered_right_joint_control
        ↓
      teleop_bridge_node
        ↓ 应用 negation + 角度→弧度
      /robot1/right_arm/joint_follow
        ↓
      lbot_driver
        ↓ 网络 (192.168.10.21)
      真机右臂
EOF
echo ""

# ==================== 完成 ====================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  配置检查完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "下一步:"
echo "  1. 按照上面的指南在5个终端中启动节点"
echo "  2. 运行验证命令确认系统正常"
echo "  3. 小心移动遥操臂，观察真机是否跟随"
echo "  4. 如有问题，运行 diagnose_data_flow.py 诊断"
echo ""
echo -e "${RED}紧急停止: Ctrl+C 或按下急停按钮${NC}"
echo ""