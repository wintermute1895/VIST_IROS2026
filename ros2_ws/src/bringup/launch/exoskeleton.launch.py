#!/usr/bin/env python3
"""
Exoskeleton Launch File
启动外骨骼遥操节点
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """生成外骨骼启动描述"""

    # 外骨骼工作空间路径
    exo_ws = '/home/ilex/Dev/VIST/ros2_ws/src/external_sdk/arm_teleop'
    config_file = os.path.join(exo_ws, 'src/linkerta/config/lta.yaml')

    # 声明启动参数
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to linkerta configuration file'
    )

    arm_side_arg = DeclareLaunchArgument(
        'arm_side',
        default_value='left',
        description='Arm side: left or right'
    )

    # 外骨骼节点
    exoskeleton_node = Node(
        package='linkerta',
        executable='linkerta_node',
        name='linkerta_node',
        output='screen',
        parameters=[LaunchConfiguration('config_file')],
        remappings=[
            # 根据arm_side动态重映射话题
            # 默认发布到 /left_arm_joint_control 或 /right_arm_joint_control
        ]
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Exoskeleton (Linkerta)...')

    return LaunchDescription([
        log_info,
        config_file_arg,
        arm_side_arg,
        exoskeleton_node,
    ])
