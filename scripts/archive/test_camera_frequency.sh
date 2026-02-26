#!/bin/bash
# 测试相机频率修复

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIST_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}相机频率测试${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    source /opt/ros/humble/setup.bash
fi

cd "$VIST_ROOT"
source install/setup.bash

# 启动相机（后台）
echo -e "${GREEN}[1/4] 启动相机节点...${NC}"
bash scripts/start_camera.sh > /tmp/camera_test.log 2>&1 &
CAMERA_PID=$!

# 等待启动
echo -e "${YELLOW}等待相机初始化（5秒）...${NC}"
sleep 5

# 检查节点
echo -e "${GREEN}[2/4] 检查节点状态...${NC}"
if ros2 node list | grep -q "realsense_camera"; then
    echo -e "${GREEN}✓ 相机节点已启动${NC}"
else
    echo -e "${RED}✗ 相机节点未找到${NC}"
    kill $CAMERA_PID 2>/dev/null || true
    exit 1
fi

# 检查话题
echo -e "${GREEN}[3/4] 检查话题...${NC}"
if ros2 topic list | grep -q "/camera/color/image_raw"; then
    echo -e "${GREEN}✓ 图像话题存在${NC}"
else
    echo -e "${RED}✗ 图像话题未找到${NC}"
    kill $CAMERA_PID 2>/dev/null || true
    exit 1
fi

# 检查频率
echo -e "${GREEN}[4/4] 测试发布频率（15秒）...${NC}"
echo -e "${YELLOW}预期频率: 25-30 Hz${NC}"
echo ""

timeout 15 ros2 topic hz /camera/color/image_raw 2>&1 | tee /tmp/camera_hz.log || true

# 分析结果
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}测试结果分析${NC}"
echo -e "${BLUE}========================================${NC}"

# 提取平均频率
AVG_RATE=$(grep "average rate:" /tmp/camera_hz.log | tail -1 | awk '{print $3}')

if [ -n "$AVG_RATE" ]; then
    echo -e "平均频率: ${GREEN}${AVG_RATE} Hz${NC}"

    # 判断是否合格
    if (( $(echo "$AVG_RATE > 25" | bc -l) )); then
        echo -e "${GREEN}✓ 频率测试通过（>25Hz）${NC}"
        RESULT="PASS"
    elif (( $(echo "$AVG_RATE > 15" | bc -l) )); then
        echo -e "${YELLOW}⚠ 频率偏低但可接受（15-25Hz）${NC}"
        RESULT="WARN"
    else
        echo -e "${RED}✗ 频率过低（<15Hz）${NC}"
        RESULT="FAIL"
    fi
else
    echo -e "${RED}✗ 无法获取频率数据${NC}"
    RESULT="ERROR"
fi

echo ""
echo -e "${YELLOW}按Ctrl+C停止相机节点...${NC}"

# 清理
trap "kill $CAMERA_PID 2>/dev/null || true; exit 0" INT TERM

wait $CAMERA_PID