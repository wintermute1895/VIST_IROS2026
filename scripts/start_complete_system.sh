#!/bin/bash
# 完整的右臂测试启动脚本（修复版）
# Complete Right Arm Test Startup Script (Fixed)

echo "=========================================="
echo "右臂单独测试 - 完整启动脚本"
echo "=========================================="
echo ""
echo "此脚本将在5个终端中启动所有必要的节点"
echo "请确保:"
echo "  1. 机械臂已通过web控制器使能"
echo "  2. 急停按钮在手边"
echo "  3. 工作空间安全"
echo ""
read -p "按Enter继续..."

# 检查tmux是否安装
if ! command -v tmux &> /dev/null; then
    echo "错误: 需要安装tmux"
    echo "运行: sudo apt install tmux"
    exit 1
fi

# 创建新的tmux会话
SESSION="right_arm_test"
tmux kill-session -t $SESSION 2>/dev/null

# 创建会话和窗口
tmux new-session -d -s $SESSION -n "lbot_driver"

# 窗口1: lbot_driver
tmux send-keys -t $SESSION:0 "cd /home/ilex/Dev/VIST/external_sdk/arm_teleop" C-m
tmux send-keys -t $SESSION:0 "source install/setup.bash" C-m
tmux send-keys -t $SESSION:0 "echo '启动 lbot_driver...'" C-m
tmux send-keys -t $SESSION:0 "ros2 run lbot_driver lbot_driver --ros-args --params-file src/lbot_driver/config/lbot_config.yaml" C-m

sleep 2

# 窗口2: linkerta
tmux new-window -t $SESSION:1 -n "linkerta"
tmux send-keys -t $SESSION:1 "echo '启动 linkerta (外骨骼)...'" C-m
tmux send-keys -t $SESSION:1 "ros2 run linkerta linkerta_node --ros-args -p publish_left:=false -p publish_right:=true" C-m

sleep 2

# 窗口3: filter
tmux new-window -t $SESSION:2 -n "filter"
tmux send-keys -t $SESSION:2 "cd /home/ilex/Dev/VIST" C-m
tmux send-keys -t $SESSION:2 "echo '启动 unified_filter_node (无滤波)...'" C-m
tmux send-keys -t $SESSION:2 "./scripts/start_right_arm_filter.sh none" C-m

sleep 2

# 窗口4: teleop_bridge (使用topic remap修复话题名称)
tmux new-window -t $SESSION:3 -n "teleop"
tmux send-keys -t $SESSION:3 "cd /home/ilex/Dev/VIST/external_sdk/arm_teleop" C-m
tmux send-keys -t $SESSION:3 "source install/setup.bash" C-m
tmux send-keys -t $SESSION:3 "echo '启动 teleop_bridge (带话题重映射)...'" C-m
tmux send-keys -t $SESSION:3 "ros2 run lbot_teleop teleop_bridge_node --ros-args --params-file src/lbot_teleop/config/teleop_bridge_params.yaml --ros-args -r /robot1/right_arm/joint_follow:=/right_arm/joint_follow -r /robot1/left_arm/joint_follow:=/left_arm/joint_follow" C-m

sleep 2

# 窗口5: 监控
tmux new-window -t $SESSION:4 -n "monitor"
tmux send-keys -t $SESSION:4 "cd /home/ilex/Dev/VIST" C-m
tmux send-keys -t $SESSION:4 "echo '等待5秒让所有节点启动...'" C-m
tmux send-keys -t $SESSION:4 "sleep 5" C-m
tmux send-keys -t $SESSION:4 "echo ''" C-m
tmux send-keys -t $SESSION:4 "echo '========================================'" C-m
tmux send-keys -t $SESSION:4 "echo '系统状态检查'" C-m
tmux send-keys -t $SESSION:4 "echo '========================================'" C-m
tmux send-keys -t $SESSION:4 "./scripts/check_topic_safety.sh" C-m

# 附加到会话
echo ""
echo "=========================================="
echo "所有节点已启动！"
echo "=========================================="
echo ""
echo "tmux窗口:"
echo "  0: lbot_driver"
echo "  1: linkerta"
echo "  2: filter"
echo "  3: teleop_bridge"
echo "  4: monitor"
echo ""
echo "切换窗口: Ctrl+b 然后按数字键 (0-4)"
echo "退出tmux: Ctrl+b 然后按 d"
echo "停止所有: tmux kill-session -t right_arm_test"
echo ""
echo "附加到tmux会话..."
sleep 2
tmux attach-session -t $SESSION
