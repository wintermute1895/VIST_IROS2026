#!/bin/bash
# 验证逻辑修复效果

echo "=========================================="
echo "VIST 逻辑修复验证"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

echo "1. 检查代码修改"
echo "----------------------------------------"
echo ""

echo "✅ 修复1: 速度计算使用卡尔曼状态估计"
grep -n "joint_vel_estimate = self.state\[self.n_joints:\]" ros2_ws/src/core/vist_kalman_filter.py && echo "   已应用" || echo "   ❌ 未找到"

echo ""
echo "✅ 修复2: 动态更新F矩阵"
grep -n "actual_dt = current_time - self.last_update_time" ros2_ws/src/core/vist_kalman_filter.py && echo "   已应用" || echo "   ❌ 未找到"

echo ""
echo "✅ 修复3: 移除previous_shadow_joints更新"
grep -n "self.previous_shadow_joints = shadow_joints.copy()" ros2_ws/src/core/vist_kalman_filter.py && echo "   ❌ 仍存在（应该已删除）" || echo "   已移除"

echo ""
echo "2. 重启VIST节点"
echo "----------------------------------------"
echo ""

# 停止现有节点
pkill -f "vist_filter_node.py"
sleep 2

# 启动新节点
source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash
python3 ros2_ws/src/nodes/vist_filter_node.py \
    --ros-args \
    --params-file config/baseline_filters_config.yaml \
    > /tmp/vist_logic_fix.log 2>&1 &

VIST_PID=$!
echo "节点已重启 (PID: $VIST_PID)"
echo ""

# 等待初始化
echo "3. 等待节点初始化..."
sleep 3

# 检查节点是否运行
if ps -p $VIST_PID > /dev/null; then
    echo "   ✓ 节点运行正常"
else
    echo "   ✗ 节点启动失败"
    echo "   查看日志: tail -50 /tmp/vist_logic_fix.log"
    exit 1
fi

echo ""
echo "4. 测试意图因子"
echo "----------------------------------------"
echo ""

echo "当前意图因子 (观察α_vel是否更稳定):"
timeout 2 ros2 topic echo /vist_intent_factors --once 2>&1 | grep -A 5 "data:"

echo ""
echo "5. 预期改进"
echo "----------------------------------------"
echo ""
echo "修复后应该看到:"
echo "  1. α_vel 不再总是1.0，而是在0.5-0.9之间波动"
echo "  2. α 值更稳定，波动更小"
echo "  3. 机械臂响应更平滑"
echo ""
echo "但主要抖动问题仍需参数修复:"
echo "  运行: ./fix_shaking.sh"
echo ""

echo "=========================================="
echo "验证完成"
echo "=========================================="
echo ""
echo "节点日志: tail -f /tmp/vist_logic_fix.log"
echo "意图因子: ros2 topic echo /vist_intent_factors"
echo ""
