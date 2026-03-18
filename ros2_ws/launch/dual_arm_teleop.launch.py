#!/usr/bin/env python3
"""
双臂遥操作启动文件
启动两个独立的VIST滤波节点，分别处理左臂和右臂

使用方法:
    ros2 launch dual_arm_teleop.launch.py

作者: VIST Team
日期: 2026-03-17
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os
from pathlib import Path


def generate_launch_description():
    # 获取项目根目录
    # launch文件在 /home/ilex/Dev/VIST/ros2_ws/launch/
    # 项目根目录在 /home/ilex/Dev/VIST/
    launch_file_dir = Path(__file__).parent
    ros2_ws_root = launch_file_dir.parent
    project_root = ros2_ws_root.parent

    # 配置文件路径
    config_file = str(project_root / 'config' / 'baseline_filters_config.yaml')

    # 声明启动参数
    filter_type_arg = DeclareLaunchArgument(
        'filter_type',
        default_value='oneeuro',
        description='滤波器类型: gello, oneeuro, vist, fsm, apf'
    )

    output_freq_arg = DeclareLaunchArgument(
        'output_freq_hz',
        default_value='80.0',
        description='输出频率 (Hz)'
    )

    # 左臂滤波节点
    left_arm_node = Node(
        package='vist_teleop',  # 替换为你的包名
        executable='vist_filter_node.py',
        name='vist_filter_left',
        namespace='',
        parameters=[
            config_file,
            {
                'arm_side': 'left',
                'filter_type': LaunchConfiguration('filter_type'),
                'output_freq_hz': LaunchConfiguration('output_freq_hz')
            }
        ],
        output='screen',
        emulate_tty=True,
        prefix='xterm -e'  # 在独立终端中运行（可选）
    )

    # 右臂滤波节点
    right_arm_node = Node(
        package='vist_teleop',  # 替换为你的包名
        executable='vist_filter_node.py',
        name='vist_filter_right',
        namespace='',
        parameters=[
            config_file,
            {
                'arm_side': 'right',
                'filter_type': LaunchConfiguration('filter_type'),
                'output_freq_hz': LaunchConfiguration('output_freq_hz')
            }
        ],
        output='screen',
        emulate_tty=True,
        prefix='xterm -e'  # 在独立终端中运行（可选）
    )

    return LaunchDescription([
        filter_type_arg,
        output_freq_arg,
        left_arm_node,
        right_arm_node
    ])