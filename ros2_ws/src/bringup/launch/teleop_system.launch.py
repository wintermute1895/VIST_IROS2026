#!/usr/bin/env python3
"""
VIST Teleoperation System - Top Level Launch File
顶层启动文件，按顺序启动所有子系统

工作空间架构：
- 主工作空间 (ros2_ws): 包含上层应用节点（相机、灵巧手、机械臂驱动）
- 外部工作空间 (arm_teleop): 包含底层硬件驱动节点（外骨骼、VIST滤波器、遥操作桥接）

环境变量加载顺序（由 start_system.sh 完成）：
1. 系统 ROS2: /opt/ros/humble/setup.bash
2. 外部工作空间: ~/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop/install/setup.bash
3. 主工作空间: ~/Dev/VIST/ros2_ws/install/setup.bash

启动顺序：
1. [主工作空间] 相机（可选，T+0s）
2. [外部工作空间] 外骨骼（T+0s）
3. [外部工作空间] VIST滤波器（T+2s，等待外骨骼）
4. [主工作空间] 灵巧手（可选，T+1s）
5. [主工作空间] 机械臂驱动（T+4s，等待滤波器）
6. [外部工作空间] 遥操作桥接（T+7s，等待机械臂驱动）
"""

import os
import launch
import launch.conditions
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    LogInfo
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """生成完整系统启动描述"""

    # ========================================
    # 获取两个工作空间的包路径
    # ========================================

    # 主工作空间 (ros2_ws) - 上层应用节点
    bringup_dir = get_package_share_directory('bringup')
    main_launch_dir = os.path.join(bringup_dir, 'launch')

    # 外部工作空间 (arm_teleop) - 底层硬件驱动节点
    # 注意：这些包来自 external_sdk/arm_teleop，通过环境变量级联已经加载
    # 包括：lbot_driver, lbot_teleop, linkerta 等

    # ========================================
    # 启动参数声明
    # ========================================

    enable_camera_arg = DeclareLaunchArgument(
        'enable_camera',
        default_value='true',
        description='Enable camera for data collection'
    )

    enable_hand_arg = DeclareLaunchArgument(
        'enable_hand',
        default_value='true',
        description='Enable dexterous hand'
    )

    arm_side_arg = DeclareLaunchArgument(
        'arm_side',
        default_value='left',
        description='Arm side: left or right'
    )

    # ========================================
    # 子 Launch 文件路径
    # ========================================

    # Block 1: 主工作空间 (ros2_ws) 的 launch 文件
    camera_launch = os.path.join(main_launch_dir, 'camera.launch.py')
    dexterous_hand_launch = os.path.join(main_launch_dir, 'dexterous_hand.launch.py')
    robot_driver_launch = os.path.join(main_launch_dir, 'robot_driver.launch.py')

    # Block 2: 外部工作空间 (arm_teleop) 的 launch 文件
    # 这些 launch 文件位于主工作空间的 bringup 包中，但启动的是外部工作空间的节点
    exoskeleton_launch = os.path.join(main_launch_dir, 'exoskeleton.launch.py')
    vist_filter_launch = os.path.join(main_launch_dir, 'vist_filter.launch.py')
    teleop_bridge_launch = os.path.join(main_launch_dir, 'teleop_bridge.launch.py')

    # ========================================
    # 启动信息
    # ========================================

    system_start_info = LogInfo(
        msg='\n'
            '========================================\n'
            '  VIST Teleoperation System Starting\n'
            '  两工作空间架构 (Two-Workspace Architecture)\n'
            '========================================\n'
    )

    # ============================================================================
    # Block 1: 启动主工作空间 (ros2_ws) 的节点
    # ============================================================================
    # 主工作空间包含上层应用节点：
    # - camera: RealSense D435i 相机驱动
    # - dexterous_hand: Linker Hand L10 灵巧手控制
    # - robot_driver: 机械臂底层驱动
    # ============================================================================

    # ----------------------------------------
    # 1.1 相机节点（可选，T+0s 立即启动）
    # ----------------------------------------
    # 功能：采集 RGB-D 图像用于数据记录
    # 依赖：无
    # 包来源：主工作空间 (ros2_ws)

    camera_action = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(camera_launch),
        launch_arguments={
            'serial_number': '348122071157',
        }.items(),
        condition=launch.conditions.IfCondition(
            LaunchConfiguration('enable_camera')
        )
    )

    # ----------------------------------------
    # 1.2 灵巧手节点（可选，T+1s 延迟启动）
    # ----------------------------------------
    # 功能：控制 Linker Hand L10 灵巧手
    # 依赖：无（独立运行）
    # 包来源：主工作空间 (ros2_ws)

    dexterous_hand_action = TimerAction(
        period=1.0,
        actions=[
            LogInfo(msg='[Block 1] Starting Dexterous Hand (after 1s delay)...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(dexterous_hand_launch),
                launch_arguments={
                    'hand_type': LaunchConfiguration('arm_side'),
                }.items(),
                condition=launch.conditions.IfCondition(
                    LaunchConfiguration('enable_hand')
                )
            )
        ]
    )

    # ----------------------------------------
    # 1.3 机械臂驱动节点（T+4s 延迟启动）
    # ----------------------------------------
    # 功能：机械臂底层驱动，接收关节控制指令
    # 依赖：等待 VIST 滤波器启动（T+2s）后 2 秒
    # 包来源：主工作空间 (ros2_ws)

    robot_driver_action = TimerAction(
        period=4.0,
        actions=[
            LogInfo(msg='[Block 1] Starting Robot Driver (after 4s delay)...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(robot_driver_launch),
            )
        ]
    )

    # ============================================================================
    # Block 2: 启动外部工作空间 (arm_teleop) 的节点
    # ============================================================================
    # 外部工作空间包含底层硬件驱动节点：
    # - exoskeleton: Linkerta 外骨骼数据采集
    # - vist_filter: VIST 自适应卡尔曼滤波器
    # - teleop_bridge: 遥操作桥接（外骨骼 → 机械臂）
    # ============================================================================

    # ----------------------------------------
    # 2.1 外骨骼节点（T+0s 立即启动）
    # ----------------------------------------
    # 功能：采集 Linkerta 外骨骼关节角度数据
    # 依赖：无（最先启动）
    # 包来源：外部工作空间 (arm_teleop/linkerta)

    exoskeleton_action = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(exoskeleton_launch),
        launch_arguments={
            'arm_side': LaunchConfiguration('arm_side'),
        }.items()
    )

    # ----------------------------------------
    # 2.2 VIST 滤波器节点（T+2s 延迟启动）
    # ----------------------------------------
    # 功能：对外骨骼数据进行自适应卡尔曼滤波
    # 依赖：等待外骨骼节点启动（T+0s）后 2 秒
    # 包来源：外部工作空间 (arm_teleop/lbot_teleop)

    vist_filter_action = TimerAction(
        period=2.0,
        actions=[
            LogInfo(msg='[Block 2] Starting VIST Filter (after 2s delay)...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(vist_filter_launch),
            )
        ]
    )

    # ----------------------------------------
    # 2.3 遥操作桥接节点（T+7s 延迟启动）
    # ----------------------------------------
    # 功能：将滤波后的外骨骼数据转换为机械臂控制指令
    # 依赖：等待机械臂驱动启动（T+4s）后 3 秒
    # 包来源：外部工作空间 (arm_teleop/lbot_teleop)

    teleop_bridge_action = TimerAction(
        period=7.0,
        actions=[
            LogInfo(msg='[Block 2] Starting Teleop Bridge (after 7s delay)...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(teleop_bridge_launch),
                launch_arguments={
                    'arm_side': LaunchConfiguration('arm_side'),
                }.items()
            )
        ]
    )

    # ========================================
    # 系统完成信息
    # ========================================

    system_ready_info = TimerAction(
        period=10.0,
        actions=[
            LogInfo(
                msg='\n'
                    '========================================\n'
                    '  VIST Teleoperation System Ready!\n'
                    '  所有节点已启动完成\n'
                    '========================================\n'
            )
        ]
    )

    # ========================================
    # 返回 Launch 描述
    # ========================================

    return LaunchDescription([
        # ----------------------------------------
        # 参数声明
        # ----------------------------------------
        enable_camera_arg,
        enable_hand_arg,
        arm_side_arg,

        # ----------------------------------------
        # 启动信息
        # ----------------------------------------
        system_start_info,

        # ----------------------------------------
        # Block 1: 主工作空间 (ros2_ws) 节点
        # ----------------------------------------
        camera_action,           # T+0s (可选)
        dexterous_hand_action,   # T+1s (可选)
        robot_driver_action,     # T+4s

        # ----------------------------------------
        # Block 2: 外部工作空间 (arm_teleop) 节点
        # ----------------------------------------
        exoskeleton_action,      # T+0s
        vist_filter_action,      # T+2s
        teleop_bridge_action,    # T+7s

        # ----------------------------------------
        # 系统就绪信息
        # ----------------------------------------
        system_ready_info,       # T+10s
    ])