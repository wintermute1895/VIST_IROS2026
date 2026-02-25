#!/bin/bash
# 统一数据录制脚本（增强版）
# 功能：
# 1. 集成Episode管理器
# 2. 自动质量验证
# 3. 自动元数据生成
# 4. 统一输出到 data/collection/
#
# 用法:
#   bash scripts/record_data.sh --task task_name --config config/task_config.yaml [--duration 30]
#   bash scripts/record_data.sh --quick [--duration 30]  # 快速测试模式

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

# 默认参数
TASK_NAME=""
CONFIG_FILE=""
DURATION=30
QUICK_MODE=false
USE_EPISODE_MANAGER=true

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --task)
            TASK_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=true
            TASK_NAME="quick_test"
            shift
            ;;
        --no-episode-manager)
            USE_EPISODE_MANAGER=false
            shift
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "用法: bash scripts/record_data.sh --task task_name --config config.yaml [--duration 30]"
            echo "      bash scripts/record_data.sh --quick [--duration 30]"
            exit 1
            ;;
    esac
done

# 检查参数
if [ -z "$TASK_NAME" ]; then
    echo -e "${RED}错误：必须指定任务名称 (--task) 或使用快速模式 (--quick)${NC}"
    exit 1
fi

if [ "$QUICK_MODE" = false ] && [ -z "$CONFIG_FILE" ]; then
    echo -e "${RED}错误：必须指定配置文件 (--config)${NC}"
    exit 1
fi

# Source ROS2环境
echo -e "${YELLOW}加载ROS2环境...${NC}"
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

if [ -f "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash" ]; then
    source "${PROJECT_ROOT}/external_sdk/arm_teleop/install/setup.bash"
    echo -e "${GREEN}✓ 已加载lbot_arm_interfaces环境${NC}"
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}VIST 数据录制${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  任务名称: ${TASK_NAME}"
echo -e "  录制时长: ${DURATION}秒"
if [ "$QUICK_MODE" = true ]; then
    echo -e "  模式: 快速测试"
else
    echo -e "  配置文件: ${CONFIG_FILE}"
fi
echo ""

# 快速模式：使用默认话题
if [ "$QUICK_MODE" = true ]; then
    echo -e "${YELLOW}快速测试模式：使用默认话题${NC}"
    TOPICS="/robot1/right_arm/joint_states /right_arm_joint_control"

    # 创建临时配置
    CONFIG_FILE="/tmp/quick_record_config_$$.yaml"
    cat > "$CONFIG_FILE" << EOF
task_info:
  name: "quick_test"
  description: "快速测试录制"

topics:
  - "/robot1/right_arm/joint_states"
  - "/right_arm_joint_control"

control_params:
  control_frequency: 50
  max_episode_duration: ${DURATION}

quality_requirements:
  min_sync_quality: "acceptable"
  max_time_diff_ms: 100

automation:
  auto_validate: true
  auto_convert: false
EOF
    echo -e "${GREEN}✓ 已创建临时配置${NC}"
else
    # 检查配置文件
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}错误：配置文件不存在: $CONFIG_FILE${NC}"
        exit 1
    fi

    # 从配置文件提取话题
    TOPICS=$(python3 << EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
topics = config.get('topics', [])
print(' '.join(topics))
EOF
)
fi

echo -e "${YELLOW}录制话题:${NC}"
echo "$TOPICS" | tr ' ' '\n' | sed 's/^/  - /'
echo ""

# 检查控制节点
echo -e "${YELLOW}检查控制节点状态...${NC}"
if ros2 node list 2>/dev/null | grep -q "linkerta_node\|lbot_driver\|teleop_bridge"; then
    echo -e "${GREEN}✓ 检测到运行的控制节点${NC}"
else
    echo -e "${RED}错误：未检测到运行的控制节点！${NC}"
    echo -e "${YELLOW}请先启动控制系统${NC}"
    exit 1
fi
echo ""

