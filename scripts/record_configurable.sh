#!/bin/bash
# 配置化数据录制脚本
# 根据配置文件录制多个话题，支持灵活的数据采集策略
# 用法: bash scripts/record_configurable.sh [配置文件] [时长秒数]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Source ROS2和lbot_arm_interfaces环境
echo -e "${YELLOW}加载ROS2环境...${NC}"
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

if [ -f "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash" ]; then
    source "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash"
    echo -e "${GREEN}✓ 已加载lbot_arm_interfaces环境${NC}"
else
    echo -e "${YELLOW}警告：未找到lbot_arm_interfaces环境，某些话题可能无法录制${NC}"
fi

# 参数
CONFIG_FILE=${1:-"config/recording_config.yaml"}
DURATION=${2:-30}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="${PROJECT_ROOT}/data/recordings/rec_${TIMESTAMP}"
mkdir -p "$DATA_DIR"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}配置化数据录制${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  配置文件: ${CONFIG_FILE}"
echo -e "  时长: ${DURATION}秒"
echo -e "  数据目录: $DATA_DIR"
echo ""

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误：配置文件不存在: $CONFIG_FILE${NC}"
    exit 1
fi

# 复制配置文件到数据目录
cp "$CONFIG_FILE" "$DATA_DIR/recording_config.yaml"

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}停止录制...${NC}"
    pkill -f "linkerta_node" || true
    pkill -f "vision_node_depth.py" || true
    pkill -f "vist_ros2_bridge.py" || true
    pkill -f "teleop_bridge" || true
    pkill -f "high_freq_resampler" || true
    pkill -f "ros2 bag record" || true
    pkill -f "ros2 topic hz" || true
    echo -e "${GREEN}✓ 录制完成${NC}"
    echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
}

trap cleanup EXIT INT TERM

# 解析配置文件（使用Python）
echo -e "${YELLOW}1. 解析配置文件...${NC}"
python3 << EOF > "$DATA_DIR/parsed_config.sh"
import yaml
import sys

with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)

# 提取配置
mode = config['recording_mode']['mode']
topics = config['topics']

# 生成bash变量
print(f"RECORDING_MODE='{mode}'")

# 收集要录制的话题
enabled_topics = []
for key, value in topics.items():
    if value.get('enabled', False):
        enabled_topics.append(value['topic'])

print(f"TOPICS='{' '.join(enabled_topics)}'")
print(f"TOPIC_COUNT={len(enabled_topics)}")

# 检查是否需要启动各个节点
needs_exo = any(t.get('enabled') and 'exo' in k for k, t in topics.items())
needs_vision = any(t.get('enabled') and 'vision' in k for k, t in topics.items())
needs_bridge = any(t.get('enabled') and 'processed' in k for k, t in topics.items())

print(f"NEEDS_EXO={str(needs_exo).lower()}")
print(f"NEEDS_VISION={str(needs_vision).lower()}")
print(f"NEEDS_BRIDGE={str(needs_bridge).lower()}")
EOF

# 加载解析后的配置
source "$DATA_DIR/parsed_config.sh"

echo -e "${GREEN}✓ 配置解析完成${NC}"
echo -e "  录制模式: ${RECORDING_MODE}"
echo -e "  话题数量: ${TOPIC_COUNT}"
echo -e "  话题列表: ${TOPICS}"
echo ""

# 检查控制节点是否已启动
echo -e "${YELLOW}2. 检查控制节点状态...${NC}"

if ros2 node list 2>/dev/null | grep -q "linkerta_node\|lbot_driver\|teleop_bridge"; then
    echo -e "${GREEN}✓ 检测到已运行的控制节点${NC}"
else
    echo -e "${RED}错误：未检测到运行的控制节点！${NC}"
    echo -e "${YELLOW}请先启动控制系统：${NC}"
    echo -e "  cd external_sdk/arm_teleop"
    echo -e "  source install/setup.bash"
    echo -e "  ros2 launch lbot_teleop teleop.launch.py"
    echo ""
    echo -e "${YELLOW}然后在另一个终端运行此录制脚本${NC}"
    exit 1
fi

echo ""

# 列出当前所有话题
echo -e "${YELLOW}6. 检查可用话题...${NC}"
sleep 2
ros2 topic list > "$DATA_DIR/available_topics.txt"
echo -e "${GREEN}✓ 话题列表保存到: available_topics.txt${NC}"

# 检查配置的话题是否存在
echo -e "${YELLOW}7. 验证配置的话题...${NC}"
MISSING_TOPICS=""
for topic in $TOPICS; do
    if grep -q "^${topic}$" "$DATA_DIR/available_topics.txt"; then
        echo -e "${GREEN}  ✓ $topic${NC}"
    else
        echo -e "${RED}  ✗ $topic (不存在)${NC}"
        MISSING_TOPICS="$MISSING_TOPICS $topic"
    fi
done

if [ -n "$MISSING_TOPICS" ]; then
    echo -e "${YELLOW}警告：以下话题不存在，将被跳过:${MISSING_TOPICS}${NC}"
    # 过滤掉不存在的话题
    FILTERED_TOPICS=""
    for topic in $TOPICS; do
        if grep -q "^${topic}$" "$DATA_DIR/available_topics.txt"; then
            FILTERED_TOPICS="$FILTERED_TOPICS $topic"
        fi
    done
    TOPICS="$FILTERED_TOPICS"
