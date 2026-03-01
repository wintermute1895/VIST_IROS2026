#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # 声明参数
    declare_input_topic = DeclareLaunchArgument(
        'input_topic',
        default_value='/cb_left_hand_control_cmd',
        description='要监控的输入话题'
    )

    declare_output_topic = DeclareLaunchArgument(
        'output_topic',
        default_value='',
        description='要监控的输出话题（可选）'
    )

    declare_output_file = DeclareLaunchArgument(
        'output_file',
        default_value='performance_log.csv',
        description='性能数据输出文件'
    )

    declare_window_size = DeclareLaunchArgument(
        'window_size',
        default_value='100',
        description='统计窗口大小'
    )

    declare_print_interval = DeclareLaunchArgument(
        'print_interval',
        default_value='5.0',
        description='打印统计信息的间隔（秒）'
    )

    # 创建性能监控节点
    performance_monitor_node = Node(
        package='performance_monitor',
        executable='performance_monitor',
        name='performance_monitor',
        output='screen',
        parameters=[{
            'input_topic': LaunchConfiguration('input_topic'),
            'output_topic': LaunchConfiguration('output_topic'),
            'output_file': LaunchConfiguration('output_file'),
            'window_size': LaunchConfiguration('window_size'),
            'print_interval': LaunchConfiguration('print_interval'),
        }],
    )

    return LaunchDescription([
        declare_input_topic,
        declare_output_topic,
        declare_output_file,
        declare_window_size,
        declare_print_interval,
        performance_monitor_node,
    ])
