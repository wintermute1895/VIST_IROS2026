#!/bin/bash
# VIST 死锁测试 - 诊断抖动来源

echo "=========================================="
echo "VIST 死锁测试（Deadlock Test）"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

# 检查参数
if [ "$1" == "enable" ]; then
    MODE="enable"
elif [ "$1" == "disable" ]; then
    MODE="disable"
else
    echo "用法: $0 [enable|disable]"
    echo ""
    echo "enable  - 启用死锁测试模式"
    echo "disable - 禁用死锁测试模式（恢复正常）"
    echo ""
    exit 1
fi

echo "模式: $MODE"
echo ""

# 备份文件
FILTER_FILE="ros2_ws/src/core/vist_kalman_filter.py"
BACKUP_FILE="${FILTER_FILE}.backup_deadlock"

if [ "$MODE" == "enable" ]; then
    echo "1. 启用死锁测试模式"
    echo "----------------------------------------"

    # 备份原文件
    cp "$FILTER_FILE" "$BACKUP_FILE"
    echo "   ✓ 已备份原文件"

    # 取消注释测试代码
    sed -i 's/^        # ENABLE_DEADLOCK_TEST = True/        ENABLE_DEADLOCK_TEST = True/' "$FILTER_FILE"
    sed -i 's/^        # if ENABLE_DEADLOCK_TEST:/        if ENABLE_DEADLOCK_TEST:/' "$FILTER_FILE"
    sed -i 's/^        #     alpha = 1.0/            alpha = 1.0/' "$FILTER_FILE"
    sed -i 's/^        #     shadow_joints = self.state/            shadow_joints = self.state/' "$FILTER_FILE"
    sed -i 's/^        #     print(f"\[DEADLOCK TEST\]/            print(f"[DEADLOCK TEST]/' "$FILTER_FILE"
    sed -i 's/^        #     # 跳过意图检测/            # 跳过意图检测/' "$FILTER_FILE"
    sed -i 's/^        #     self.alpha = alpha/            self.alpha = alpha/' "$FILTER_FILE"
    sed -i 's/^        #     self.alpha_smoothed = alpha/            self.alpha_smoothed = alpha/' "$FILTER_FILE"
    sed -i 's/^        #     # 继续执行后续步骤/            # 继续执行后续步骤/' "$FILTER_FILE"

    echo "   ✓ 已启用死锁测试代码"

    echo ""
    echo "2. 测试配置"
    echo "----------------------------------------"
    echo "   - α 锁定为: 1.0（全约束模式）"
    echo "   - 观测值: 使用内部状态（不接受外部输入）"
    echo "   - 效果: 系统\"自己跟自己玩\""
    echo ""

elif [ "$MODE" == "disable" ]; then
    echo "1. 禁用死锁测试模式"
    echo "----------------------------------------"

    if [ -f "$BACKUP_FILE" ]; then
        # 恢复备份
        cp "$BACKUP_FILE" "$FILTER_FILE"
        rm "$BACKUP_FILE"
        echo "   ✓ 已恢复原文件"
    else
        # 注释测试代码
        sed -i 's/^        ENABLE_DEADLOCK_TEST = True/        # ENABLE_DEADLOCK_TEST = True/' "$FILTER_FILE"
        sed -i 's/^        if ENABLE_DEADLOCK_TEST:/        # if ENABLE_DEADLOCK_TEST:/' "$FILTER_FILE"
        sed -i 's/^            alpha = 1.0/        #     alpha = 1.0/' "$FILTER_FILE"
        sed -i 's/^            shadow_joints = self.state/        #     shadow_joints = self.state/' "$FILTER_FILE"
        sed -i 's/^            print(f"\[DEADLOCK TEST\]/        #     print(f"[DEADLOCK TEST]/' "$FILTER_FILE"
        sed -i 's/^            # 跳过意图检测/        #     # 跳过意图检测/' "$FILTER_FILE"
        sed -i 's/^            self.alpha = alpha/        #     self.alpha = alpha/' "$FILTER_FILE"
        sed -i 's/^            self.alpha_smoothed = alpha/        #     self.alpha_smoothed = alpha/' "$FILTER_FILE"
        sed -i 's/^            # 继续执行后续步骤/        #     # 继续执行后续步骤/' "$FILTER_FILE"

        echo "   ✓ 已禁用死锁测试代码"
    fi

    echo ""
    echo "2. 恢复正常模式"
    echo "----------------------------------------"
    echo "   - α: 动态计算"
    echo "   - 观测值: 接受外部输入"
    echo ""
fi

echo "3. 重启VIST节点"
echo "----------------------------------------"

# 停止现有节点
pkill -f "vist_filter_node.py"
sleep 2

# 启动新节点
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_deadlock_test.log 2>&1 &

VIST_PID=$!
echo "   ✓ 节点已重启 (PID: $VIST_PID)"
echo ""

# 等待初始化
echo "4. 等待节点初始化..."
sleep 3

if ps -p $VIST_PID > /dev/null; then
    echo "   ✓ 节点运行正常"
else
    echo "   ✗ 节点启动失败"
    echo "   查看日志: tail -50 /tmp/vist_deadlock_test.log"
    exit 1
fi

echo ""
echo "=========================================="
echo "诊断指南"
echo "=========================================="
echo ""

if [ "$MODE" == "enable" ]; then
    echo "死锁测试已启用，现在观察机械臂："
    echo ""
    echo "情况A: 机械臂不抖了"
    echo "  → 抖动来自外部输入或α跳变"
    echo "  → 可能原因："
    echo "    1. 遥操臂信号太脏（高频噪声）"
    echo "    2. α在0和1之间疯狂跳变（意图切换震荡）"
    echo "    3. 虚拟引导计算不稳定"
    echo "  → 解决方案："
    echo "    - 增加输入滤波"
    echo "    - 增加α平滑（intent_smoothing: 0.95）"
    echo "    - 检查虚拟引导计算"
    echo ""
    echo "情况B: 机械臂还在抖"
    echo "  → 抖动来自算法内部"
    echo "  → 可能原因："
    echo "    1. 卡尔曼增益过大（自激震荡）"
    echo "    2. 约束方差过紧（0.01太小）"
    echo "    3. 过程噪声设置不当"
    echo "  → 解决方案："
    echo "    - 放宽约束方差（0.01 → 0.1）"
    echo "    - 增加过程噪声"
    echo "    - 降低卡尔曼增益"
    echo ""
    echo "查看实时日志:"
    echo "  tail -f /tmp/vist_deadlock_test.log | grep DEADLOCK"
    echo ""
    echo "查看意图因子（应该锁定在1.0）:"
    echo "  ros2 topic echo /vist_intent_factors"
    echo ""

else
    echo "死锁测试已禁用，系统恢复正常运行"
    echo ""
    echo "如果需要再次测试:"
    echo "  $0 enable"
    echo ""
fi

echo "=========================================="