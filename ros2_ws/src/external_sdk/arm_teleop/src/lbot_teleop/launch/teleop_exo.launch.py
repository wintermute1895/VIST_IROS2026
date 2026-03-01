"""
外骨骼遥操作Launch文件（使用话题重映射）
不修改SDK源码，通过ROS2 remapping功能防止话题冲突

架构:
linkerta → /exo_left_joint_control (remapped)
              ↓
        teleop_bridge_node
              ↓
        /robot1/left_arm/joint_follow
              ↓
          lbot_driver
"""

import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import TimerAction
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    lbot_teleop_dir = get_package_share_directory('lbot_teleop')

    # 配置文件路径
    teleop_config = os.path.join(lbot_teleop_dir, 'config', 'teleop_config.yaml')
    lbot_driver_config = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')

    # 读取配置文件获取从臂 IP 列表
    with open(teleop_config, 'r') as f:
        config = yaml.safe_load(f)

    slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])
    teleop_bridge_params = config.get('teleop_bridge_node', {}).get('ros__parameters', {})

    # 自动生成命名空间列表: robot1, robot2, robot3...
    slave_namespaces = [f"robot{i+1}" for i in range(len(slave_arm_ips))]

    # 打印配置信息
    print(f"[teleop_exo.launch.py] 外骨骼遥操作模式（使用话题重映射）")
    print(f"[teleop_exo.launch.py] 从臂配置:")
    for i, (ns, ip) in enumerate(zip(slave_namespaces, slave_arm_ips)):
        print(f"  - {ns}: {ip}")
    print(f"[teleop_exo.launch.py] 话题重映射:")
    print(f"  - /left_arm_joint_control → /exo_left_joint_control")
    print(f"  - /right_arm_joint_control → /exo_right_joint_control")

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
        # 关键：使用remappings重映射话题，不修改源码
        remappings=[
            ('/left_arm_joint_control', '/exo_left_joint_control'),
            ('/right_arm_joint_control', '/exo_right_joint_control'),
        ]
    )

    linkerta_launch = TimerAction(
        period=1.0,
        actions=[linkerta_node]
    )

    # 3. 启动 teleop_bridge (桥接节点) - 延迟2秒
    # 注意：需要修改 teleop_config.yaml 中的 master_left_topic 为 /exo_left_joint_control
    teleop_bridge_node = Node(
        package='lbot_teleop',
        executable='teleop_bridge_node',
        name='teleop_bridge_node',
        output='screen',
        parameters=[
            teleop_bridge_params,
            {
                "slave_namespaces": slave_namespaces,
                # 通过参数覆盖配置文件中的话题名称
                "master_left_topic": "/exo_left_joint_control",
                "master_right_topic": "/exo_right_joint_control",
            }
        ]
    )

    teleop_bridge_launch = TimerAction(
        period=2.0,
        actions=[teleop_bridge_node]
    )

    return LaunchDescription([
        *driver_nodes,          # 所有从臂驱动节点
        linkerta_launch,        # 主臂节点（重映射话题）
        teleop_bridge_launch,   # 桥接节点
    ])
