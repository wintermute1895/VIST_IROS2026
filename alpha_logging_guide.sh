#!/bin/bash
# Alpha 记录和分析工具 - 使用指南

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║         VIST Alpha 记录和分析工具                            ║
╚══════════════════════════════════════════════════════════════╝

📊 方案对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

方案1: 异步话题订阅（推荐）✅
  - 性能影响: 无（独立进程）
  - 实时性: 80Hz 完整采样
  - 使用: python3 log_alpha.py

方案2: ROS2 bag 录制
  - 性能影响: 极小
  - 实时性: 完整记录
  - 使用: ros2 bag record /vist_intent_factors

方案3: 内存缓冲 + 延迟写入
  - 性能影响: 极小
  - 实时性: 80Hz 完整采样
  - 使用: 修改 VIST 代码启用

🚀 快速开始
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 启动 VIST 节点（如果还没启动）
   source ros2_ws/install/setup.bash
   python3 ros2_ws/src/nodes/vist_filter_node.py \
       --ros-args --params-file config/baseline_filters_config.yaml &

2. 启动 Alpha 记录器（新终端）
   source ros2_ws/install/setup.bash
   python3 log_alpha.py

3. 操作机械臂（执行你的测试任务）

4. 停止记录（Ctrl+C）

5. 分析数据
   python3 plot_alpha.py

📈 数据分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

plot_alpha.py 会生成3个图表:

图1: α 总值变化
  - 观察 α 是否在 0-1 之间合理变化
  - 检查是否有异常跳变

图2: α 分量（geo, vel, align）
  - 分析各分量的贡献
  - 检查哪个分量导致 α 异常

图3: α 变化率（震荡检测）
  - 检测高频震荡
  - 标注异常变化点

🔍 诊断指南
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

正常模式:
  ✓ α 在 0.3-0.7 之间平滑变化
  ✓ 变化率 < 5.0 /s
  ✓ 无频繁跳变

异常模式A: α 疯狂跳变
  ✗ α 在 0.1-0.9 之间快速震荡
  ✗ 变化率 > 10.0 /s
  → 原因: 意图检测不稳定
  → 解决: 增加 intent_smoothing

异常模式B: α 长期偏高
  ✗ α 持续 > 0.8
  ✗ 变化率正常
  → 原因: 几何因子或速度因子异常
  → 解决: 调整 w_geo, w_vel

异常模式C: α 长期偏低
  ✗ α 持续 < 0.2
  ✗ 变化率正常
  → 原因: 距离过远或速度过快
  → 解决: 检查目标位姿设置

🛠️ 高级用法
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 指定输出文件
python3 log_alpha.py --output my_test.csv

# 分析特定文件
python3 plot_alpha.py data/alpha_logs/alpha_log_20260302_143000.csv

# 使用 ROS2 bag（完整记录所有话题）
ros2 bag record -o my_test /vist_intent_factors /vist_performance

# 回放 bag 文件
ros2 bag play my_test

📁 文件位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

日志目录: ~/Dev/VIST/data/alpha_logs/
  - alpha_log_YYYYMMDD_HHMMSS.csv  (原始数据)
  - alpha_log_YYYYMMDD_HHMMSS_plot.png  (可视化图表)

CSV 格式:
  timestamp, elapsed_time, alpha, alpha_geo, alpha_vel, alpha_alignment

💡 提示
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 记录器是独立进程，不影响 VIST 性能
2. 可以同时运行多个记录器（不同输出文件）
3. 数据以 80Hz 采样，完整记录所有变化
4. 图表会自动检测震荡并标注异常点

EOF