#!/bin/bash
# 重启 Foxglove Bridge（自动清理旧进程）

echo "=========================================="
echo "重启 Foxglove Bridge"
echo "=========================================="
echo ""

# 1. 检查是否有旧进程
echo "【1】检查现有进程..."
EXISTING_PID=$(pgrep -f foxglove_bridge)

if [ -n "$EXISTING_PID" ]; then
    echo "  发现现有进程: $EXISTING_PID"
    echo "  正在停止..."
    pkill -9 foxglove_bridge
    sleep 1
    echo "  ✓ 已停止"
else
    echo "  ✓ 无现有进程"
fi

echo ""

# 2. 检查端口占用
echo "【2】检查端口 8765..."
PORT_USED=$(lsof -i :8765 2>/dev/null)

if [ -n "$PORT_USED" ]; then
    echo "  ⚠ 端口 8765 仍被占用:"
    echo "$PORT_USED"
    echo ""
    echo "  正在强制释放..."
    fuser -k 8765/tcp 2>/dev/null
    sleep 1
    echo "  ✓ 端口已释放"
else
    echo "  ✓ 端口可用"
fi

echo ""

# 3. 启动新的 Foxglove Bridge
echo "【3】启动 Foxglove Bridge..."
echo ""

ros2 launch foxglove_bridge foxglove_bridge_launch.xml