#!/usr/bin/env python3
"""
Dexterous Hand Launch File
启动灵巧手驱动节点
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """生成灵巧手启动描述"""

    # 声明启动参数
    hand_type_arg = DeclareLaunchArgument(
        'hand_type',
        default_value='left',
        description='Hand type: left or right'
    )

    can_port_arg = DeclareLaunchArgument(
        'can_port',
        default_value='can0',
        description='CAN port name'
    )

    enable_touch_arg = DeclareLaunchArgument(
        'enable_touch',
        default_value='false',
        description='Enable touch sensor'
    )

    # CAN端口初始化（如果需要）
    # 注意：这需要sudo权限，可能需要预先配置或使用udev规则
    can_setup = ExecuteProcess(
        cmd=[
            'bash', '-c',
            'if ! ip link show can0 | grep -q "state UP"; then '
            'sudo ip link set can0 up type can bitrate 1000000; fi'
        ],
        output='screen',
        shell=False
    )

    # 灵巧手节点 - 使用ExecuteProcess避免ROS2自动添加参数
    dexterous_hand_node = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'linker_hand_ros2_sdk', 'linker_hand_advanced_l10',
            '--hand_type', LaunchConfiguration('hand_type'),
            '--can', LaunchConfiguration('can_port'),
            '--is_touch', LaunchConfiguration('enable_touch'),
        ],
        output='screen',
        shell=False
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Dexterous Hand...')

    return LaunchDescription([
        log_info,
        hand_type_arg,
        can_port_arg,
        enable_touch_arg,
        can_setup,
        dexterous_hand_node,
    ])