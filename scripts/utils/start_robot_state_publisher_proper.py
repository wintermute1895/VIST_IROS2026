#!/usr/bin/env python3
"""
启动robot_state_publisher，正确处理package://路径
"""

import os
from pathlib import Path
import rclpy
from rclpy.node import Node

def main():
    # URDF文件路径
    urdf_path = Path("/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description.urdf")

    # 读取URDF内容
    with open(urdf_path, 'r') as f:
        urdf_content = f.read()

    # 替换package://路径为file://路径（仅用于Pinocchio）
    # 但保持原始内容用于ROS2参数
    mesh_base = "/home/ilex/Dev/VIST/config"

    # 设置ROS_PACKAGE_PATH环境变量
    # 这样robot_state_publisher就能找到package://my_robot/
    os.environ['ROS_PACKAGE_PATH'] = f"{mesh_base}:{os.environ.get('ROS_PACKAGE_PATH', '')}"

    # 启动robot_state_publisher
    os.system(f"""
    ros2 run robot_state_publisher robot_state_publisher \\
        --ros-args \\
        -p robot_description:="{urdf_content.replace('"', '\\"')}"
    """)

if __name__ == '__main__':
    main()