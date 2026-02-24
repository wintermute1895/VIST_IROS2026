#!/bin/bash
# VIST 视觉控制完整测试流程
# 功能：启动 → 录制 → 分析

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# 配置参数
RECORD_DURATION=30  # 录制时长（秒）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="data/vision_control_test_${TIMESTAMP}"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     VIST 视觉控制完整测试流程                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 加载ROS2环境
echo -e "${BLUE}[1/6] 加载ROS2环境...${NC}"
source /opt/ros/humble/setup.bash
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash
    echo "✓ ROS2环境已加载"
else
    echo -e "${RED}✗ 找不到 lbot_arm_interfaces${NC}"
    echo "请先编译: cd external_sdk/arm_teleop && colcon build"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
echo "✓ 输出目录: $OUTPUT_DIR"
echo ""

# 检查依赖
echo -e "${BLUE}[2/6] 检查依赖...${NC}"

# 检查视觉节点
if [ ! -f "src/nodes/vision_node_depth.py" ]; then
    echo -e "${RED}✗ 找不到视觉节点${NC}"
    exit 1
fi

# 检查仿真脚本
if [ ! -f "scripts/experiments/simulate_full_flow.py" ]; then
    echo -e "${RED}✗ 找不到仿真脚本${NC}"
    exit 1
fi

# 检查分析脚本
if [ ! -f "scripts/analyze_all_metrics.py" ]; then
    echo -e "${RED}✗ 找不到分析脚本${NC}"
    exit 1
fi

echo "✓ 所有依赖文件存在"
echo ""

# 询问是否应用高频补丁
echo -e "${YELLOW}[3/6] 检查高频插值配置...${NC}"
if grep -q "HighFrequencyPublisher" scripts/experiments/simulate_full_flow.py 2>/dev/null; then
    echo "✓ 高频插值已集成"
else
    echo -e "${YELLOW}⚠ 高频插值未集成${NC}"
    echo ""
    echo "请手动应用补丁："
    echo "  1. 查看 scripts/high_freq_patch.py"
    echo "  2. 按照说明修改 simulate_full_flow.py"
    echo ""
    read -p "是否继续（不使用高频插值）? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi
echo ""

# 启动节点
echo -e "${BLUE}[4/6] 启动节点...${NC}"
echo ""
echo "将在新终端中启动以下节点："
echo "  1. 视觉节点 (vision_node_depth.py)"
echo "  2. 仿真控制 (simulate_full_flow.py)"
echo ""

# 检查是否在tmux或screen中
if [ -n "$TMUX" ] || [ -n "$STY" ]; then
    echo "检测到tmux/screen环境"
    USE_TMUX=true
else
    USE_TMUX=false
fi

# 启动视觉节点
echo "启动视觉节点..."
if [ "$USE_TMUX" = true ] && [ -n "$TMUX" ]; then
    # 在tmux中创建新窗口
    tmux new-window -n "vision" "cd $(pwd) && PYTHONPATH=$(pwd):\$PYTHONPATH python3 src/nodes/vision_node_depth.py; read"
    VISION_PID=""
else
    # 在后台启动
    PYTHONPATH="$(pwd):$PYTHONPATH" python3 src/nodes/vision_node_depth.py > "$OUTPUT_DIR/vision_node.log" 2>&1 &
    VISION_PID=$!
    echo "  PID: $VISION_PID"
fi

sleep 3

# 启动仿真控制
echo "启动仿真控制..."
if [ "$USE_TMUX" = true ] && [ -n "$TMUX" ]; then
    tmux new-window -n "simulation" "cd $(pwd) && source /opt/ros/humble/setup.bash && source external_sdk/arm_teleop/install/setup.bash && PYTHONPATH=$(pwd):\$PYTHONPATH python3 scripts/experiments/simulate_full_flow.py; read"
    SIMULATION_PID=""
else
    (source /opt/ros/humble/setup.bash && \
     source external_sdk/arm_teleop/install/setup.bash && \
     PYTHONPATH="$(pwd):$PYTHONPATH" python3 scripts/experiments/simulate_full_flow.py) > "$OUTPUT_DIR/simulation.log" 2>&1 &
    SIMULATION_PID=$!
    echo "  PID: $SIMULATION_PID"
fi

sleep 5

