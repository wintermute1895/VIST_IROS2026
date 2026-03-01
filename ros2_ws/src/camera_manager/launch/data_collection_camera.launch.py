#!/usr/bin/env python3
"""
启动数据采集相机（序列号: 348122071157）
用于模仿学习数据收集
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    启动数据采集相机节点

    相机配置:
    - 序列号: 348122071157 (Intel RealSense D435I)
    - 用途: 模仿学习数据采集
    - 分辨率: 848x480 @ 30fps
    - 功能: RGB + Depth + 对齐
    """

    data_collection_camera = Node(
        package='camera_manager',
        executable='realsense_camera_node',
        name='data_collection_camera',
        namespace='data_collection',
        output='screen',
        parameters=[{
            # 相机标识
            'serial_number': '348122071157',
            'camera_name': 'data_camera',
            'camera_id': 1,

            # 彩色流配置
            'color_width': 848,
            'color_height': 480,
            'color_fps': 30,

            # 深度流配置
            'depth_width': 848,
            'depth_height': 480,
            'depth_fps': 30,

            # 功能开关
            'enable_color': True,
            'enable_depth': True,
            'enable_pointcloud': False,  # 数据采集不需要点云
            'enable_imu': False,
            'align_depth_to_color': True,  # 对齐深度到彩色
        }],
        emulate_tty=True
    )

    return LaunchDescription([
        data_collection_camera
    ])
