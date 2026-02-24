#!/bin/bash
# 只启动VIST后端API服务器

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VIST 后端API服务器${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否在正确的目录
if [ ! -d "web/backend" ]; then
    echo -e "${RED}错误: 请在VIST项目根目录运行此脚本${NC}"
    exit 1
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到Python3${NC}"
    exit 1
fi

# 安装依赖
echo -e "\n${YELLOW}检查后端依赖...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}安装后端依赖...${NC}"
    pip install -r web/backend/requirements.txt
fi

# 创建日志目录
mkdir -p logs

# 启动后端
echo -e "\n${YELLOW}启动后端服务器...${NC}"
cd web/backend
python3 main.py &
BACKEND_PID=$!
cd ../..

# 等待启动
sleep 2

# 检查是否启动成功
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}错误: 后端启动失败${NC}"
    exit 1
fi

# 保存PID
echo $BACKEND_PID > logs/web_backend.pid

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  后端API服务器已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}API地址: http://localhost:8000${NC}"
echo -e "${BLUE}API文档: http://localhost:8000/docs${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${YELLOW}提示:${NC}"
echo -e "  - 在浏览器中打开 http://localhost:8000/docs 查看API"
echo -e "  - 按 Ctrl+C 停止服务器"
echo -e "${GREEN}========================================${NC}\n"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止服务器...${NC}"
    kill $BACKEND_PID 2>/dev/null
    rm -f logs/web_backend.pid
    echo -e "${GREEN}服务器已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 保持脚本运行
wait
