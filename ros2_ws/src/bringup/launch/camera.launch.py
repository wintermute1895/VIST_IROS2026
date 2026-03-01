#!/usr/bin/env python3
"""
Camera Launch File
启动RealSense相机节点（可选组件）
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """生成相机启动描述"""

    # 声明启动参数
    serial_number_arg = DeclareLaunchArgument(
        'serial_number',
        default_value='348122071157',
        description='RealSense camera serial number'
    )

    width_arg = DeclareLaunchArgument(
        'width',
        default_value='848',
        description='Camera image width'
    )

    height_arg = DeclareLaunchArgument(
        'height',
        default_value='480',
        description='Camera image height'
    )

    fps_arg = DeclareLaunchArgument(
        'fps',
        default_value='30',
        description='Camera frame rate'
    )

    # 相机节点 - 使用ExecuteProcess直接运行Python模块
    camera_node = ExecuteProcess(
        cmd=[
            'python3', '-m', 'camera_manager.realsense_camera_node',
            '--ros-args',
            '-p', ['serial_number:=', LaunchConfiguration('serial_number')],
            '-p', ['width:=', LaunchConfiguration('width')],
            '-p', ['height:=', LaunchConfiguration('height')],
            '-p', ['fps:=', LaunchConfiguration('fps')],
        ],
        output='screen',
        shell=False
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting RealSense Camera...')

    return LaunchDescription([
        log_info,
        serial_number_arg,
        width_arg,
        height_arg,
        fps_arg,
        camera_node,
    ])