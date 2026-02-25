#!/bin/bash
# 验证 simulate_full_flow.py 的修改

echo "验证 simulate_full_flow.py 的高频插值集成..."
echo ""

FILE="scripts/experiments/simulate_full_flow.py"

# 检查5个关键修改
echo "检查修改点："
echo ""

# 1. 导入
if grep -q "from simulation_ros2_publisher import SimulationPublisherWrapper" "$FILE" && \
   grep -q "from high_frequency_publisher import HighFrequencyPublisher" "$FILE"; then
    echo "✓ [1/5] 导入已添加"
else
    echo "✗ [1/5] 导入缺失"
fi

# 2. 初始化
if grep -q "self.ros2_publisher = SimulationPublisherWrapper" "$FILE" && \
   grep -q "self.high_freq_pub = HighFrequencyPublisher" "$FILE" && \
   grep -q "self.enable_simple_filter" "$FILE"; then
    echo "✓ [2/5] 初始化代码已添加"
else
    echo "✗ [2/5] 初始化代码缺失"
fi

# 3. 启动
if grep -q "self.high_freq_pub.start(q_init=init_q)" "$FILE"; then
    echo "✓ [3/5] 启动代码已添加"
else
    echo "✗ [3/5] 启动代码缺失"
fi

# 4. 滤波和发布
if grep -q "self.q_filtered" "$FILE" && \
   grep -q "self.high_freq_pub.update_target" "$FILE"; then
    echo "✓ [4/5] 滤波和发布代码已添加"
else
    echo "✗ [4/5] 滤波和发布代码缺失"
fi

# 5. 清理
if grep -q "self.high_freq_pub.stop()" "$FILE" && \
   grep -q "self.ros2_publisher.shutdown()" "$FILE"; then
    echo "✓ [5/5] 清理代码已添加"
else
    echo "✗ [5/5] 清理代码缺失"
fi

echo ""
echo "验证完成！"
echo ""
echo "下一步："
echo "1. 运行测试: ./scripts/run_vision_control_test.sh"
echo "2. 或手动启动: python3 scripts/experiments/simulate_full_flow.py"
