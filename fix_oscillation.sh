#!/bin/bash
# 修复算法内部自激震荡问题

echo "=========================================="
echo "VIST 自激震荡修复"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

echo "诊断结果: 死锁测试后还在抖"
echo "结论: 算法内部自激震荡"
echo ""

echo "1. 当前参数检查"
echo "----------------------------------------"
echo ""

echo "过程噪声 Q:"
grep -A 2 "position_variance:" config/system_config.yaml | grep -v "^--"

echo ""
echo "约束方差 Sigma_cons:"
grep "cons_variance_xyz:" config/system_config.yaml | grep -v "#"

echo ""
echo "时间步长 dt:"
grep "dt: 0.0125" config/system_config.yaml | head -1

echo ""
echo "2. 问题分析"
echo "----------------------------------------"
echo ""
echo "自激震荡的可能原因:"
echo ""
echo "原因1: 约束方差过小"
echo "  当前: cons_variance_xyz = [0.1, 0.1, 1.0]"
echo "  问题: 0.1 rad² 仍然较小（约5.7°）"
echo "  结果: 卡尔曼增益 K 过大，对微小扰动敏感"
echo ""
echo "原因2: 过程噪声过大"
echo "  当前: position_variance = 1e-4, velocity_variance = 1e-3"
echo "  问题: 如果 Q 太大，P_pred 会增长，导致 K 增大"
echo "  结果: 系统不稳定"
echo ""
echo "原因3: dt 计算错误"
echo "  当前: dt = 0.0125s (80Hz)"
echo "  问题: 如果实际 dt 与配置不符，F 矩阵会错误"
echo "  结果: 状态预测不准确"
echo ""

echo "3. 修复方案"
echo "----------------------------------------"
echo ""

# 备份配置
cp config/system_config.yaml config/system_config.yaml.backup_oscillation

echo "方案A: 大幅放宽约束方差（推荐）"
echo "  cons_variance_xyz: [0.1, 0.1, 1.0] → [0.5, 0.5, 1.0]"
echo "  效果: 降低卡尔曼增益，减少对扰动的敏感度"
echo ""

echo "方案B: 减小过程噪声"
echo "  position_variance: 1e-4 → 1e-5"
echo "  velocity_variance: 1e-3 → 1e-4"
echo "  效果: 降低 P_pred，从而降低卡尔曼增益"
echo ""

echo "方案C: 增大观测噪声"
echo "  human_base_variance: 1e-2 → 1e-1"
echo "  效果: 增大 R，降低卡尔曼增益"
echo ""

echo "应用综合修复方案..."
echo ""

# 方案A: 放宽约束方差
sed -i 's/cons_variance_xyz: \[0.1, 0.1, 1.0\]/cons_variance_xyz: [0.5, 0.5, 1.0]/' config/system_config.yaml
echo "✓ 已放宽约束方差: 0.1 → 0.5"

# 方案B: 减小过程噪声
sed -i 's/position_variance: 1e-4/position_variance: 1e-5/' config/system_config.yaml
sed -i 's/velocity_variance: 1e-3/velocity_variance: 1e-4/' config/system_config.yaml
echo "✓ 已减小过程噪声: position 1e-4→1e-5, velocity 1e-3→1e-4"

# 方案C: 增大观测噪声
sed -i 's/human_base_variance: 1e-2/human_base_variance: 5e-2/' config/system_config.yaml
echo "✓ 已增大观测噪声: 1e-2 → 5e-2"

echo ""
echo "4. 验证修改"
echo "----------------------------------------"
echo ""

echo "新的约束方差:"
grep "cons_variance_xyz:" config/system_config.yaml | grep -v "#"

echo ""
echo "新的过程噪声:"
grep -A 2 "position_variance:" config/system_config.yaml | grep -v "^--"

echo ""
echo "新的观测噪声:"
grep "human_base_variance:" config/system_config.yaml | grep -v "#"

echo ""
echo "5. 理论分析"
echo "----------------------------------------"
echo ""
echo "卡尔曼增益公式:"
echo "  K = P_pred @ H^T @ inv(H @ P_pred @ H^T + R)"
echo ""
echo "其中:"
echo "  P_pred = F @ P @ F^T + Q  (过程噪声影响)"
echo "  R = 观测噪声"
echo ""
echo "修复效果:"
echo "  1. 增大 R (观测噪声) → K 减小"
echo "  2. 减小 Q (过程噪声) → P_pred 减小 → K 减小"
echo "  3. 放宽约束方差 → 即使 K 较大，系统也更柔顺"
echo ""
echo "预期结果:"
echo "  K 从 0.8-0.9 降低到 0.3-0.5"
echo "  系统更稳定，不再自激震荡"
echo ""

echo "6. 重启节点测试"
echo "----------------------------------------"
echo ""

# 停止节点
pkill -f "vist_filter_node.py"
sleep 2

# 启动节点
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_oscillation_fix.log 2>&1 &

VIST_PID=$!
echo "✓ 节点已重启 (PID: $VIST_PID)"
echo ""

sleep 3

if ps -p $VIST_PID > /dev/null; then
    echo "✓ 节点运行正常"
else
    echo "✗ 节点启动失败"
    echo "查看日志: tail -50 /tmp/vist_oscillation_fix.log"
    exit 1
fi

echo ""
echo "7. 测试建议"
echo "----------------------------------------"
echo ""
echo "保持死锁测试模式启用，观察是否还抖动"
echo ""
echo "如果还在抖:"
echo "  1. 进一步放宽约束: cons_variance_xyz: [1.0, 1.0, 1.0]"
echo "  2. 进一步减小过程噪声: position_variance: 1e-6"
echo "  3. 检查 dt 计算（添加日志打印实际 dt）"
echo ""
echo "如果不抖了:"
echo "  1. 禁用死锁测试"
echo "  2. 测试正常模式是否还抖动"
echo "  3. 如果正常模式还抖，说明是外部输入问题"
echo ""

echo "=========================================="
echo "修复完成"
echo "=========================================="
echo ""
echo "节点日志: tail -f /tmp/vist_oscillation_fix.log"
echo "恢复备份: cp config/system_config.yaml.backup_oscillation config/system_config.yaml"
echo ""