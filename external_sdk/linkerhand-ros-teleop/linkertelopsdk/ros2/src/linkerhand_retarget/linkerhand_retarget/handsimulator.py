#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# 强制使用src目录的路径
def setup_src_paths():
    """确保使用src目录而不是build目录"""
    # 获取工作空间的绝对路径
    current_file = Path(__file__).absolute()
    workspace_dir = current_file.parent.parent.parent.parent
    
    # 添加src目录到Python路径
    src_package_dir = workspace_dir / "src" / "linkerhand_retarget" / "linkerhand_retarget"
    if src_package_dir.exists():
        paths_to_add = [
            src_package_dir,
            src_package_dir / "linkerhand",
        ]
        
        for path in paths_to_add:
            if path.exists() and str(path) not in sys.path:
                sys.path.insert(0, str(path))
    
    return src_package_dir

workspace_dir = setup_src_paths()


import time
from threading import Thread, Event
from pathlib import Path
from queue import Empty
from typing import Optional
import numpy as np
import enum
import signal, sys

from .linkerhand.utils import *
from .linkerhand.vtrdyncore import *
from .linkerhand.handcore import HandCore
from .linkerhand.config import HandConfig

from ament_index_python.packages import get_package_share_directory
from pathlib import Path

import rclpy
import rclpy.qos
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseArray

import sapien
import tyro
from loguru import logger
from sapien.asset import create_dome_envmap
from sapien.utils import Viewer

from .linkerhand.constants import (
    RetargetingType, 
    DataSource, 
    ROBOT_LEN_MAP,
    MotionSource, 
    RobotName, 
    HandType, 
    get_default_config_path,
)
from .linkerhand.retargeting_config import RetargetingConfig

vr_pose_cache_r = []
vr_pose_cache_l = []
video_pose_cache_r = []
video_pose_cache_l = []
reangle_r = []
reangle_l = []
right_hand_pose_end = []
left_hand_pose_end = []


def signal_handler(sig, frame):
    rclpy.shutdown()
    sys.exit(0)


