#!/bin/bash
# 快速检查 CAN 通信的脚本

echo "======================================================================"
echo "LinkerHand CAN 通信快速检查"
echo "======================================================================"

# 检查 CAN 接口
echo ""
echo "1. CAN 接口状态:"
ip link show can0

# 检查波特率
echo ""
echo "2. CAN 波特率:"
ip -details link show can0 | grep bitrate

# 检查流量统计
echo ""
echo "3. CAN 流量统计:"
ifconfig can0 | grep -E "RX|TX"

# 提示监控 CAN 数据
echo ""
echo "======================================================================"
echo "4. 监控 CAN 数据 (按 Ctrl+C 停止):"
echo "======================================================================"
echo ""
echo "现在将监控 CAN 总线上的数据..."
echo "请在另一个终端运行手控制程序，观察是否有数据"
echo ""
echo "预期看到的数据格式:"
echo "  can0  027  [7]  01 XX XX XX XX XX XX  <- 前 6 个关节"
echo "  can0  027  [5]  04 XX XX XX XX        <- 后 4 个关节"
echo ""
echo "其中 027 是 CAN ID (0x27)"
echo ""

# 监控 CAN 数据
candump can0