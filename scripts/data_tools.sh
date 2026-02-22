#!/bin/bash
# 数据录制与回放快速启动脚本
# 提供常用的录制和回放命令

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 数据目录
DATA_DIR="$PROJECT_ROOT/data/recordings"
mkdir -p "$DATA_DIR"

# 显示菜单
show_menu() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}📹 VIST 数据录制与回放工具${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    echo "1) 录制标准测试数据 (60秒)"
    echo "2) 录制快速测试数据 (30秒)"
    echo "3) 回放最新录制的数据"
    echo "4) 循环回放最新录制的数据"
    echo "5) 查看所有录制文件"
    echo "6) 删除所有录制文件"
    echo "0) 退出"
    echo ""
    echo -e "${YELLOW}请选择操作:${NC} "
}

# 录制数据
record_data() {
    local duration=$1
    local filename="recording_$(date +%Y%m%d_%H%M%S).jsonl"
    local filepath="$DATA_DIR/$filename"

    echo -e "${GREEN}📹 开始录制...${NC}"
    echo -e "${YELLOW}文件: $filepath${NC}"
    echo -e "${YELLOW}时长: ${duration}秒${NC}"
    echo ""
    echo -e "${RED}⚠️  请确保视觉节点正在运行！${NC}"
    echo -e "${YELLOW}按 Enter 继续，或 Ctrl+C 取消...${NC}"
    read

    python scripts/record_vision_data.py "$filepath" --duration "$duration"

    echo ""
    echo -e "${GREEN}✅ 录制完成！${NC}"
    echo -e "${YELLOW}文件: $filepath${NC}"
}

# 回放数据
playback_data() {
    local loop=$1
    local latest_file=$(ls -t "$DATA_DIR"/*.jsonl 2>/dev/null | head -n 1)

    if [ -z "$latest_file" ]; then
        echo -e "${RED}❌ 没有找到录制文件${NC}"
        echo -e "${YELLOW}请先录制数据（选项 1 或 2）${NC}"
        return
    fi

    echo -e "${GREEN}▶️  回放数据...${NC}"
    echo -e "${YELLOW}文件: $latest_file${NC}"
    echo ""
    echo -e "${RED}⚠️  请确保控制器正在运行！${NC}"
    echo -e "${YELLOW}按 Enter 继续，或 Ctrl+C 取消...${NC}"
    read

    if [ "$loop" = "true" ]; then
        python scripts/playback_vision_data.py "$latest_file" --loop
    else
        python scripts/playback_vision_data.py "$latest_file"
    fi
}

# 查看录制文件
list_recordings() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}📂 录制文件列表${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""

    if [ ! -d "$DATA_DIR" ] || [ -z "$(ls -A "$DATA_DIR" 2>/dev/null)" ]; then
        echo -e "${YELLOW}没有录制文件${NC}"
        return
    fi

    local count=0
    for file in "$DATA_DIR"/*.jsonl; do
        if [ -f "$file" ]; then
            count=$((count + 1))
            local size=$(du -h "$file" | cut -f1)
            local frames=$(wc -l < "$file")
            local basename=$(basename "$file")
            echo -e "${GREEN}$count)${NC} $basename"
            echo -e "   大小: $size | 帧数: $frames"
            echo ""
        fi
    done

    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}没有录制文件${NC}"
    fi
}

# 删除录制文件
delete_recordings() {
    echo -e "${RED}⚠️  警告: 这将删除所有录制文件！${NC}"
    echo -e "${YELLOW}确认删除? (yes/no):${NC} "
    read confirm

    if [ "$confirm" = "yes" ]; then
        rm -rf "$DATA_DIR"/*.jsonl
        echo -e "${GREEN}✅ 已删除所有录制文件${NC}"
    else
        echo -e "${YELLOW}已取消${NC}"
    fi
}

# 主循环
while true; do
    show_menu
    read choice

    case $choice in
        1)
            record_data 60
            ;;
        2)
            record_data 30
            ;;
        3)
            playback_data false
            ;;
        4)
            playback_data true
            ;;
        5)
            list_recordings
            ;;
        6)
            delete_recordings
            ;;
        0)
            echo -e "${GREEN}再见！${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}无效选项${NC}"
            ;;
    esac

    echo ""
    echo -e "${YELLOW}按 Enter 继续...${NC}"
    read
    clear
done