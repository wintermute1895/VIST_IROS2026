#!/bin/bash
# 自动修复VIST抖动问题

echo "=========================================="
echo "VIST 抖动问题自动修复"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

# 备份原始配置
echo "1. 备份原始配置..."
cp config/system_config.yaml config/system_config.yaml.backup.$(date +%Y%m%d_%H%M%S)
echo "   ✓ 备份完成"
echo ""

# 应用修复
echo "2. 应用修复方案..."
echo ""

# 方案A: 放宽约束方差 (0.01 -> 0.1)
echo "   修复A: 放宽约束方差 (0.01 -> 0.1)"
sed -i 's/cons_variance_xyz: \[0.01, 0.01, 1.0\]/cons_variance_xyz: [0.1, 0.1, 1.0]/' config/system_config.yaml

# 方案B: 调整意图权重 (更跟随操作者)
echo "   修复B: 调整意图权重 (w_geo=0.3, w_vel=0.7)"
sed -i 's/w_geo: 0.5/w_geo: 0.3/' config/system_config.yaml
sed -i 's/w_vel: 0.5/w_vel: 0.7/' config/system_config.yaml

# 方案C: 增加意图平滑 (0.7 -> 0.9)
echo "   修复C: 增加意图平滑 (0.7 -> 0.9)"
sed -i 's/intent_smoothing: 0.7/intent_smoothing: 0.9/' config/system_config.yaml

# 方案D: 确保频率一致
echo "   修复D: 确保频率一致 (dt=0.0125)"
# 已经是0.0125，无需修改

echo ""
echo "   ✓ 所有修复已应用"
echo ""

# 显示修改内容
echo "3. 修改内容确认"
echo "----------------------------------------"
echo ""
echo "约束方差:"
grep "cons_variance_xyz:" config/system_config.yaml
echo ""
echo "意图权重:"
grep -E "w_geo:|w_vel:" config/system_config.yaml | grep -v "#"
echo ""
echo "意图平滑:"
grep "intent_smoothing:" config/system_config.yaml | grep -v "#"
echo ""

# 重启节点
echo "4. 重启VIST节点..."
echo "----------------------------------------"
pkill -f "vist_filter_node.py"
sleep 2

source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_fixed.log 2>&1 &

VIST_PID=$!
echo "   ✓ 节点已重启 (PID: $VIST_PID)"
echo ""

# 等待初始化
echo "5. 等待节点初始化..."
sleep 3

# 验证修复
echo ""
echo "6. 验证修复效果"
echo "----------------------------------------"
echo ""
echo "新的意图因子 (应该更低):"
timeout 2 ros2 topic echo /vist_intent_factors --once 2>&1 | grep -A 5 "data:"
echo ""

echo "=========================================="
echo "修复完成！"
echo "=========================================="
echo ""
echo "预期效果:"
echo "  - α值应该降低 (从0.88降到0.5-0.7)"
echo "  - 机械臂响应更灵敏"
echo "  - 抖动减少或消失"
echo ""
echo "如果仍有抖动，可以进一步放宽约束方差:"
echo "  cons_variance_xyz: [0.2, 0.2, 1.0]  # 更宽松"
echo ""
echo "查看节点日志: tail -f /tmp/vist_fixed.log"
echo "恢复备份: cp config/system_config.yaml.backup.* config/system_config.yaml"
echo ""