#!/bin/bash
# 外骨骼遥操完整测试 - 启动指南
# 请按照步骤在不同终端执行

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║     外骨骼遥操 + 数据手套 完整测试流程                        ║
╚══════════════════════════════════════════════════════════════╝

环境检查结果:
  ✅ 机器人已连接: 192.168.10.21
  ✅ RealSense相机: 348122071157, 327122074150
  ✅ CAN总线: can0 (UP)
  ✅ ROS2: humble

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【步骤1】启动数据手套驱动（可选，如果有数据手套）

在 终端1 执行:

cd ~/Dev/VIST/external_sdk/linkerhand-ros2-sdk
source install/setup.bash
ros2 launch linker_hand_ros2_sdk linker_hand.launch.py

预期输出:
  - "left L10 set speed to [200, 250, ...]"
  - "left L10 set maximum torque to [200, 200, ...]"

如果没有数据手套，跳过此步骤，继续步骤2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【步骤2】启动外骨骼遥操系统

在 终端2 执行:

cd ~/Dev/VIST/external_sdk/arm_teleop
source install/setup.bash
ros2 launch lbot_teleop teleop.launch.py

预期输出:
  - "[teleop.launch.py] 从臂配置:"
  - "  - robot1: 192.168.10.21"
  - lbot_driver, linkerta, teleop_bridge_node 启动成功

⚠️  等待所有节点启动完成（约5-10秒）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【步骤3】验证ROS2 Topics（可选）

在 终端3 执行:

# 查看所有topics
ros2 topic list

# 检查关键topics的频率
ros2 topic hz /right_arm_joint_control        # 应该 ~250Hz
ros2 topic hz /robot1/right_arm/joint_follow  # 应该 ~250Hz

# 如果启动了数据手套
ros2 topic hz /cb_left_hand_state             # 应该 ~40Hz

按 Ctrl+C 停止频率检查

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【步骤4】运行数据采集测试

在 终端3 执行:

cd ~/Dev/VIST

# 测试30秒（默认）
./scripts/test_exo_teleop_pipeline.sh

# 或自定义时长和任务名
./scripts/test_exo_teleop_pipeline.sh 60 "pick_test"

脚本会:
  1. 检查相机连接
  2. 检查机器人连接
  3. 创建数据目录
  4. 验证ROS2 topics
  5. 自动检测数据手套（如果有）
  6. 启动相机
  7. 录制数据
  8. 生成分析报告

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【步骤5】查看采集结果

数据保存在: data/collection/<task_name>_<timestamp>/

查看报告:
  cat data/collection/*/metadata.json
  cat data/collection/*/frequency_report.json
  cat data/collection/*/sync_report.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【注意事项】

⚠️  安全第一:
  - 确保机器人工作空间内无障碍物
  - 随时准备按下急停按钮
  - 首次测试使用小幅度动作

⚠️  如果遇到问题:
  - 检查所有设备是否上电
  - 检查网络连接 (ping 192.168.10.21)
  - 检查CAN总线 (ip link show can0)
  - 查看ROS2日志输出

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

准备好了吗？按照上述步骤开始测试！

EOF