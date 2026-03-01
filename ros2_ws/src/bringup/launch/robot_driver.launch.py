#!/usr/bin/env python3
"""
Robot Driver Launch File
启动机械臂驱动节点
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    """生成机械臂驱动启动描述"""

    # ROS2 工作空间路径
    ros2_ws = '/home/ilex/Dev/VIST/ros2_ws'

    # lbot_driver的launch文件路径（使用ROS2标准安装路径）
    lbot_driver_launch = os.path.join(
        ros2_ws,
        'install/lbot_driver/share/lbot_driver/launch/lbot_start_driver.launch.py'
    )

    # 包含lbot_driver的launch文件
    include_lbot_driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(lbot_driver_launch),
        launch_arguments={
            # 如果需要传递参数，在这里添加
        }.items()
    )

    # 启动信息
    log_info = LogInfo(msg='[Bringup] Starting Robot Driver (lbot_driver)...')

    return LaunchDescription([
        log_info,
        include_lbot_driver,
    ])