#!/bin/bash
# 真机双臂完整启动指南

cat << 'EOF'
========================================
真机双臂完整启动指南
========================================

【前置条件】
----------------------------------------
✓ 遥操臂已连接（CAN1）
✓ 真机网络已连接（192.168.10.21）
✓ 所有配置文件已检查


【启动顺序】
----------------------------------------

终端1: LinkerTA节点
  cd /home/ilex/Dev/VIST
  ./launch_linkerta.sh

终端2: 左臂滤波节点
  cd /home/ilex/Dev/VIST
  ./launch_filter_left_unique.sh

终端3: 右臂滤波节点
  cd /home/ilex/Dev/VIST
  ./launch_filter_right_unique.sh

终端4: 真机驱动 ⭐ 新增
  cd /home/ilex/Dev/VIST
  ros2 launch lbot_driver lbot_start_driver.launch.py

终端5: 遥操桥接节点
  cd /home/ilex/Dev/VIST
  ./launch_bridge.sh

终端6: Meshcat可视化（可选）
  cd /home/ilex/Dev/VIST
  python3 visualize_dual_arm_realtime.py

终端7: rqt监控（可选）
  rqt


【验证步骤】
----------------------------------------

1. 检查所有节点运行:
   ros2 node list

   应该看到:
   /linkerta_node
   /vist_filter_node_left
   /vist_filter_node_right
   /robot1/lbot_main_node          ⭐ 真机驱动
   /robot1/lbot_left_arm_node      ⭐ 真机左臂
   /robot1/lbot_right_arm_node     ⭐ 真机右臂
   /teleop_bridge_node

2. 检查话题频率:
   ros2 topic hz /left_arm_joint_control          # 80Hz
   ros2 topic hz /filtered_left_joint_control     # 80Hz
   ros2 topic hz /robot1/left_arm/joint_follow    # 80Hz
   ros2 topic hz /robot1/left_arm/joint_states    # 真机反馈

3. 小心移动遥操臂:
   - 先移动小幅度
   - 观察真机是否跟随
   - 检查方向是否正确


【安全注意事项】⚠️
----------------------------------------
1. 首次测试时，保持小幅度运动
2. 确保急停按钮可用
3. 检查机械臂周围无障碍物
4. 随时准备按Ctrl+C停止
5. 如果方向不对，立即停止


【故障排查】
----------------------------------------

问题1: 真机驱动无法连接
  检查: ping 192.168.10.21
  检查: 网络配置是否正确

问题2: 真机不跟随
  检查: ros2 topic hz /robot1/left_arm/joint_follow
  检查: 桥接节点是否在真机驱动之后启动

问题3: 方向不对
  检查: config/joint_directions.yaml
  检查: teleop_bridge_params.yaml 的 negation 配置

问题4: 频率不稳定
  检查: 各个节点的日志
  检查: 网络延迟


【紧急停止】
----------------------------------------
方法1: 按下急停按钮
方法2: 在任意终端按 Ctrl+C
方法3: 运行: pkill -9 lbot_driver


【数据录制】（可选）
----------------------------------------
录制测试数据:
  ros2 bag record -a -o dual_arm_real_test

回放分析:
  ros2 bag play dual_arm_real_test


========================================
准备好了吗？
========================================

1. 运行配置检查:
   ./check_real_robot_config.sh

2. 确认网络连接:
   ping 192.168.10.21

3. 按照上面的顺序启动所有节点

4. 小心测试！

EOF