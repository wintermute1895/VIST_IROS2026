import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 你的 URDF 绝对路径
    urdf_path = '/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description.urdf'
    
    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}]
        )
    ])