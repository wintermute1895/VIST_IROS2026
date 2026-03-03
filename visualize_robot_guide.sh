#!/bin/bash
# 机械臂Meshcat可视化使用指南

echo "=========================================="
echo "机械臂Meshcat可视化"
echo "=========================================="
echo ""
echo "脚本: visualize_robot_meshcat.py"
echo "URDF: /home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description_fsm.urdf"
echo ""

echo "功能:"
echo "  ✓ 加载完整的机械臂3D模型"
echo "  ✓ 在Meshcat中显示双臂机器人"
echo "  ✓ 播放左臂关节运动动画"
echo "  ✓ 自动打开浏览器查看"
echo ""

echo "使用方法:"
echo "  python3 visualize_robot_meshcat.py"
echo ""

echo "操作提示:"
echo "  - 脚本启动后会自动打开浏览器"
echo "  - 在浏览器中可以看到完整的3D机械臂模型"
echo "  - 鼠标左键: 旋转视图"
echo "  - 鼠标右键: 平移视图"
echo "  - 滚轮: 缩放视图"
echo "  - 按 Ctrl+C 停止动画"
echo "  - 按 Enter 退出程序"
echo ""

echo "机器人信息:"
echo "  - 关节总数: 14 (双臂各7个)"
echo "  - 左臂关节:"
echo "    1. Left_Shoulder_Pitch_Joint"
echo "    2. Left_Shoulder_Roll_Joint"
echo "    3. Left_Shoulder_Yaw_Joint"
echo "    4. Left_Elbow_Pitch_Joint"
echo "    5. Left_Wrist_Yaw_Joint"
echo "    6. Left_Wrist_Pitch_Joint"
echo "    7. Left_Wrist_Roll_Joint"
echo ""

echo "依赖:"
echo "  pip install pinocchio meshcat"
echo ""

echo "=========================================="
