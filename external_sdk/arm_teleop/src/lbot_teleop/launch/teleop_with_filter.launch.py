"""
外骨骼遥操作 + 滤波器集成 Launch文件
支持切换不同滤波器类型进行对比实验

架构流程:
linkerta → /exo_right_joint_control
              ↓
        VIST Filter Node (可切换滤波器类型)
              ↓
        /filtered_right_joint_control
              ↓
        teleop_bridge_node
              ↓
        /robot1/right_arm/joint_follow
              ↓
          lbot_driver

支持的滤波器类型:
- passthrough: 无滤波（Baseline对照组）
- one_euro: One-Euro滤波器
- ema: 指数移动平均滤波器
- vist_kalman: VIST卡尔曼滤波器（完整VIST算法）

使用示例:
  ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=passthrough
  ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=one_euro
  ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=ema
  ros2 launch lbot_teleop teleop_with_filter.launch.py filter_type:=vist_kalman
"""

import os
import sys
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import TimerAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # 声明launch参数
    filter_type_arg = DeclareLaunchArgument(
        'filter_type',
        default_value='passthrough',
        description='滤波器类型: passthrough, one_euro, ema, vist_kalman'
    )

    arm_side_arg = DeclareLaunchArgument(
        'arm_side',
        default_value='right',
        description='控制哪个臂: left, right'
    )

    output_freq_arg = DeclareLaunchArgument(
        'output_freq',
        default_value='100.0',
        description='滤波器输出频率 (Hz)'
    )

    # 获取launch参数
    filter_type = LaunchConfiguration('filter_type')
    arm_side = LaunchConfiguration('arm_side')
    output_freq = LaunchConfiguration('output_freq')

    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    lbot_teleop_dir = get_package_share_directory('lbot_teleop')

    # 配置文件路径
    teleop_config = os.path.join(lbot_teleop_dir, 'config', 'teleop_config.yaml')
    lbot_driver_config = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')

    # VIST项目路径（假设在上层目录）
    vist_project_root = os.path.abspath(os.path.join(lbot_teleop_dir, '../../../../..'))
    vist_config_path = os.path.join(vist_project_root, 'config', 'system_config.yaml')

    # 读取配置文件获取从臂 IP 列表
    with open(teleop_config, 'r') as f:
        config = yaml.safe_load(f)

    slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])
    teleop_bridge_params = config.get('teleop_bridge_node', {}).get('ros__parameters', {})

    # 自动生成命名空间列表: robot1, robot2, robot3...
    slave_namespaces = [f"robot{i+1}" for i in range(len(slave_arm_ips))]

    # 打印配置信息
    print("=" * 80)
    print("[teleop_with_filter.launch.py] 外骨骼遥操作 + 滤波器集成")
    print("=" * 80)
    print(f"从臂配置:")
    for i, (ns, ip) in enumerate(zip(slave_namespaces, slave_arm_ips)):
        print(f"  - {ns}: {ip}")
    print(f"\n滤波器配置:")
    print(f"  - 类型: {filter_type} (可选: passthrough, one_euro, ema, vist_kalman)")
    print(f"  - 臂侧: {arm_side}")
    print(f"  - 频率: {output_freq} Hz")
    print(f"\n话题流程:")
    print(f"  linkerta → /exo_{arm_side}_joint_control")
    print(f"           ↓")
    print(f"  VIST Filter Node ({filter_type})")
    print(f"           ↓")
    print(f"  /filtered_{arm_side}_joint_control")
    print(f"           ↓")
    print(f"  teleop_bridge → /robot1/{arm_side}_arm/joint_follow")
    print("=" * 80)

    # 1. 启动 lbot_driver (从臂) - 根据 IP 列表动态创建
    driver_nodes = []
    for namespace, arm_ip in zip(slave_namespaces, slave_arm_ips):
        driver_node = Node(
            package='lbot_driver',
            executable='lbot_driver',
            namespace=namespace,
            parameters=[
                lbot_driver_config,
                {"arm_ip": arm_ip}
            ],
            output='screen',
            emulate_tty=True,
        )
        driver_nodes.append(driver_node)

    # 2. 启动 linkerta (主臂/外骨骼) - 延迟1秒，使用话题重映射
    linkerta_node = Node(
        package='linkerta',
        executable='linkerta_node',
        name='linkerta_node',
        output='screen',
        emulate_tty=True,
        # 重映射话题：原始话题 → 外骨骼专用话题
        remappings=[
            ('/left_arm_joint_control', '/exo_left_joint_control'),
            ('/right_arm_joint_control', '/exo_right_joint_control'),
        ]
    )

    linkerta_launch = TimerAction(
        period=1.0,
        actions=[linkerta_node]
    )

    # 3. 启动 VIST Filter Node - 延迟2秒
    # 注意：需要确保VIST项目的Python路径已添加
    vist_filter_node = Node(
        package='vist_nodes',  # 假设VIST节点已安装为ROS2包
        executable='vist_filter_node',
        name='vist_filter_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            {
                # 话题配置
                'exo_left_topic': '/exo_left_joint_control',
                'exo_right_topic': '/exo_right_joint_control',
                'vision_left_topic': '/vision_left_joint_control',
                'vision_right_topic': '/vision_right_joint_control',
                'filtered_left_topic': '/filtered_left_joint_control',
                'filtered_right_topic': '/filtered_right_joint_control',

                # 控制参数
                'output_freq_hz': output_freq,
                'arm_side': arm_side,

                # 滤波器类型
                'filter_type': filter_type,

                # 意图因子配置（仅VIST使用）
                'enable_distance_factor': True,
                'enable_velocity_factor': True,
                'enable_alignment_factor': True,
                'enable_conflict_detection': True,

                # EMA参数
                'ema_alpha': 0.3,

                # One Euro参数
                'one_euro_min_cutoff': 1.0,
                'one_euro_beta': 0.007,

                # VIST配置文件路径
                'vist_config_path': vist_config_path,

                # 性能监控
                'enable_performance_monitoring': True,
                'performance_topic': '/vist_performance',
            }
        ],
        # 添加VIST项目路径到PYTHONPATH
        additional_env={'PYTHONPATH': f"{vist_project_root}:{os.environ.get('PYTHONPATH', '')}"}
    )

    vist_filter_launch = TimerAction(
        period=2.0,
        actions=[vist_filter_node]
    )

    # 4. 启动 teleop_bridge (桥接节点) - 延迟3秒
    # 订阅滤波后的话题
    teleop_bridge_node = Node(
        package='lbot_teleop',
        executable='teleop_bridge_node',
        name='teleop_bridge_node',
        output='screen',
        parameters=[
            teleop_bridge_params,
            {
                "slave_namespaces": slave_namespaces,
                # 订阅滤波后的话题
                "master_left_topic": "/filtered_left_joint_control",
                "master_right_topic": "/filtered_right_joint_control",
            }
        ]
    )

    teleop_bridge_launch = TimerAction(
        period=3.0,
        actions=[teleop_bridge_node]
    )

    return LaunchDescription([
        # Launch参数
        filter_type_arg,
        arm_side_arg,
        output_freq_arg,

        # 节点
        *driver_nodes,          # 所有从臂驱动节点
        linkerta_launch,        # 主臂节点（重映射话题）
        vist_filter_launch,     # VIST滤波节点
        teleop_bridge_launch,   # 桥接节点（订阅滤波后话题）
    ])
