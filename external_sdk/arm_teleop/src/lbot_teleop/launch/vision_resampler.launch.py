from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    """
    视觉控制专用launch文件
    启动高频重采样节点，将30Hz视觉输入插值到200Hz
    """
    # 获取配置文件路径
    pkg_share = get_package_share_directory('lbot_teleop')
    config_file = os.path.join(pkg_share, 'config', 'vision_resampler.yaml')

    return LaunchDescription([
        # 高频重采样节点（视觉专用）
        Node(
            package='lbot_teleop',
            executable='high_freq_resampler_node',
            name='high_freq_resampler_node',
            output='screen',
            parameters=[config_file],
            emulate_tty=True,
        ),
    ])
