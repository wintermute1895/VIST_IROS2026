#!/bin/bash
# 停止VIST Web控制台

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}停止VIST Web控制台...${NC}"

# 从PID文件读取进程ID
if [ -f "logs/web_backend.pid" ]; then
    BACKEND_PID=$(cat logs/web_backend.pid)
    kill $BACKEND_PID 2>/dev/null
    rm logs/web_backend.pid
    echo -e "${GREEN}✓ 后端服务器已停止${NC}"
fi

if [ -f "logs/web_frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/web_frontend.pid)
    kill $FRONTEND_PID 2>/dev/null
    rm logs/web_frontend.pid
    echo -e "${GREEN}✓ 前端服务器已停止${NC}"
fi

echo -e "${GREEN}VIST Web控制台已停止${NC}"
