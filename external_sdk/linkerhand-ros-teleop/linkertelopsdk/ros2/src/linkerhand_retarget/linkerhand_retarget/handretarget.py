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


_script_dir = str(Path(__file__).parent)
# 使用本地 linkerhand
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from linkerhand.utils import *
from linkerhand.vtrdyncore import *
from linkerhand.handcore import HandCore
from linkerhand.config import HandConfig
from linkerhand.constants import RetargetingType, DataSource, MotionSource, RobotName

from ament_index_python.packages import get_package_share_directory
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseArray


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

        package_share_dir = Path(get_package_share_directory('linkerhand_retarget'))

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
                ('calibration', False)
            ]
        )
        #
        self.scene, self.retargeting_r, self.retargeting_l, self.config_r, self.config_l = None, None, None, None, None
        self.robot_name_r, self.robot_name_l = None, None
        self.retargeting_type = None
        self.datasource_type = None
        self.motion_type = None
        self.udp_ip, self.udp_port, self.use_can, self.motion_device = None, None, None, None

        self.calibration = self.get_parameter('calibration').value
        print(f"是否启用标定: {self.calibration} ")
        self.calibrationopen_r, self.calibrationopen_l, self.calibrationclose_r, self.calibrationclose_l = None, None, None, None
        self.retarget = None
        self.datasource_type = DataSource[self.baseconfig["system"]["datasource_type"]]
        self.retargeting_type = RetargetingType[self.baseconfig["system"]["retargeting_type"]]
        self.motion_type = MotionSource[self.baseconfig["system"]["motion_type"]]
        self.robot_name_r = RobotName[self.baseconfig["system"]["robotname_r"]]
        self.robot_name_l = RobotName[self.baseconfig["system"]["robotname_l"]]

        self.udp_ip = self.baseconfig["udp"]["ip"]
        self.udp_port = int(self.baseconfig["udp"]["port"])
        self.use_can = bool(self.baseconfig["system"]["usecan"])
        self.motion_device = self.baseconfig["system"]["motion_device"]

        self.righthandprint = bool(self.baseconfig["debug"]["joint_motor_debug_r"])
        self.lefthandprint = bool(self.baseconfig["debug"]["joint_motor_debug_l"])

        # if self.datasource_type == DataSource.vr:
        #     self.vr_right_sub = self.create_subscription(
        #         JointState,
        #         '/vr_right_hand_pose',
        #         self.vr_right_pose_callback,
        #         10)
        #     self.vr_left_sub = self.create_subscription(
        #         JointState,
        #         '/vr_left_hand_pose',
        #         self.vr_left_pose_callback,
        #         10)
        # elif self.datasource_type == DataSource.video:
        #     self.video_right_sub = self.create_subscription(
        #         JointState,
        #         '/video_right_hand_pose',
        #         self.video_right_pose_callback,
        #         10)
        #     self.video_left_sub = self.create_subscription(
        #         JointState,
        #         '/video_left_hand_pose',
        #         self.video_left_pose_callback,
        #         10)
        
        self.pubprintcount = 0

    def retargetrun(self):
        if self.motion_type == MotionSource.udexreal:
            from linkerhand_retarget.motion.udexreal.retarget import Retarget
            self.retarget = Retarget(
                self,
                ip=self.udp_ip,
                port=self.udp_port,
                deviceid=self.motion_device,
                righthand=self.robot_name_r,
                lefthand=self.robot_name_l,
                handcore=self.handcore,
                lefthandpubprint=self.lefthandprint,
                righthandpubprint=self.righthandprint
            )
        elif self.motion_type == MotionSource.udexrealv2t:
            from linkerhand_retarget.motion.udexrealv2t.retarget import Retarget
            self.retarget = Retarget(
                self,
                ip=self.udp_ip,
                port=self.udp_port,
                deviceid=self.motion_device,
                righthand=self.robot_name_r,
                lefthand=self.robot_name_l,
                handcore=self.handcore,
                lefthandpubprint=self.lefthandprint,
                righthandpubprint=self.righthandprint,
                calibration = self.calibration
            )
        elif self.motion_type == MotionSource.linkerforce:
            from linkerhand_retarget.motion.linkerforce.retarget import Retarget
            self.retarget = Retarget(
                self,
                righthand=self.robot_name_r,
                lefthand=self.robot_name_l,
                handcore=self.handcore,
                lefthandpubprint=self.lefthandprint,
                righthandpubprint=self.righthandprint,
                calibration = self.calibration
            )
        elif self.motion_type == MotionSource.vtrdyn:
            from linkerhand_retarget.motion.vtrdyn.retarget import Retarget
            self.retarget = Retarget(
                self,
                ip=self.udp_ip,
                port=self.udp_port,
                righthand=self.robot_name_r,
                lefthand=self.robot_name_l,
                handcore=self.handcore,
                lefthandpubprint=self.lefthandprint,
                righthandpubprint=self.righthandprint,
                calibration = self.calibration
            )     
        elif self.motion_type == MotionSource.linkermcg:
            from linkerhand_retarget.motion.linkermcg.retarget import Retarget
            self.retarget = Retarget(
                self,
                ip=self.udp_ip,
                port=self.udp_port,
                righthand=self.robot_name_r,
                lefthand=self.robot_name_l,
                handcore=self.handcore,
                lefthandpubprint=self.lefthandprint,
                righthandpubprint=self.righthandprint
            )    
        if self.retarget is None:
            self.get_logger().error("未正确创建应用实例")
        else:
            print("启动应用实例")
            self.retarget.process()

def main(args=None):
    rclpy.init(args=args)
    
    try:
        signal.signal(signal.SIGINT, signal_handler)
        node = HandRetargetNode()
        executor = MultiThreadedExecutor()
        node.retargetrun()
        
        # Keep the node alive
        rclpy.spin(node, executor)
    except KeyboardInterrupt:
        node.get_logger().info("收到终止信号")       
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