fi

if [ -z "$TOPICS" ]; then
    echo -e "${RED}错误：没有可用的话题！${NC}"
    exit 1
fi

echo ""

# 开始录制
echo -e "${YELLOW}8. 开始录制数据...${NC}"
BAG_DIR="${DATA_DIR}/rosbag"
echo -e "${CYAN}录制话题：${NC}"
echo "$TOPICS"
echo ""

ros2 bag record -o "$BAG_DIR" $TOPICS > "$DATA_DIR/rosbag.log" 2>&1 &
RECORD_PID=$!
sleep 2

# 监控话题频率
echo -e "${YELLOW}9. 监控话题频率...${NC}"
for topic in $TOPICS; do
    echo -e "${CYAN}监控: $topic${NC}"
    timeout $DURATION ros2 topic hz "$topic" > "$DATA_DIR/hz_${topic//\//_}.txt" 2>&1 &
done

echo ""
echo -e "${GREEN}录制进行中...${NC}"
echo -e "${CYAN}请进行操作（遥操臂或视觉控制）${NC}"
echo ""

# 倒计时
for ((i=$DURATION; i>0; i--)); do
    echo -ne "\r剩余时间: ${i}秒  "
    sleep 1
done

echo ""
echo -e "${GREEN}✓ 录制完成！${NC}"

# 等待录制进程结束
sleep 2
pkill -f "ros2 bag record" || true
wait $RECORD_PID 2>/dev/null || true

# 分析录制的数据
echo ""
echo -e "${YELLOW}10. 分析录制的数据...${NC}"
ros2 bag info "$BAG_DIR" > "$DATA_DIR/bag_info.txt" 2>&1
cat "$DATA_DIR/bag_info.txt"

# 汇总频率信息
echo ""
echo -e "${YELLOW}11. 汇总频率信息...${NC}"
echo "========================================" > "$DATA_DIR/frequency_summary.txt"
echo "话题频率汇总" >> "$DATA_DIR/frequency_summary.txt"
echo "========================================" >> "$DATA_DIR/frequency_summary.txt"
echo "" >> "$DATA_DIR/frequency_summary.txt"

for topic in $TOPICS; do
    hz_file="$DATA_DIR/hz_${topic//\//_}.txt"
    if [ -f "$hz_file" ]; then
        echo "话题: $topic" >> "$DATA_DIR/frequency_summary.txt"
        grep -E "average rate|min|max" "$hz_file" | tail -4 >> "$DATA_DIR/frequency_summary.txt" || echo "  无数据" >> "$DATA_DIR/frequency_summary.txt"
        echo "" >> "$DATA_DIR/frequency_summary.txt"
    fi
done

cat "$DATA_DIR/frequency_summary.txt"

# 生成报告
echo ""
echo -e "${YELLOW}12. 生成录制报告...${NC}"
cat > "$DATA_DIR/README.md" << EOF
# 配置化数据录制报告

**录制时间**: $(date)
**录制时长**: ${DURATION}秒
**录制模式**: ${RECORDING_MODE}

## 1. 配置信息

\`\`\`yaml
$(cat "$DATA_DIR/recording_config.yaml")
\`\`\`

## 2. 录制的话题

\`\`\`
$TOPICS
\`\`\`

## 3. 录制的数据

\`\`\`
$(cat "$DATA_DIR/bag_info.txt")
\`\`\`

## 4. 频率分析

\`\`\`
$(cat "$DATA_DIR/frequency_summary.txt")
\`\`\`

## 5. 数据层级说明

根据录制的话题，数据包含以下层级：

- **原始输出**: 控制算法的直接输出（如 /right_arm_joint_control, /vision_right_joint_control）
- **处理后输出**: 经过桥接/插值处理的数据（如 /robot1/right_arm/joint_follow）
- **真机反馈**: 真实机器人执行后的反馈（如 /robot1/right_arm/joint_states）

## 6. 评估建议

1. **对比原始输出**: 比较不同控制方法的算法输出
2. **对比处理后输出**: 比较实际发送给真机的指令
3. **分析频率差异**: 检查不同层级的频率变化
4. **验证数据一致性**: 确保数据格式和单位统一

## 7. 下一步

\`\`\`bash
# 评估录制的数据
python scripts/evaluate_vision_performance.py \\
    --rosbag $DATA_DIR/rosbag \\
    --config config/evaluation_config.yaml \\
    --output $DATA_DIR/evaluation

# 对比多个话题
python scripts/compare_topics.py \\
    --rosbag $DATA_DIR/rosbag \\
    --topics "$TOPICS"
\`\`\`

EOF

echo -e "${GREEN}✓ 报告保存到: $DATA_DIR/README.md${NC}"
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}录制完成！${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
echo ""
echo -e "${YELLOW}下一步：${NC}"
echo "  1. 查看报告: cat $DATA_DIR/README.md"
echo "  2. 评估数据: python scripts/evaluate_vision_performance.py --rosbag $DATA_DIR/rosbag"
echo "  3. 对比话题: python scripts/compare_topics.py --rosbag $DATA_DIR/rosbag"
echo ""
