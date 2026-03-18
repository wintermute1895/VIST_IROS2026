#!/bin/bash
# 检查当前滤波器状态

echo "=========================================="
echo "VIST 滤波器状态检查"
echo "=========================================="
echo ""

# 1. 检查配置文件
echo "【1】配置文件中的滤波器类型:"
grep "filter_type:" config/baseline_filters_config.yaml | head -1
echo ""

# 2. 检查运行的节点
echo "【2】运行中的滤波节点:"
ros2 node list | grep vist_filter || echo "  未找到滤波节点"
echo ""

# 3. 检查节点参数
echo "【3】节点运行时参数:"
ros2 param get /vist_filter_node filter_type 2>/dev/null || echo "  节点未运行或参数不存在"
echo ""

# 4. 检查话题频率
echo "【4】话题发布频率:"
echo "  原始数据频率:"
timeout 3 ros2 topic hz /left_arm_joint_control 2>/dev/null | grep "average rate" || echo "    无数据"
echo "  滤波后频率:"
timeout 3 ros2 topic hz /filtered_left_joint_control 2>/dev/null | grep "average rate" || echo "    无数据"
echo ""

echo "=========================================="
echo "提示: 如果要切换滤波器，修改 config/baseline_filters_config.yaml"
echo "      然后重启滤波节点"
echo "=========================================="