# 使用Episode管理器或直接录制
if [ "$USE_EPISODE_MANAGER" = true ] && [ "$QUICK_MODE" = false ]; then
    echo -e "${YELLOW}使用Episode管理器录制...${NC}"

    # 创建任务（如果不存在）
    SESSION_ID=$(python3 << EOF
import sys
import json
from pathlib import Path

sys.path.insert(0, 'scripts')
from episode_manager import EpisodeManager

manager = EpisodeManager()

# 检查任务是否存在
task_dir = Path('data/collection') / '$TASK_NAME'
if not task_dir.exists():
    print("创建新任务...", file=sys.stderr)
    import yaml
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    session_id = manager.create_task('$TASK_NAME', config)
else:
    # 使用最新的session
    sessions = sorted(task_dir.glob('session_*'))
    if sessions:
        session_id = sessions[-1].name
    else:
        import yaml
        with open('$CONFIG_FILE', 'r') as f:
            config = yaml.safe_load(f)
        session_id = manager.create_task('$TASK_NAME', config)

print(session_id)
EOF
)

    echo -e "${GREEN}✓ Session ID: ${SESSION_ID}${NC}"
    echo ""

    # 开始录制
    echo -e "${YELLOW}开始Episode录制...${NC}"
    python3 << EOF
import sys
sys.path.insert(0, 'scripts')
from episode_manager import EpisodeManager

manager = EpisodeManager()
episode_id = manager.start_episode('$SESSION_ID', max_duration=$DURATION, topics='$TOPICS'.split())
print(f"Episode ID: {episode_id}")

# 等待录制完成
import time
print(f"录制中... ({$DURATION}秒)")
time.sleep($DURATION)

# 停止录制
manager.stop_episode(episode_id, auto_validate=True)
print("录制完成！")
EOF

else
    # 直接录制模式（不使用Episode管理器）
    echo -e "${YELLOW}直接录制模式...${NC}"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    if [ "$QUICK_MODE" = true ]; then
        DATA_DIR="${PROJECT_ROOT}/data/collection/quick_test/session_${TIMESTAMP}/episode_000000"
    else
        DATA_DIR="${PROJECT_ROOT}/data/collection/${TASK_NAME}/session_${TIMESTAMP}/episode_000000"
    fi

    mkdir -p "$DATA_DIR"
    ROSBAG_DIR="$DATA_DIR/rosbag"

    echo -e "  数据目录: $DATA_DIR"
    echo ""

    # 复制配置文件
    cp "$CONFIG_FILE" "$DATA_DIR/recording_config.yaml"

    # 清理函数
    cleanup() {
        echo ""
        echo -e "${YELLOW}停止录制...${NC}"
        pkill -f "ros2 bag record" || true
        pkill -f "ros2 topic hz" || true

        # 生成元数据
        echo -e "${YELLOW}生成元数据...${NC}"
        python3 scripts/generate_episode_metadata.py "$ROSBAG_DIR" \
            --task "$TASK_NAME" 2>/dev/null || true

        # 验证时间同步
        if [ -f "$ROSBAG_DIR/metadata.yaml" ]; then
            echo -e "${YELLOW}验证时间同步...${NC}"
            python3 scripts/validate_time_sync.py "$ROSBAG_DIR" 2>/dev/null || true
        fi

        echo -e "${GREEN}✓ 录制完成${NC}"
        echo -e "${GREEN}数据保存在: $DATA_DIR${NC}"
    }

    trap cleanup EXIT INT TERM

    # 开始rosbag录制
    echo -e "${YELLOW}开始rosbag录制...${NC}"
    ros2 bag record -o "$ROSBAG_DIR" $TOPICS > "$DATA_DIR/rosbag.log" 2>&1 &
    RECORD_PID=$!

    sleep 2

    # 检查录制进程
    if ! kill -0 $RECORD_PID 2>/dev/null; then
        echo -e "${RED}错误：rosbag录制启动失败${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 录制已启动 (PID: $RECORD_PID)${NC}"
    echo ""

    # 倒计时
    echo -e "${CYAN}录制进行中...${NC}"
    for ((i=$DURATION; i>0; i--)); do
        echo -ne "\r剩余时间: ${i}秒  "
        sleep 1
    done
    echo ""

    # 停止录制
    pkill -f "ros2 bag record" || true
    wait $RECORD_PID 2>/dev/null || true
fi

# 清理临时文件
if [ "$QUICK_MODE" = true ]; then
    rm -f "$CONFIG_FILE"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}录制完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}下一步:${NC}"
echo "  1. 查看数据: ls -lh data/collection/${TASK_NAME}/"
echo "  2. 验证质量: python scripts/validate_time_sync.py <rosbag_path>"
echo "  3. 分析数据: python scripts/analyze_episode.py <episode_path>"
echo ""