# 检查话题
echo ""
echo "检查ROS2话题..."
if ros2 topic list | grep -q "/vision_control/joint_follow"; then
    echo -e "${GREEN}✓ 视觉控制话题已发布${NC}"

    # 检查频率
    FREQ=$(timeout 3 ros2 topic hz /vision_control/joint_follow 2>/dev/null | grep "average rate" | awk '{print $3}' || echo "0")
    echo "  发布频率: ${FREQ} Hz"
else
    echo -e "${RED}✗ 未找到视觉控制话题${NC}"
    echo "请检查节点是否正常启动"

    # 清理
    [ -n "$VISION_PID" ] && kill $VISION_PID 2>/dev/null
    [ -n "$SIMULATION_PID" ] && kill $SIMULATION_PID 2>/dev/null
    exit 1
fi

echo ""

# 录制数据
echo -e "${BLUE}[5/6] 录制数据 (${RECORD_DURATION}秒)...${NC}"
echo ""
echo "录制话题:"
echo "  - /vision_control/joint_follow"
echo "  - /vision_control/joint_states"
echo ""

# 启动rosbag录制
ros2 bag record \
    /vision_control/joint_follow \
    /vision_control/joint_states \
    -o "$OUTPUT_DIR/rosbag" \
    --max-bag-duration $RECORD_DURATION &
ROSBAG_PID=$!

# 显示进度
for i in $(seq 1 $RECORD_DURATION); do
    echo -ne "\r  进度: [$i/$RECORD_DURATION] "
    for j in $(seq 1 $((i * 50 / RECORD_DURATION))); do
        echo -n "█"
    done
    sleep 1
done
echo ""

# 等待rosbag完成
wait $ROSBAG_PID 2>/dev/null || true

echo -e "${GREEN}✓ 数据录制完成${NC}"
echo ""

# 停止节点
echo "停止节点..."
if [ -n "$VISION_PID" ]; then
    kill $VISION_PID 2>/dev/null || true
fi
if [ -n "$SIMULATION_PID" ]; then
    kill $SIMULATION_PID 2>/dev/null || true
fi

# 如果在tmux中，提示用户手动关闭
if [ "$USE_TMUX" = true ]; then
    echo "请手动关闭tmux窗口中的节点（Ctrl+C）"
    sleep 2
fi

echo ""

# 分析数据
echo -e "${BLUE}[6/6] 分析数据...${NC}"
echo ""

# 运行分析脚本
./scripts/run_analysis.sh \
    --rosbag "$OUTPUT_DIR/rosbag" \
    --config config/analysis_config.yaml \
    --output "$OUTPUT_DIR/analysis"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 数据分析完成${NC}"
else
    echo ""
    echo -e "${RED}✗ 数据分析失败${NC}"
fi

# 生成报告
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    测试完成                                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "输出目录: $OUTPUT_DIR"
echo ""
echo "生成的文件:"
echo "  📁 rosbag/          - 原始数据"
echo "  📁 analysis/        - 分析结果"
echo "  📊 analysis/all_metrics.json       - 性能指标"
echo "  📈 analysis/trajectory_comparison.png  - 轨迹对比图"
echo "  📈 analysis/metrics_comparison.png     - 指标对比图"
echo ""
echo "查看结果:"
echo "  cat $OUTPUT_DIR/analysis/all_metrics.json"
echo "  xdg-open $OUTPUT_DIR/analysis/trajectory_comparison.png"
echo ""

# 显示关键指标
if [ -f "$OUTPUT_DIR/analysis/all_metrics.json" ]; then
    echo -e "${YELLOW}关键指标:${NC}"
    python3 -c "
import json
import sys

try:
    with open('$OUTPUT_DIR/analysis/all_metrics.json', 'r') as f:
        data = json.load(f)

    for source, info in data.items():
        print(f\"\\n{info['label']}:\")
        metrics = info['metrics']
        print(f\"  频率: {metrics['frequency']:.2f} Hz\")
        print(f\"  中位速度: {metrics['avg_velocity']:.4f} rad/s\")
        print(f\"  99%速度: {metrics['max_velocity']:.4f} rad/s\")
        print(f\"  中位Jerk: {metrics['avg_jerk']:.4f} rad/s³\")
        print(f\"  99%Jerk: {metrics['max_jerk']:.4f} rad/s³\")
except Exception as e:
    print(f\"无法读取指标: {e}\", file=sys.stderr)
"
fi

echo ""
echo -e "${GREEN}测试流程完成！${NC}"