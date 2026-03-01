from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # 获取配置文件路径
    pkg_share = get_package_share_directory('lbot_teleop')
    config_file = os.path.join(pkg_share, 'config', 'high_freq_resampler.yaml')

    return LaunchDescription([
        # 声明参数
        DeclareLaunchArgument(
            'config_file',
            default_value=config_file,
            description='Path to the high-freq resampler config file'
        ),

        # 高频重采样节点
        Node(
            package='lbot_teleop',
            executable='high_freq_resampler_node',
            name='high_freq_resampler_node',
            output='screen',
            parameters=[LaunchConfiguration('config_file')],
            emulate_tty=True,
        ),
    ])
