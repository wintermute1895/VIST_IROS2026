#!/usr/bin/env python3
"""
Teleoperation Bridge Launch File
启动遥操作桥接节点
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """生成遥操作桥接启动描述"""

    # 外骨骼工作空间路径
    exo_ws = '/home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop'
    config_file = os.path.join(
        exo_ws,
        'src/lbot_teleop/config/teleop_bridge_params.yaml'
    )

    # 声明启动参数
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to teleop bridge configuration file'
    )

    arm_side_arg = DeclareLaunchArgument(
        'arm_side',
        default_value='left',
        description='Arm side: left or right'
    )

    # 遥操作桥接节点
    teleop_bridge_node = Node(
        package='lbot_teleop',
        executable='teleop_bridge_node',
        name='teleop_bridge_node',
        output='screen',
        parameters=[LaunchConfiguration('config_file')],
        remappings=[
            # 输入：滤波后的控制指令
            ('/filtered_left_joint_control', '/filtered_left_joint_control'),
            # 输出：机械臂控制指令
            ('/robot1/left_arm/joint_follow', '/robot1/left_arm/joint_follow'),
        ]
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Teleoperation Bridge...')

    return LaunchDescription([
        log_info,
        config_file_arg,
        arm_side_arg,
        teleop_bridge_node,
    ])