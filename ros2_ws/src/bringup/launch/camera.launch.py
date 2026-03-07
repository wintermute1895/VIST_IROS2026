#!/usr/bin/env python3
"""
Camera Launch File
启动两个RealSense相机节点（D435i和D405）
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """生成相机启动描述"""

    # D435i 相机参数（主相机）
    d435i_serial_arg = DeclareLaunchArgument(
        'd435i_serial',
        default_value='348122071157',
        description='D435i camera serial number'
    )

    # D405 相机参数（辅助相机）
    d405_serial_arg = DeclareLaunchArgument(
        'd405_serial',
        default_value='409122273357',  # 需要填入实际的D405序列号
        description='D405 camera serial number'
    )

    # 通用参数
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

    # D435i 相机节点（主相机，命名为camera_d435i）
    camera_d435i_node = ExecuteProcess(
        cmd=[
            'python3', '-m', 'camera_manager.realsense_camera_node',
            '--ros-args',
            '-p', ['serial_number:=', LaunchConfiguration('d435i_serial')],
            '-p', 'camera_name:=camera_d435i',
            '-p', ['width:=', LaunchConfiguration('width')],
            '-p', ['height:=', LaunchConfiguration('height')],
            '-p', ['fps:=', LaunchConfiguration('fps')],
        ],
        output='screen',
        shell=False
    )

    # D405 相机节点（辅助相机，命名为camera_d405）
    camera_d405_node = ExecuteProcess(
        cmd=[
            'python3', '-m', 'camera_manager.realsense_camera_node',
            '--ros-args',
            '-p', ['serial_number:=', LaunchConfiguration('d405_serial')],
            '-p', 'camera_name:=camera_d405',
            '-p', ['width:=', LaunchConfiguration('width')],
            '-p', ['height:=', LaunchConfiguration('height')],
            '-p', ['fps:=', LaunchConfiguration('fps')],
        ],
        output='screen',
        shell=False
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Two RealSense Cameras (D435i + D405)...')

    return LaunchDescription([
        log_info,
        d435i_serial_arg,
        d405_serial_arg,
        width_arg,
        height_arg,
        fps_arg,
        camera_d435i_node,
        camera_d405_node,
    ])