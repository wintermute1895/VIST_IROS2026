#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # 获取配置文件路径
    config_file = PathJoinSubstitution([
        FindPackageShare('performance_monitor'),
        'config',
        'advanced.yaml'
    ])

    # 声明参数
    declare_config_file = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='配置文件路径'
    )

    declare_input_topic = DeclareLaunchArgument(
        'input_topic',
        default_value='/cb_left_hand_control_cmd',
        description='要监控的输入话题'
    )

    declare_feedback_topic = DeclareLaunchArgument(
        'feedback_topic',
        default_value='',
        description='反馈话题（用于跟踪误差计算）'
    )

    declare_output_file = DeclareLaunchArgument(
        'output_file',
        default_value='performance_log_advanced.csv',
        description='性能数据输出文件'
    )

    # 创建性能监控节点（扩展版）
    performance_monitor_node = Node(
        package='performance_monitor',
        executable='performance_monitor_advanced',
        name='performance_monitor_advanced',
        output='screen',
        parameters=[
            LaunchConfiguration('config_file'),
            {
                'input_topic': LaunchConfiguration('input_topic'),
                'feedback_topic': LaunchConfiguration('feedback_topic'),
                'output_file': LaunchConfiguration('output_file'),
            }
        ],
    )

    return LaunchDescription([
        declare_config_file,
        declare_input_topic,
        declare_feedback_topic,
        declare_output_file,
        performance_monitor_node,
    ])
