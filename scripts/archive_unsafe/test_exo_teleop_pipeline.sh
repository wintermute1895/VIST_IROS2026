#!/bin/bash
# 外骨骼遥操数据采集测试脚本
# 用途：打通外骨骼→机器人控制链路，采集数据并分析性能指标

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置参数
DURATION=${1:-30}  # 录制时长（秒），默认30秒
TASK_NAME=${2:-"exo_teleop_test"}  # 任务名称
CAMERA_SERIAL=${3:-"348122071157"}  # 相机序列号，默认使用第一个D435I

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}外骨骼遥操数据采集测试${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "配置信息："
echo "  录制时长: ${DURATION}秒"
echo "  任务名称: ${TASK_NAME}"
echo "  相机序列号: ${CAMERA_SERIAL}"
echo ""

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}错误: ROS2环境未设置${NC}"
    echo "请先运行: source /opt/ros/<distro>/setup.bash"
    exit 1
fi

# 检查相机
echo -e "${YELLOW}[1/6] 检查相机连接...${NC}"
if ! rs-enumerate-devices | grep -q "$CAMERA_SERIAL"; then
    echo -e "${RED}错误: 未找到相机 $CAMERA_SERIAL${NC}"
    echo "可用的相机："
    rs-enumerate-devices | grep "Serial Number"
    exit 1
fi
echo -e "${GREEN}✓ 相机已连接${NC}"
echo ""

# 检查机器人连接
echo -e "${YELLOW}[2/6] 检查机器人连接...${NC}"
ROBOT_IP="192.168.10.21"
if ! ping -c 1 -W 1 $ROBOT_IP &> /dev/null; then
    echo -e "${RED}警告: 无法ping通机器人 $ROBOT_IP${NC}"
    read -p "是否继续（仅录制外骨骼数据）？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ 机器人已连接${NC}"
fi
echo ""

# 创建episode目录
echo -e "${YELLOW}[3/6] 创建数据目录...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EPISODE_DIR="data/collection/${TASK_NAME}_${TIMESTAMP}"
mkdir -p "$EPISODE_DIR"
echo -e "${GREEN}✓ 数据目录: $EPISODE_DIR${NC}"
echo ""

# 启动外骨骼遥操系统
echo -e "${YELLOW}[4/6] 启动外骨骼遥操系统...${NC}"
echo "执行命令: ros2 launch lbot_teleop teleop.launch.py"
echo ""
echo -e "${YELLOW}请在另一个终端执行以下命令：${NC}"
echo -e "${GREEN}cd /home/ilex/Dev/VIST/external_sdk/arm_teleop${NC}"
echo -e "${GREEN}source install/setup.bash${NC}"
echo -e "${GREEN}ros2 launch lbot_teleop teleop.launch.py${NC}"
echo ""
read -p "外骨骼系统启动完成后按回车继续..."

# 验证topic是否发布
echo -e "${YELLOW}验证ROS2 topics...${NC}"
REQUIRED_TOPICS=(
    "/right_arm_joint_control"
    "/robot1/right_arm/joint_follow"
)

OPTIONAL_TOPICS=(
    "/cb_left_hand_control_cmd"
    "/cb_left_hand_state"
)

for topic in "${REQUIRED_TOPICS[@]}"; do
    if ros2 topic list | grep -q "^${topic}$"; then
        echo -e "${GREEN}✓ $topic${NC}"
    else
        echo -e "${RED}✗ $topic 未找到${NC}"
        echo "可用的topics:"
        ros2 topic list
        exit 1
    fi
done

echo ""
echo "检查可选topics（数据手套）:"
HAND_TOPICS_FOUND=false
HAND_TOPICS_TO_RECORD=""
for topic in "${OPTIONAL_TOPICS[@]}"; do
    if ros2 topic list | grep -q "^${topic}$"; then
        echo -e "${GREEN}✓ $topic${NC}"
        HAND_TOPICS_FOUND=true
        HAND_TOPICS_TO_RECORD="$HAND_TOPICS_TO_RECORD $topic"
    else
        echo -e "${YELLOW}⚠ $topic 未找到（可选）${NC}"
    fi
done

if [ "$HAND_TOPICS_FOUND" = false ]; then
    echo -e "${YELLOW}注意: 未检测到数据手套topics，将不录制手指数据${NC}"
    echo -e "${YELLOW}如需录制手指数据，请先启动:${NC}"
    echo -e "${YELLOW}  cd /home/ilex/Dev/VIST/external_sdk/linkerhand-ros2-sdk${NC}"
    echo -e "${YELLOW}  source install/setup.bash${NC}"
    echo -e "${YELLOW}  ros2 launch linker_hand_ros2_sdk linker_hand.launch.py${NC}"
fi
echo ""

