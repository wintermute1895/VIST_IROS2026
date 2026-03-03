#!/bin/bash
# 快速启用死锁测试（手动版本）

echo "=========================================="
echo "快速启用死锁测试"
echo "=========================================="
echo ""

cd /home/ilex/Dev/VIST

echo "修改代码以启用死锁测试..."
echo ""

# 在 update 函数开始处插入测试代码
cat > /tmp/deadlock_patch.py << 'EOF'
        self.iteration_count += 1

        # ==========================================
        # 🔬 死锁测试模式 - 已启用
        # ==========================================
        ENABLE_DEADLOCK_TEST = True
        if ENABLE_DEADLOCK_TEST:
            alpha = 1.0  # 锁定为全约束模式
            shadow_joints = self.state[:self.n_joints]  # 观测值=当前状态
            print(f"[DEADLOCK TEST] α={alpha:.3f}, using internal state as observation")
            # 跳过意图检测，直接使用锁定的alpha
            self.alpha = alpha
            self.alpha_smoothed = alpha
            # 继续执行后续步骤...
EOF

echo "测试代码已准备"
echo ""
echo "⚠️ 注意：这个脚本只是演示"
echo ""
echo "请手动编辑文件进行测试："
echo "  文件: ros2_ws/src/core/vist_kalman_filter.py"
echo "  位置: update() 方法开始处（第546行之后）"
echo ""
echo "插入以下代码："
echo "----------------------------------------"
cat /tmp/deadlock_patch.py
echo "----------------------------------------"
echo ""
echo "然后重启节点:"
echo "  pkill -f vist_filter_node"
echo "  source ros2_ws/install/setup.bash"
echo "  python3 ros2_ws/src/nodes/vist_filter_node.py \\"
echo "      --ros-args --params-file config/baseline_filters_config.yaml &"
echo ""