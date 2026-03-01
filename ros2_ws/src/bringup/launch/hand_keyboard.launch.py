#!/usr/bin/env python3
"""
Hand Keyboard Control Launch File
启动灵巧手键盘控制节点（在新终端窗口中）
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
import os


def launch_keyboard_control(context):
    """启动键盘控制的函数"""
    hand_type = LaunchConfiguration('hand_type').perform(context)
    preset = LaunchConfiguration('preset').perform(context)

    # 构建命令
    cmd = [
        'gnome-terminal', '--',
        'bash', '-c',
        f'source /opt/ros/humble/setup.bash && '
        f'source /home/ilex/Dev/VIST/ros2_ws/install/setup.bash && '
        f'python3 /home/ilex/Dev/VIST/scripts/hand_control.py '
        f'--hand_type {hand_type} --preset {preset}; '
        f'exec bash'
    ]

    return [ExecuteProcess(
        cmd=cmd,
        output='screen',
        shell=False
    )]


def generate_launch_description():
    """生成灵巧手键盘控制启动描述"""

    # 声明启动参数
    hand_type_arg = DeclareLaunchArgument(
        'hand_type',
        default_value='left',
        description='Hand type: left or right'
    )

    preset_arg = DeclareLaunchArgument(
        'preset',
        default_value='medium',
        description='Grasp preset: small, medium, or large'
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Hand Keyboard Control in new terminal...')

    # 使用 OpaqueFunction 来延迟执行，以便能够获取 LaunchConfiguration 的值
    keyboard_control = OpaqueFunction(function=launch_keyboard_control)

    return LaunchDescription([
        log_info,
        hand_type_arg,
        preset_arg,
        keyboard_control,
    ])