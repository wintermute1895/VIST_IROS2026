#!/bin/bash
# VIST Web控制台一键启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VIST Web控制台启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否在正确的目录
if [ ! -d "web" ]; then
    echo -e "${RED}错误: 请在VIST项目根目录运行此脚本${NC}"
    exit 1
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到Python3${NC}"
    exit 1
fi

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: 未找到Node.js${NC}"
    echo -e "${YELLOW}请安装Node.js: https://nodejs.org/${NC}"
    exit 1
fi

# 检查npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误: 未找到npm${NC}"
    exit 1
fi

# 检查后端依赖
echo -e "\n${YELLOW}[1/4] 检查后端依赖...${NC}"
if [ ! -f "web/backend/requirements.txt" ]; then
    echo -e "${RED}错误: 未找到requirements.txt${NC}"
    exit 1
fi

# 安装后端依赖（如果需要）
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}安装后端依赖...${NC}"
    pip install -r web/backend/requirements.txt
fi
echo -e "${GREEN}✓ 后端依赖已就绪${NC}"

# 检查前端依赖
echo -e "\n${YELLOW}[2/4] 检查前端依赖...${NC}"
if [ ! -d "web/frontend/node_modules" ]; then
    echo -e "${YELLOW}安装前端依赖（首次运行可能需要几分钟）...${NC}"
    cd web/frontend
    npm install
    cd ../..
fi
echo -e "${GREEN}✓ 前端依赖已就绪${NC}"

# 启动后端
echo -e "\n${YELLOW}[3/4] 启动后端服务器...${NC}"
cd web/backend
python3 main.py > ../../logs/web_backend.log 2>&1 &
BACKEND_PID=$!
cd ../..

# 等待后端启动
sleep 3

# 检查后端是否启动成功
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}错误: 后端启动失败${NC}"
    echo -e "${YELLOW}查看日志: logs/web_backend.log${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 后端服务器已启动 (PID: $BACKEND_PID)${NC}"
echo -e "${BLUE}   API地址: http://localhost:8000${NC}"
echo -e "${BLUE}   API文档: http://localhost:8000/docs${NC}"

# 启动前端
echo -e "\n${YELLOW}[4/4] 启动前端开发服务器...${NC}"
cd web/frontend
npm run dev > ../../logs/web_frontend.log 2>&1 &
FRONTEND_PID=$!
cd ../..

# 等待前端启动
sleep 3

# 检查前端是否启动成功
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}错误: 前端启动失败${NC}"
    echo -e "${YELLOW}查看日志: logs/web_frontend.log${NC}"
    kill $BACKEND_PID
    exit 1
fi
echo -e "${GREEN}✓ 前端服务器已启动 (PID: $FRONTEND_PID)${NC}"
echo -e "${BLUE}   前端地址: http://localhost:3000${NC}"

# 保存PID到文件
echo $BACKEND_PID > logs/web_backend.pid
echo $FRONTEND_PID > logs/web_frontend.pid

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  VIST Web控制台已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}前端: http://localhost:3000${NC}"
echo -e "${BLUE}后端: http://localhost:8000${NC}"
echo -e "${BLUE}API文档: http://localhost:8000/docs${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${YELLOW}提示:${NC}"
echo -e "  - 在浏览器中打开 http://localhost:3000"
echo -e "  - 按 Ctrl+C 停止服务器"
echo -e "  - 或运行: bash web/stop_web.sh"
echo -e "${GREEN}========================================${NC}\n"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止服务器...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    rm -f logs/web_backend.pid logs/web_frontend.pid
    echo -e "${GREEN}服务器已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 保持脚本运行
wait
