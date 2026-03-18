#!/bin/bash
# 数据流诊断脚本 - 追踪数据从LinkerTA到可视化的完整路径

echo "=========================================="
echo "  数据流完整诊断"
echo "=========================================="
echo ""

echo "1. 检查LinkerTA原始输出"
echo "----------------------------------------"
echo "话题: /left_arm_joint_control"
echo "等待数据（最多5秒）..."
echo ""
LEFT_RAW=$(timeout 5 ros2 topic echo /left_arm_joint_control --once 2>/dev/null)
if [ -n "$LEFT_RAW" ]; then
    echo "$LEFT_RAW" | grep "position:"
    # 提取第一个关节角度
    FIRST_JOINT=$(echo "$LEFT_RAW" | grep -A1 "position:" | tail -1 | tr -d ' ')
    echo "第一个关节值: $FIRST_JOINT"

    if [ "$FIRST_JOINT" == "0.0" ] || [ "$FIRST_JOINT" == "0" ]; then
        echo "⚠️  LinkerTA输出全是0！"
        echo "   可能原因："
        echo "   1. 遥操臂没有移动"
        echo "   2. 遥操臂未正确连接"
        echo "   3. 需要标定LinkerTA"
    else
        echo "✓ LinkerTA输出正常（非零）"
    fi
else
    echo "✗ 无法读取LinkerTA数据"
fi

echo ""
echo "2. 检查滤波节点输出"
echo "----------------------------------------"
echo "话题: /filtered_left_joint_control"
echo ""
LEFT_FILTERED=$(timeout 1 ros2 topic echo /filtered_left_joint_control --once 2>/dev/null)
if [ -n "$LEFT_FILTERED" ]; then
    echo "$LEFT_FILTERED" | grep "position:"
    # 提取第一个关节角度
    FIRST_JOINT_FILTERED=$(echo "$LEFT_FILTERED" | grep -A1 "position:" | tail -1 | tr -d ' ')
    echo "第一个关节值: $FIRST_JOINT_FILTERED"

    if [ "$FIRST_JOINT_FILTERED" == "0.0" ] || [ "$FIRST_JOINT_FILTERED" == "0" ]; then
        echo "⚠️  滤波节点输出全是0！"
        echo "   可能原因："
        echo "   1. 滤波器初始化失败"
        echo "   2. 单位转换错误"
        echo "   3. 滤波器配置问题"
    else
        echo "✓ 滤波节点输出正常（非零）"
    fi
else
    echo "✗ 无法读取滤波节点数据"
fi

echo ""
echo "3. 数据对比"
echo "----------------------------------------"
if [ -n "$FIRST_JOINT" ] && [ -n "$FIRST_JOINT_FILTERED" ]; then
    echo "LinkerTA输出:  $FIRST_JOINT"
    echo "滤波后输出:    $FIRST_JOINT_FILTERED"

    if [ "$FIRST_JOINT" != "0.0" ] && [ "$FIRST_JOINT_FILTERED" == "0.0" ]; then
        echo ""
        echo "🔴 问题定位: 滤波节点把非零数据变成了0"
        echo ""
        echo "建议操作："
        echo "1. 检查滤波节点日志"
        echo "2. 尝试使用GELLO直通模式"
        echo "3. 检查单位转换代码"
    elif [ "$FIRST_JOINT" == "0.0" ]; then
        echo ""
        echo "🔴 问题定位: LinkerTA输出就是0"
        echo ""
        echo "建议操作："
        echo "1. 移动遥操臂"
        echo "2. 检查LinkerTA连接"
        echo "3. 可能需要标定LinkerTA"
    else
        echo ""
        echo "✓ 数据流正常"
    fi
fi

echo ""
echo "4. 实时监控（5秒）"
echo "----------------------------------------"
echo "监控LinkerTA输出变化..."
echo ""

# 监控5秒，看数据是否变化
SAMPLES=5
for i in $(seq 1 $SAMPLES); do
    SAMPLE=$(timeout 1 ros2 topic echo /left_arm_joint_control --once 2>/dev/null | grep -A1 "position:" | tail -1 | awk '{print $1}')
    echo "样本 $i: $SAMPLE"
    sleep 1
done

echo ""
echo "如果所有样本都是0.0，请移动遥操臂后重新运行此脚本"
echo "=========================================="