#!/bin/bash
# 快速测试：录制数据 → 仿真验证工作流程
# 用于验证数据录制和回放功能是否正常工作

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🧪 录制数据 → 仿真验证测试${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 测试数据文件
TEST_DATA="data/recordings/quick_test.jsonl"
mkdir -p data/recordings

# Step 1: 检查视觉节点是否运行
echo -e "${YELLOW}Step 1: 检查视觉节点...${NC}"
if ! pgrep -f "vision_node_depth.py" > /dev/null; then
    echo -e "${YELLOW}⚠️  视觉节点未运行${NC}"
    echo -e "${YELLOW}   请在另一个终端运行: python src/nodes/vision_node_depth.py${NC}"
    echo ""
    read -p "视觉节点已启动？按 Enter 继续，或 Ctrl+C 取消... " answer
else
    echo -e "${GREEN}✅ 视觉节点正在运行${NC}"
fi
echo ""

# Step 2: 录制测试数据
echo -e "${YELLOW}Step 2: 录制测试数据（10秒）...${NC}"
echo -e "${YELLOW}   录制前有10秒倒计时，请准备好站到摄像头前${NC}"
echo ""
read -p "按 Enter 开始倒计时... " answer

python scripts/record_vision_data.py "$TEST_DATA" --duration 10 --countdown 10

if [ ! -f "$TEST_DATA" ]; then
    echo -e "${RED}❌ 录制失败：文件不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 录制完成${NC}"
echo ""

# Step 3: 在仿真环境中回放
echo -e "${YELLOW}Step 3: 在仿真环境中回放...${NC}"
echo -e "${YELLOW}   将在浏览器中打开 MeshCat 可视化${NC}"
echo -e "${YELLOW}   URL: http://127.0.0.1:7000/static/${NC}"
echo ""
read -p "按 Enter 启动仿真环境... " answer

# 启动仿真环境（后台）
python scripts/simulate_full_flow.py &
SIM_PID=$!

# 等待仿真环境启动
echo -e "${YELLOW}   等待仿真环境启动...${NC}"
sleep 3

# 回放数据
echo -e "${YELLOW}   开始回放数据...${NC}"
python scripts/playback_vision_data.py "$TEST_DATA"

# 等待回放完成
wait

# 清理
kill $SIM_PID 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ 测试完成！${NC}"
echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}📊 测试总结${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "录制文件: $TEST_DATA"
echo -e "文件大小: $(du -h "$TEST_DATA" | cut -f1)"
echo -e "帧数: $(wc -l < "$TEST_DATA")"
echo ""
echo -e "${YELLOW}下一步：${NC}"
echo -e "1. 如果仿真验证通过，可以部署到真机"
echo -e "2. 运行: python scripts/run_real_robot_vist_refactored.py --duration 60"
echo ""