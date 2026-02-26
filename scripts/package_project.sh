#!/bin/bash
# VIST项目打包脚本
# 用于创建可分发的项目压缩包

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VIST项目打包脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 项目根目录
PROJECT_ROOT="$HOME/Dev/VIST"
if [ ! -d "$PROJECT_ROOT" ]; then
    echo -e "${RED}错误: VIST项目目录不存在: $PROJECT_ROOT${NC}"
    exit 1
fi

cd "$PROJECT_ROOT/.."

# 输出文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="VIST_${TIMESTAMP}.tar.gz"

echo -e "${GREEN}项目目录: $PROJECT_ROOT${NC}"
echo -e "${GREEN}输出文件: $OUTPUT_FILE${NC}"
echo ""

# 排除的目录和文件
EXCLUDE_PATTERNS=(
    "build"
    "install"
    "log"
    ".git"
    "__pycache__"
    "*.pyc"
    "*.pyo"
    ".vscode"
    ".idea"
    "*.bag"
    "data/experiments/*"
    ".ros"
)

# 构建tar命令的排除参数
EXCLUDE_ARGS=""
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=VIST/$pattern"
done

echo -e "${YELLOW}排除以下内容:${NC}"
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    echo "  - $pattern"
done
echo ""

echo -e "${GREEN}开始打包...${NC}"

# 创建压缩包
tar -czf "$OUTPUT_FILE" $EXCLUDE_ARGS VIST/

# 检查结果
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo -e "${GREEN}打包完成！${NC}"
    echo -e "文件: $OUTPUT_FILE"
    echo -e "大小: $FILE_SIZE"
    echo ""
    echo -e "${YELLOW}使用方法:${NC}"
    echo "1. 将 $OUTPUT_FILE 传输到目标机器"
    echo "2. 解压: tar -xzf $OUTPUT_FILE"
    echo "3. 参考 docs/ENVIRONMENT_SETUP.md 配置环境"
    echo "4. 参考 docs/FINAL_STARTUP_GUIDE.md 启动系统"
else
    echo -e "${RED}打包失败！${NC}"
    exit 1
fi