class HandRetargetNode(Node):
    def __init__(self):
        super().__init__('handretarget_node')
        print("Ready Create HandRetargetNode!")

        package_share_dir = workspace_dir

        self.robot_dir = package_share_dir  / "assets" / "robots" / "hands"
        self.base_config = package_share_dir 

        self.handconfig = HandConfig(str(self.robot_dir), str(self.base_config))
        self.handcore = HandCore(self.handconfig)

        self.baseconfig = self.handconfig.baseconfig
        self.retagetconfig = self.handconfig.retagetconfig

        # 声明参数并提供默认值
        self.declare_parameters(
            namespace='',
            parameters=[
                ('driver', False)
            ]
        )
        #
        self.scene, self.retargeting_r, self.retargeting_l, self.config_r, self.config_l = None, None, None, None, None
        self.robot_name_r, self.robot_name_l = None, None
        self.retargeting_type = None
        self.datasource_type = None
        self.motion_type = None
        self.udp_ip, self.udp_port, self.use_can, self.motion_device = None, None, None, None

        self.retarget = None
        self.datasource_type = DataSource[self.baseconfig["system"]["datasource_type"]]
        self.retargeting_type = RetargetingType[self.baseconfig["system"]["retargeting_type"]]
        self.motion_type = MotionSource[self.baseconfig["system"]["motion_type"]]
        self.robot_name_r = RobotName[self.baseconfig["system"]["robotname_r"]]
        self.robot_name_l = RobotName[self.baseconfig["system"]["robotname_l"]]
        self.driverenable = self.get_parameter('driver').value
        self.config_path = get_default_config_path(self.robot_name_r, self.retargeting_type, HandType.right)
        if self.baseconfig["system"]["sapientype"] == "left":
            self.config_path = get_default_config_path(self.robot_name_l, self.retargeting_type, HandType.left)
        RetargetingConfig.set_default_urdf_dir(str(self.robot_dir))

        self.retargeting = RetargetingConfig.load_from_file(self.config_path).build()
        self.udp_ip = self.baseconfig["udp"]["ip"]
        self.udp_port = int(self.baseconfig["udp"]["port"])
        self.use_can = bool(self.baseconfig["system"]["usecan"])
        self.motion_device = self.baseconfig["system"]["motion_device"]

        self.righthandprint = bool(self.baseconfig["debug"]["joint_motor_debug_r"])
        self.lefthandprint = bool(self.baseconfig["debug"]["joint_motor_debug_l"])

        self.robot, self.sapien_joint_names, self.viewer  = None, None, None

        self.left_hand_angles = []  # 左手各关节角度值列表
        self.right_hand_angles = []  # 右手各关节角度值列表

        self.qpos = None
        self.g_jointpositions = None
        qos_profile = rclpy.qos.QoSProfile(
            depth=100,
            reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
            history=rclpy.qos.QoSHistoryPolicy.KEEP_LAST
        )
        # ROS2 接收器
        self.left_angle_subscription = self.create_subscription(
            JointState,
            '/cb_left_hand_control_angle_cmd',
            self.angle_left_callback,
            10  # QoS 队列深度
        )
        self.right_angle_subscription = self.create_subscription(
            JointState,
            '/cb_right_hand_control_angle_cmd', 
            self.angle_right_callback,
            10  # QoS 队列深度
        )

        # ROS2 发布器
        self.publisher_r = self.create_publisher(
            JointState,
            '/cb_right_hand_control_cmd',
            self.handcore.hand_numjoints_r)
            
        self.publisher_l = self.create_publisher(
            JointState,
            '/cb_left_hand_control_cmd',
            self.handcore.hand_numjoints_l)

    def sapien_init(self):
        sapien.render.set_viewer_shader_dir("default")
        sapien.render.set_camera_shader_dir("default")

        config = RetargetingConfig.load_from_file(self.config_path)

        # Setup
        scene = sapien.Scene()
        render_mat = sapien.render.RenderMaterial()
        render_mat.base_color = [0.06, 0.08, 0.12, 1]
        render_mat.metallic = 0.0
        render_mat.roughness = 0.9
        render_mat.specular = 0.8
        scene.add_ground(-0.2, render_material=render_mat, render_half_size=[1000, 1000])

        # Lighting
        scene.add_directional_light(np.array([1, 1, -1]), np.array([3, 3, 3]))
        scene.add_point_light(np.array([2, 2, 2]), np.array([2, 2, 2]), shadow=False)
        scene.add_point_light(np.array([2, -2, 2]), np.array([2, 2, 2]), shadow=False)
        scene.set_environment_map(
            create_dome_envmap(sky_color=[0.2, 0.2, 0.2], ground_color=[0.2, 0.2, 0.2])
        )
        scene.add_area_light_for_ray_tracing(
            sapien.Pose([2, 1, 2], [0.707, 0, 0.707, 0]), np.array([1, 1, 1]), 5, 5
        )

        # Camera
        cam = scene.add_camera(
            name="Cheese!", width=600, height=600, fovy=1, near=0.1, far=10
        )
        cam.set_local_pose(sapien.Pose([0.50, 0, 0.0], [0, 0, 0, -1]))

        self.viewer = Viewer()
        self.viewer.set_scene(scene)
        self.viewer.control_window.show_origin_frame = False
        self.viewer.control_window.move_speed = 0.01
        self.viewer.control_window.toggle_camera_lines(False)
        self.viewer.set_camera_pose(cam.get_local_pose())

        # Load robot and set it to a good pose to take picture
        loader = scene.create_urdf_loader()
        filepath = Path(config.urdf_path)
        robot_name = filepath.stem
        loader.load_multiple_collisions_from_file = True
        loader.scale = 1.5

        filepath = str(filepath)
        self.robot = loader.load(filepath)
        self.robot.set_pose(sapien.Pose([0, 0, -0.13]))

        # Different robot loader may have different orders for joints
        self.sapien_joint_names = [joint.get_name() for joint in self.robot.get_active_joints()]
        retargeting_joint_names = self.retargeting.joint_names
        retargeting_to_sapien = np.array(
            [retargeting_joint_names.index(name) for name in self.sapien_joint_names]
        ).astype(int)

        self.qpos = [0] * len(self.sapien_joint_names)

    def angle_left_callback(self, msg):
        self.left_hand_angles = list(msg.position)  # 将元组转换为列表  
           
    def angle_right_callback(self, msg):
        self.right_hand_angles = list(msg.position)  # 将元组转换为列表   

    def get_left_hand_angles(self):
        """获取当前左手角度值"""
        return self.left_hand_angles.copy()  # 返回副本以避免外部修改
    
    def get_right_hand_angles(self):
        """获取当前右手角度值"""
        return self.right_hand_angles.copy()  # 返回副本以避免外部修改

    def process_callback(self):
        self.viewer.render()
        if self.driverenable :
            joint_arc = self.robot.get_qpos()
            if self.baseconfig["system"]["sapientype"] == "right":
                if self.robot_name_r == RobotName.o7 \
                    or self.robot_name_r == RobotName.l7 \
                    or self.robot_name_r == RobotName.o7v1 \
                    or self.robot_name_r == RobotName.o7v3:
                    self.qpos = np.zeros(25)
                    self.qpos[16] = joint_arc[0]
                    self.qpos[17] = joint_arc[5]
                    self.qpos[18] = joint_arc[10]
                    self.qpos[19] = joint_arc[10]
                    self.qpos[20] = joint_arc[10]

                    # 食指 index
                    self.qpos[0] = joint_arc[1]
                    self.qpos[1] = joint_arc[1]
                    self.qpos[2] = joint_arc[1]
                    self.qpos[3] = joint_arc[1]

                    # 小指 little
                    self.qpos[4] = joint_arc[4]
                    self.qpos[5] = joint_arc[4]
                    self.qpos[6] = joint_arc[4]
                    self.qpos[7] = joint_arc[4]

                    # 中指 middle
                    self.qpos[8] = joint_arc[2]
                    self.qpos[9] = joint_arc[2]
                    self.qpos[10] = joint_arc[2]
                    self.qpos[11] = joint_arc[2]

                    # 无名指 ring
                    self.qpos[12] = joint_arc[3]
                    self.qpos[13] = joint_arc[3]
                    self.qpos[14] = joint_arc[3]
                    self.qpos[15] = joint_arc[3] 

                    self.g_jointpositions = self.handcore.trans_to_motor_right(self.qpos)
                elif self.robot_name_r == RobotName.o6 \
                    or self.robot_name_r == RobotName.l6:
                    
                    self.qpos = np.zeros(25)
                    self.qpos[16] = joint_arc[0]
                    self.qpos[17] = joint_arc[0]
                    self.qpos[18] = joint_arc[5]
                    self.qpos[19] = joint_arc[5]
                    self.qpos[20] = joint_arc[5]

                    # 食指 index
                    self.qpos[0] = joint_arc[1]
                    self.qpos[1] = joint_arc[1]
                    self.qpos[2] = joint_arc[1]
                    self.qpos[3] = joint_arc[1]

                    # 小指 little
                    self.qpos[4] = joint_arc[4]
                    self.qpos[5] = joint_arc[4]
                    self.qpos[6] = joint_arc[4]
                    self.qpos[7] = joint_arc[4]

                    # 中指 middle
                    self.qpos[8] = joint_arc[2]
                    self.qpos[9] = joint_arc[2]
                    self.qpos[10] = joint_arc[2]
                    self.qpos[11] = joint_arc[2]

                    # 无名指 ring
                    self.qpos[12] = joint_arc[3]
                    self.qpos[13] = joint_arc[3]
                    self.qpos[14] = joint_arc[3]
                    self.qpos[15] = joint_arc[3] 

                    self.g_jointpositions = self.handcore.trans_to_motor_right(self.qpos)
                elif self.robot_name_r == RobotName.l20:
                    pass
                elif self.robot_name_r == RobotName.l10 \
                    or self.robot_name_r == RobotName.l10v6 \
                    or self.robot_name_r == RobotName.l10v7 :
                    pass
                elif self.robot_name_r == RobotName.l21:
                    pass
                else:
                    return
                if self.g_jointpositions is None:
                    return
                msg_r = JointState()
                msg_r.header.stamp = self.get_clock().now().to_msg()
                msg_r.name = [f'joint{i + 1}' for i in range(len(self.g_jointpositions))]
                msg_r.position = [float(num) for num in self.g_jointpositions]
                self.publisher_r.publish(msg_r)
            elif self.baseconfig["system"]["sapientype"] == "left":
                if self.robot_name_l == RobotName.o7 \
                    or self.robot_name_l == RobotName.l7 \
                    or self.robot_name_l == RobotName.o7v1 \
                    or self.robot_name_l == RobotName.o7v3:
                    self.qpos = np.zeros(25)
                    self.qpos[16] = joint_arc[0]
                    self.qpos[17] = joint_arc[5]
                    self.qpos[18] = joint_arc[10]
                    self.qpos[19] = joint_arc[10]
                    self.qpos[20] = joint_arc[10]

                    # 食指 index
                    self.qpos[0] = joint_arc[1]
                    self.qpos[1] = joint_arc[1]
                    self.qpos[2] = joint_arc[1]
                    self.qpos[3] = joint_arc[1]

                    # 小指 little
                    self.qpos[4] = joint_arc[4]
                    self.qpos[5] = joint_arc[4]
                    self.qpos[6] = joint_arc[4]
                    self.qpos[7] = joint_arc[4]

                    # 中指 middle
                    self.qpos[8] = joint_arc[2]
                    self.qpos[9] = joint_arc[2]
                    self.qpos[10] = joint_arc[2]
                    self.qpos[11] = joint_arc[2]

                    # 无名指 ring
                    self.qpos[12] = joint_arc[3]
                    self.qpos[13] = joint_arc[3]
                    self.qpos[14] = joint_arc[3]
                    self.qpos[15] = joint_arc[3]
                    self.g_jointpositions = self.handcore.trans_to_motor_left(self.qpos) 
                elif self.robot_name_l == RobotName.o6 \
                    or self.robot_name_l == RobotName.l6:
                    self.qpos = np.zeros(25)
                    self.qpos[16] = joint_arc[0]
                    self.qpos[17] = joint_arc[0]
                    self.qpos[18] = joint_arc[5]
                    self.qpos[19] = joint_arc[5]
                    self.qpos[20] = joint_arc[5]

                    # 食指 index
                    self.qpos[0] = joint_arc[1]
                    self.qpos[1] = joint_arc[1]
                    self.qpos[2] = joint_arc[1]
                    self.qpos[3] = joint_arc[1]

                    # 小指 little
                    self.qpos[4] = joint_arc[4]
                    self.qpos[5] = joint_arc[4]
                    self.qpos[6] = joint_arc[4]
                    self.qpos[7] = joint_arc[4]

                    # 中指 middle
                    self.qpos[8] = joint_arc[2]
                    self.qpos[9] = joint_arc[2]
                    self.qpos[10] = joint_arc[2]
                    self.qpos[11] = joint_arc[2]

                    # 无名指 ring
                    self.qpos[12] = joint_arc[3]
                    self.qpos[13] = joint_arc[3]
                    self.qpos[14] = joint_arc[3]
                    self.qpos[15] = joint_arc[3] 

                    self.g_jointpositions = self.handcore.trans_to_motor_left(self.qpos)
                elif self.robot_name_l == RobotName.l20:
                    pass
                elif self.robot_name_l == RobotName.l10 \
                    or self.robot_name_l == RobotName.l10v6 \
                    or self.robot_name_l == RobotName.l10v7 :
                    self.qpos = np.zeros(25)
                    self.qpos[16] = joint_arc[0]        # roll
                    self.qpos[17] = joint_arc[5]        
                    self.qpos[18] = joint_arc[10]
                    self.qpos[19] = joint_arc[10]
                    self.qpos[20] = joint_arc[10]

                    # 食指 index
                    self.qpos[0] = joint_arc[1] * -1       # roll
                    self.qpos[1] = joint_arc[6]
                    self.qpos[2] = joint_arc[6]
                    self.qpos[3] = joint_arc[6]

                    # 小指 little
                    self.qpos[4] = joint_arc[4] * -1       # roll
                    self.qpos[5] = joint_arc[8]
                    self.qpos[6] = joint_arc[8]
                    self.qpos[7] = joint_arc[8]

                    # 中指 middle
                    self.qpos[8] = joint_arc[2]        # roll
                    self.qpos[9] = joint_arc[2]
                    self.qpos[10] = joint_arc[2]
                    self.qpos[11] = joint_arc[2]

                    # 无名指 ring
                    self.qpos[12] = joint_arc[3]  * -1        # roll
                    self.qpos[13] = joint_arc[7]
                    self.qpos[14] = joint_arc[7]
                    self.qpos[15] = joint_arc[7] 

                    self.g_jointpositions = self.handcore.trans_to_motor_right(self.qpos)
                elif self.robot_name_l == RobotName.l21:
                    pass
                else:
                    return
                if self.g_jointpositions is None:
                    return
                # 发布左手数据
                msg_l = JointState()
                msg_l.header.stamp = self.get_clock().now().to_msg()
                msg_l.name = [f'joint{i + 1}' for i in range(len(self.g_jointpositions))]
                msg_l.position = [float(num) for num in self.g_jointpositions]
                self.publisher_l.publish(msg_l)
        else:
            if self.baseconfig["system"]["sapientype"] == "right":
                pos_source = self.get_right_hand_angles()
                # print(f"pos_source:{pos_source}")
                if len(pos_source) > 0 :
                    if self.robot_name_r == RobotName.o7 \
                        or self.robot_name_r == RobotName.l7 \
                        or self.robot_name_r == RobotName.o7v1 \
                        or self.robot_name_r == RobotName.o7v3:
                        pass
                    elif self.robot_name_r == RobotName.o6 \
                        or self.robot_name_r == RobotName.l6:
                        self.qpos[0] = pos_source[1]
                        self.qpos[1] = pos_source[2]
                        self.qpos[2] = pos_source[3]
                        self.qpos[3] = pos_source[4]
                        self.qpos[4] = pos_source[5]
                        self.qpos[5] = pos_source[0]
                        self.qpos[6] = pos_source[2] * 0.89
                        self.qpos[7] = pos_source[3] * 0.89
                        self.qpos[8] = pos_source[4] * 0.89
                        self.qpos[9] = pos_source[5] * 0.89
                        self.qpos[10] = pos_source[0] * 1.86

                    elif self.robot_name_r == RobotName.l20:
                        pass
                    elif self.robot_name_r == RobotName.l10 \
                        or self.robot_name_r == RobotName.l10v6 \
                        or self.robot_name_r == RobotName.l10v7 :
                        pass
                    elif self.robot_name_r == RobotName.l21:
                        pass
                    
            elif self.baseconfig["system"]["sapientype"] == "left":
                pos_source = self.get_left_hand_angles()
                if len(pos_source) > 0 :
                    if self.robot_name_l == RobotName.o7 \
                        or self.robot_name_l == RobotName.l7 \
                        or self.robot_name_l == RobotName.o7v1 \
                        or self.robot_name_l == RobotName.o7v3:
                        pass
                    elif self.robot_name_r == RobotName.o6 \
                        or self.robot_name_r == RobotName.l6:
                        self.qpos[0] = pos_source[1]
                        self.qpos[1] = pos_source[2]
                        self.qpos[2] = pos_source[3]
                        self.qpos[3] = pos_source[4]
                        self.qpos[4] = pos_source[5]
                        self.qpos[5] = pos_source[0]
                        self.qpos[6] = pos_source[2] * 0.89
                        self.qpos[7] = pos_source[3] * 0.89
                        self.qpos[8] = pos_source[4] * 0.89
                        self.qpos[9] = pos_source[5] * 0.89
                        self.qpos[10] = pos_source[0] * 1.86
                    elif self.robot_name_l == RobotName.l20:
                        pass
                    elif self.robot_name_l == RobotName.l10 \
                        or self.robot_name_l == RobotName.l10v6 \
                        or self.robot_name_l == RobotName.l10v7 :
                        pass
                    elif self.robot_name_l == RobotName.l21:
                        pass
            # print(f"qpos:{self.qpos}")
            self.robot.set_qpos(self.qpos)
        

def main(args=None):
    rclpy.init(args=args)
    
    try:
        signal.signal(signal.SIGINT, signal_handler)
        node = HandRetargetNode()
        node.sapien_init()
        node.create_timer(1.0/240, node.process_callback)  # 120Hz
        # Keep the node alive
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("收到终止信号")       
    finally:
        node.get_logger().info("系统退出")       
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()