"""
LBot Teleoperation with High-Freq Resampler Launch File
集成高频重采样的遥操作启动文件

架构流程:
1. linkerta (外骨骼) → sensor_msgs/JointState (20-30Hz)
2. high_freq_resampler → lbot_arm_interfaces/FollowJoint (200Hz)
3. lbot_driver → 机器人硬件

注意: 此launch文件不启动teleop_bridge_node，因为high_freq_resampler已经处理了转换
"""

import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    linkerta_dir = get_package_share_directory('linkerta')
    lbot_teleop_dir = get_package_share_directory('lbot_teleop')

    # 配置文件路径
    teleop_config = os.path.join(lbot_teleop_dir, 'config', 'teleop_config.yaml')
    lbot_driver_config = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')
    resampler_config = os.path.join(lbot_teleop_dir, 'config', 'high_freq_resampler.yaml')

    # 读取配置文件获取从臂 IP 列表
    with open(teleop_config, 'r') as f:
        config = yaml.safe_load(f)

    slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])

    # 自动生成命名空间列表: robot1, robot2, robot3...
    slave_namespaces = [f"robot{i+1}" for i in range(len(slave_arm_ips))]

    # 打印配置信息
    print(f"[teleop_with_resampler.launch.py] 从臂配置:")
    for i, (ns, ip) in enumerate(zip(slave_namespaces, slave_arm_ips)):
        print(f"  - {ns}: {ip}")
    print(f"[teleop_with_resampler.launch.py] 启用高频重采样 (200Hz)")

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

    # 2. 启动 linkerta (主臂/外骨骼) - 延迟1秒
    linkerta_launch = TimerAction(
        period=1.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(linkerta_dir, 'launch', 'run.launch.py')
                )
            )
        ]
    )

    # 3. 启动 high_freq_resampler (高频重采样节点) - 延迟2秒
    # 注意: 不启动 teleop_bridge_node，因为 resampler 已经处理了转换
    resampler_node = Node(
        package='lbot_teleop',
        executable='high_freq_resampler_node',
        name='high_freq_resampler_node',
        output='screen',
        parameters=[resampler_config],
        emulate_tty=True,
    )

    resampler_launch = TimerAction(
        period=2.0,
        actions=[resampler_node]
    )

    return LaunchDescription([
        *driver_nodes,          # 所有从臂驱动节点
        linkerta_launch,        # 主臂/外骨骼节点
        resampler_launch,       # 高频重采样节点 (替代 teleop_bridge)
    ])