# 开始录制
echo -e "${YELLOW}[5/6] 开始录制数据...${NC}"
echo "录制以下topics:"
echo "  - /right_arm_joint_control (外骨骼原始输出 ~250Hz)"
echo "  - /robot1/right_arm/joint_follow (跟随命令 ~250Hz)"
echo "  - /robot1/right_arm/joint_states (真机反馈 ~50Hz)"
echo "  - /camera/color/image_raw (相机RGB)"
echo "  - /camera/depth/image_rect_raw (相机深度)"
if [ "$HAND_TOPICS_FOUND" = true ]; then
    echo "  - /cb_left_hand_control_cmd (数据手套控制命令 ~30Hz)"
    echo "  - /cb_left_hand_state (数据手套状态反馈 ~40Hz)"
fi
echo ""

# 启动相机（后台）
echo "启动相机..."
ros2 launch realsense2_camera rs_launch.py \
    serial_no:=$CAMERA_SERIAL \
    depth_module.profile:=640x480x30 \
    rgb_camera.profile:=640x480x30 \
    enable_gyro:=false \
    enable_accel:=false \
    &
CAMERA_PID=$!
sleep 3

# 录制rosbag
echo "开始录制 ${DURATION}秒..."
ros2 bag record \
    -o "$EPISODE_DIR/rosbag" \
    /right_arm_joint_control \
    /robot1/right_arm/joint_follow \
    /robot1/right_arm/joint_states \
    /camera/color/image_raw \
    /camera/depth/image_rect_raw \
    $HAND_TOPICS_TO_RECORD \
    --max-bag-duration $DURATION &
RECORD_PID=$!

# 等待录制完成
sleep $DURATION
wait $RECORD_PID

# 停止相机
kill $CAMERA_PID 2>/dev/null || true

echo -e "${GREEN}✓ 录制完成${NC}"
echo ""

# 生成元数据
echo -e "${YELLOW}[6/6] 生成元数据和分析报告...${NC}"

# 创建episode元数据
HAND_METADATA=""
if [ "$HAND_TOPICS_FOUND" = true ]; then
    HAND_METADATA=',
    "hand_control_cmd": "/cb_left_hand_control_cmd",
    "hand_state": "/cb_left_hand_state"'
fi

cat > "$EPISODE_DIR/metadata.json" << EOF
{
  "task_name": "$TASK_NAME",
  "timestamp": "$TIMESTAMP",
  "duration": $DURATION,
  "camera_serial": "$CAMERA_SERIAL",
  "robot_ip": "$ROBOT_IP",
  "has_hand_data": $HAND_TOPICS_FOUND,
  "topics": {
    "exo_raw": "/right_arm_joint_control",
    "exo_processed": "/robot1/right_arm/joint_follow",
    "robot_feedback": "/robot1/right_arm/joint_states",
    "camera_rgb": "/camera/color/image_raw",
    "camera_depth": "/camera/depth/image_rect_raw"$HAND_METADATA
  },
  "expected_frequencies": {
    "exo_raw": 250,
    "exo_processed": 250,
    "robot_feedback": 50,
    "camera": 30,
    "hand_control": 30,
    "hand_state": 40
  }
}
EOF

# 运行时间同步验证
echo "验证时间同步质量..."
python3 scripts/validate_time_sync.py \
    "$EPISODE_DIR/rosbag" \
    --topic1 /right_arm_joint_control \
    --topic2 /robot1/right_arm/joint_follow \
    --output "$EPISODE_DIR/sync_report.json" || true

# 生成频率分析报告
echo "分析topic频率..."
python3 << EOF
import sqlite3
import json
from pathlib import Path

db_path = Path("$EPISODE_DIR/rosbag/rosbag2_*.db3")
db_files = list(Path("$EPISODE_DIR/rosbag").glob("rosbag2_*.db3"))
if not db_files:
    print("未找到rosbag数据库文件")
    exit(1)

conn = sqlite3.connect(str(db_files[0]))
cursor = conn.cursor()

# 获取所有topic的消息数量
cursor.execute("""
    SELECT topics.name, COUNT(messages.id) as count
    FROM messages
    JOIN topics ON messages.topic_id = topics.id
    GROUP BY topics.name
""")

results = {}
for topic, count in cursor.fetchall():
    freq = count / $DURATION
    results[topic] = {
        "count": count,
        "frequency": round(freq, 2)
    }

conn.close()

# 保存结果
with open("$EPISODE_DIR/frequency_report.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n频率分析结果:")
for topic, data in results.items():
    print(f"  {topic}: {data['frequency']} Hz ({data['count']} messages)")
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}数据采集完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "数据保存位置: $EPISODE_DIR"
echo ""
echo "生成的文件:"
echo "  - rosbag/           # ROS2 bag数据"
echo "  - metadata.json     # Episode元数据"
echo "  - sync_report.json  # 时间同步报告"
echo "  - frequency_report.json  # 频率分析报告"
echo ""
echo "下一步："
echo "  1. 查看同步报告: cat $EPISODE_DIR/sync_report.json"
echo "  2. 查看频率报告: cat $EPISODE_DIR/frequency_report.json"
echo "  3. 分析性能指标: python3 scripts/analyze_episode.py $EPISODE_DIR"
echo ""