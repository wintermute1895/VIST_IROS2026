#!/usr/bin/env python3
"""
VIST Filter Launch File
启动 VIST 滤波器节点（支持 5 种 Baseline 算法切换）

支持的滤波器类型：
- gello: 直通模式（无滤波）
- oneeuro: 1-Euro 自适应滤波
- vist: VIST 卡尔曼滤波
- fsm: 有限状态机
- apf: 人工势场

使用方法：
    # 使用默认配置（从 baseline_filters_config.yaml）
    ros2 launch bringup vist_filter.launch.py

    # 指定滤波器类型
    ros2 launch bringup vist_filter.launch.py filter_type:=oneeuro

    # 使用自定义配置文件
    ros2 launch bringup vist_filter.launch.py config_file:=/path/to/config.yaml
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch.actions import ExecuteProcess


def launch_setup(context, *_args, **_kwargs):
    """根据参数动态生成节点配置"""

    # VIST 项目根目录
    vist_root = '/home/ilex/Dev/VIST'

    # 获取参数值
    config_file = LaunchConfiguration('config_file').perform(context)
    filter_type = LaunchConfiguration('filter_type').perform(context)

    # 构建命令
    cmd = [
        'python3',
        os.path.join(vist_root, 'ros2_ws/src/nodes/vist_filter_node.py'),
        '--ros-args',
        '--params-file', config_file,
    ]

    # 只有当 filter_type 不为空时才添加参数覆盖
    if filter_type:
        cmd.extend(['-p', f'filter_type:={filter_type}'])

    # 创建进程
    vist_filter_node = ExecuteProcess(
        cmd=cmd,
        output='screen',
        shell=False
    )

    return [vist_filter_node]


def generate_launch_description():
    """生成 VIST 滤波器启动描述"""

    # VIST 项目根目录
    vist_root = '/home/ilex/Dev/VIST'

    # 默认使用新的 baseline 配置文件
    default_config_file = os.path.join(vist_root, 'config/baseline_filters_config.yaml')

    # 声明启动参数
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config_file,
        description='Path to filter configuration file (baseline_filters_config.yaml)'
    )

    filter_type_arg = DeclareLaunchArgument(
        'filter_type',
        default_value='',  # 空字符串表示使用配置文件中的值
        description='Filter type: gello, oneeuro, vist, fsm, apf (overrides config file)'
    )

    # 启动信息
    log_info = LogInfo(msg=[
        '[Bringup] Starting VIST Filter Node...\n',
        '  Config: ', LaunchConfiguration('config_file'), '\n',
        '  Filter: ', LaunchConfiguration('filter_type'), ' (empty = use config file)'
    ])

    return LaunchDescription([
        config_file_arg,
        filter_type_arg,
        log_info,
        OpaqueFunction(function=launch_setup)
    ])
