#!/usr/bin/env python3
"""
RealSense 双 D435i 相机独立运行启动文件
配置全局时间戳映射，利用系统 NTP 时钟消除 USB 传输延迟

【核心配置说明】
1. global_time_enabled: true  - 使用系统时钟修正硬件时间戳，消除 USB 延迟
2. enable_sync: true           - 彩色流和深度流内部对齐
3. inter_cam_sync_mode: 0     - Default 独立模式（无硬件同步线时必须设为 0，否则严重掉帧）
4. 分辨率: 640x480 @ 30fps    - 节省带宽，适合双臂机器人实时采集

【命名空间】
- camera_global: 全局视角 D435i
- camera_wrist:  腕部视角 D435i

作者: VIST Team
日期: 2026-03-05
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """生成双 D435i 相机独立运行启动描述"""

    # ========================================
    # Launch 参数声明
    # ========================================

    # 全局相机序列号（请填入你的第一台 D435i 序列号）
    global_serial_arg = DeclareLaunchArgument(
        'global_serial',
        default_value='348122071157',  # 留空则自动检测第一台相机
        description='Global camera D435i serial number (empty for auto-detect)'
    )

    # 腕部相机序列号（请填入你的第二台 D435i 序列号）
    wrist_serial_arg = DeclareLaunchArgument(
        'wrist_serial',
        default_value='327122074150',  # 留空则自动检测第二台相机
        description='Wrist camera D435i serial number (empty for auto-detect)'
    )

    # 彩色图像分辨率
    color_width_arg = DeclareLaunchArgument(
        'color_width',
        default_value='640',
        description='Color image width'
    )

    color_height_arg = DeclareLaunchArgument(
        'color_height',
        default_value='480',
        description='Color image height'
    )

    # 帧率
    fps_arg = DeclareLaunchArgument(
        'fps',
        default_value='30',
        description='Camera frame rate'
    )

    # 深度图像分辨率
    depth_width_arg = DeclareLaunchArgument(
        'depth_width',
        default_value='640',
        description='Depth image width'
    )

    depth_height_arg = DeclareLaunchArgument(
        'depth_height',
        default_value='480',
        description='Depth image height'
    )

    # 是否启用深度流
    enable_depth_arg = DeclareLaunchArgument(
        'enable_depth',
        default_value='true',
        description='Enable depth stream'
    )

    # ========================================
    # 相机节点配置
    # ========================================

    # 全局相机节点（D435i #1 - 独立模式）
    camera_global_node = Node(
        package='realsense2_camera',
        executable='realsense2_camera_node',
        name='camera_global',
        namespace='camera_global',
        output='screen',
        parameters=[{
            # ===== 相机识别 =====
            'serial_no': '348122071157',  # D435i 全局相机序列号（直接字符串避免类型问题）
            'camera_name': 'camera_global',

            # ===== 全局时间戳配置（核心） =====
            'global_time_enabled': True,  # 启用系统时钟修正，消除 USB 延迟
            'enable_sync': True,          # 彩色流和深度流内部对齐
            'inter_cam_sync_mode': 0,     # 0 = Default 独立模式（无硬件线必须设为 0）

            # ===== 彩色流配置 =====
            'enable_color': True,
            'rgb_camera.color_profile': '640x480x30',  # 明确指定配置文件
            'rgb_camera.enable_auto_exposure': True,

            # ===== 深度流配置 =====
            'enable_depth': LaunchConfiguration('enable_depth'),
            'depth_module.depth_profile': '640x480x30',  # 明确指定配置文件
            'depth_module.enable_auto_exposure': True,

            # ===== 其他传感器（全部关闭以节省带宽） =====
            'enable_infra1': False,
            'enable_infra2': False,
            'enable_gyro': False,
            'enable_accel': False,

            # ===== 对齐配置 =====
            'align_depth.enable': True,   # 深度对齐到彩色
            'pointcloud.enable': False,   # 关闭点云（节省带宽）

            # ===== TF 配置 =====
            'publish_tf': False,          # 不发布 TF（避免命名空间冲突）
            'tf_publish_rate': 0.0,

            # ===== 后处理滤波器（全部关闭以降低延迟） =====
            'decimation_filter.enable': False,
            'spatial_filter.enable': False,
            'temporal_filter.enable': False,
            'hole_filling_filter.enable': False,
        }],
        emulate_tty=True
    )

    # 腕部相机节点（D435i #2 - 独立模式）
    camera_wrist_node = Node(
        package='realsense2_camera',
        executable='realsense2_camera_node',
        name='camera_wrist',
        namespace='camera_wrist',
        output='screen',
        parameters=[{
            # ===== 相机识别 =====
            'serial_no': '327122074150',  # D435i 腕部相机序列号（直接字符串避免类型问题）
            'camera_name': 'camera_wrist',

            # ===== 全局时间戳配置（核心） =====
            'global_time_enabled': True,  # 启用系统时钟修正，消除 USB 延迟
            'enable_sync': True,          # 彩色流和深度流内部对齐
            'inter_cam_sync_mode': 0,     # 0 = Default 独立模式（无硬件线必须设为 0）

            # ===== 彩色流配置 =====
            'enable_color': True,
            'rgb_camera.color_profile': '640x480x30',
            'rgb_camera.enable_auto_exposure': True,

            # ===== 深度流配置 =====
            'enable_depth': LaunchConfiguration('enable_depth'),
            'depth_module.depth_profile': '640x480x30',
            'depth_module.enable_auto_exposure': True,

            # ===== 其他传感器（全部关闭以节省带宽） =====
            'enable_infra1': False,
            'enable_infra2': False,
            'enable_gyro': False,
            'enable_accel': False,

            # ===== 对齐配置 =====
            'align_depth.enable': True,
            'pointcloud.enable': False,

            # ===== TF 配置 =====
            'publish_tf': False,
            'tf_publish_rate': 0.0,

            # ===== 后处理滤波器（全部关闭以降低延迟） =====
            'decimation_filter.enable': False,
            'spatial_filter.enable': False,
            'temporal_filter.enable': False,
            'hole_filling_filter.enable': False,
        }],
        emulate_tty=True
    )

    # 启动信息
    log_info = LogInfo(
        msg='[Camera Sync] 启动双 D435i 相机（独立模式 + 全局时间戳）...'
    )

    # ========================================
    # Launch Description
    # ========================================
    return LaunchDescription([
        log_info,

        # Launch 参数
        global_serial_arg,
        wrist_serial_arg,
        color_width_arg,
        color_height_arg,
        fps_arg,
        depth_width_arg,
        depth_height_arg,
        enable_depth_arg,

        # 相机节点
        camera_global_node,
        camera_wrist_node,
    ])
