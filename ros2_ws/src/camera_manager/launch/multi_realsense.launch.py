#!/usr/bin/env python3
"""
Launch file for multi-camera RealSense system.
启动多个RealSense相机的launch文件
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('camera_manager')
    config_file = os.path.join(pkg_dir, 'config', 'camera_config.yaml')

    # Declare launch arguments
    config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to camera configuration file'
    )

    # Multi-camera manager node
    multi_camera_node = Node(
        package='camera_manager',
        executable='multi_camera_manager',
        name='multi_camera_manager',
        output='screen',
        parameters=[LaunchConfiguration('config_file')],
        emulate_tty=True
    )

    return LaunchDescription([
        config_arg,
        multi_camera_node
    ])
