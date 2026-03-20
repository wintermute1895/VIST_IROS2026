#!/bin/bash
# rqt使用指南

cat << 'EOF'
========================================
RQT 使用指南
========================================

【问题】为什么rqt_topic命令不存在？
----------------------------------------
rqt_topic不是独立命令，而是rqt的插件。

正确使用方法:
  1. 启动 rqt
  2. 在菜单中加载插件


【启动rqt】
----------------------------------------
命令:
  rqt


【加载常用插件】
----------------------------------------

1. 话题监控器 (Topic Monitor)
   路径: Plugins → Topics → Topic Monitor
   功能: 查看所有话题、频率、带宽

2. 节点图 (Node Graph)
   路径: Plugins → Introspection → Node Graph
   功能: 查看节点和话题的连接关系

3. 绘图 (Plot)
   路径: Plugins → Visualization → Plot
   功能: 实时绘制数据曲线

4. 日志查看器 (Console)
   路径: Plugins → Logging → Console
   功能: 查看节点日志

5. TF树 (TF Tree)
   路径: Plugins → Visualization → TF Tree
   功能: 查看坐标系变换关系


【使用Plot绘制曲线】
----------------------------------------
1. 加载Plot插件
2. 在顶部输入框输入话题路径:
   /left_arm_joint_control/position[0]
3. 点击 "+" 添加
4. 移动遥操臂观察曲线


【推荐的布局】
----------------------------------------
┌─────────────────┬─────────────────┐
│ Node Graph      │ Topic Monitor   │
│ (节点关系图)    │ (话题列表)      │
├─────────────────┴─────────────────┤
│ Plot                              │
│ (数据曲线)                        │
└───────────────────────────────────┘


【保存和加载布局】
----------------------------------------
保存:
  Perspectives → Create Perspective
  输入名称 → 保存

加载:
  Perspectives → 选择已保存的布局


【命令行替代方案】
----------------------------------------
如果你更喜欢命令行:

查看话题列表:
  ros2 topic list

查看话题频率:
  ros2 topic hz /left_arm_joint_control

查看话题内容:
  ros2 topic echo /left_arm_joint_control

查看话题信息:
  ros2 topic info /left_arm_joint_control


【快速诊断命令】
----------------------------------------
# 查看所有话题
ros2 topic list

# 查看左臂原始数据频率
ros2 topic hz /left_arm_joint_control

# 查看左臂滤波后数据频率
ros2 topic hz /filtered_left_joint_control

# 查看右臂原始数据频率
ros2 topic hz /right_arm_joint_control

# 查看右臂滤波后数据频率
ros2 topic hz /filtered_right_joint_control

# 查看桥接节点输出
ros2 topic hz /robot1/left_arm/joint_follow


【验证方向修正】
----------------------------------------
# 同时查看原始和滤波后的数据
终端1: ros2 topic echo /left_arm_joint_control
终端2: ros2 topic echo /filtered_left_joint_control

移动遥操臂第3个关节(Shoulder_Yaw)
对比 position[2] 的值，应该是相反的


【常见问题】
----------------------------------------
Q: 为什么看不到话题列表？
A: 确保节点正在运行，使用 ros2 node list 检查

Q: 为什么频率显示为0？
A: 话题没有数据发布，检查节点是否正常运行

Q: 如何对比两个话题的数据？
A: 在Plot中添加两条曲线，或用两个终端echo


========================================
现在开始使用
========================================

1. 启动rqt:
   rqt

2. 加载插件:
   Plugins → Topics → Topic Monitor
   Plugins → Visualization → Plot

3. 开始分析数据流！

EOF
