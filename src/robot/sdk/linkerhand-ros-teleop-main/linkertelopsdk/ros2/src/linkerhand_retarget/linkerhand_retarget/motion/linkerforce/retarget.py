import time
import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from pathlib import Path

# 将项目根目录放在最前面
# 强制使用项目本地的 linkerhand 模块
_project_root = Path(__file__).absolute().parent.parent.parent
_project_root_str = str(_project_root)

if _project_root_str in sys.path:
    sys.path.remove(_project_root_str)
sys.path.insert(0, _project_root_str)

from linkerhand.linkerforce import ForceSerialReader
from linkerhand.constants import RobotName, ROBOT_LEN_MAP, HandType
from linkerhand.handcore import HandCore
from tqdm import tqdm
from pathlib import Path
from colorama import Fore, init
from datetime import datetime, timedelta
import threading
import copy
import pickle
import os
import json
import sys
import numpy as np


TMP_FILE_PATH = Path(__file__).parent / "tmp" / "jointangle_data.tmp"

class Retarget():
    def __init__(self, 
                node,
                righthand: RobotName, 
                lefthand: RobotName, 
                handcore: HandCore,
                lefthandpubprint: bool, 
                righthandpubprint: bool,
                calibration: bool = False,
                auto_detect: bool = True,
                isgetdebug: bool = False):
        """
        初始化 LinkerForce Retarget 模块 (ROS1 版本)
        
        Args:
            leftport: 左手串口路径（如 '/dev/ttyUSB0'），auto_detect=True 时可忽略
            leftbaudrate: 左手波特率
            rightport: 右手串口路径（如 '/dev/ttyUSB1'），auto_detect=True 时可忽略
            rightbaudrate: 右手波特率
            lefthand: 左手机器人类型
            righthand: 右手机器人类型
            handcore: HandCore 实例
            lefthandpubprint: 是否打印左手调试信息
            righthandpubprint: 是否打印右手调试信息
            calibration: True=强制标定, False=尝试加载缓存
            auto_detect: 是否自动检测串口（默认 True）
            isgetdebug: 是否发布debug测试数据话题（默认False）
        """        

        self.node = node
        self.lefthandtype = lefthand
        self.righthandtype = righthand
        self.handcore = handcore
        self.runing = True
        self.lefthandpubprint = lefthandpubprint
        self.righthandpubprint = righthandpubprint
        self.isdebugpub = isgetdebug

        # 根据右手类型初始化
        if self.righthandtype == RobotName.o7 \
            or self.righthandtype == RobotName.l7 \
            or self.righthandtype == RobotName.o7v1 \
            or self.righthandtype == RobotName.o7v3:
            from .hand.linkerforce_l7 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
            
        elif self.righthandtype == RobotName.o6:
            from .hand.linkerforce_o6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l6:
            from .hand.linkerforce_l6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        # elif self.righthandtype == RobotName.l25:
        #     from .hand.linkerforce_l25 import RightHand
        #     self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        # elif self.righthandtype == RobotName.t25:
        #     from .hand.linkerforce_t25 import RightHand
        #     self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l20:
            from .hand.linkerforce_l20 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l10v6 :
            from .hand.linkerforce_l10v6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])        
        elif self.righthandtype == RobotName.l10 \
            or self.righthandtype == RobotName.l10v7 :
            from .hand.linkerforce_l10 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l21:
            from .hand.linkerforce_l21 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])

        # 根据左手类型初始化
        if self.lefthandtype == RobotName.o7 \
            or self.lefthandtype == RobotName.l7 \
            or self.lefthandtype == RobotName.o7v1 \
            or self.lefthandtype == RobotName.o7v3:
            from .hand.linkerforce_l7 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.o6:
            from .hand.linkerforce_o6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l6:
            from .hand.linkerforce_l6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l25:
            from .hand.linkerforce_l25 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        # elif self.lefthandtype == RobotName.t25:
        #     from .hand.linkerforce_t25 import LeftHand
        #     self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l20:
            from .hand.linkerforce_l20 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l10v6 :
            from .hand.linkerforce_l10v6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l10 \
            or self.lefthandtype == RobotName.l10v7 :
            from .hand.linkerforce_l10 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l21:
            from .hand.linkerforce_l21 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])

        # ROS2 发布器
        self.publisher_r = self.node.create_publisher(
            JointState,
            '/cb_right_hand_control_cmd',
            self.handcore.hand_numjoints_r)
            
        self.publisher_l = self.node.create_publisher(
            JointState,
            '/cb_left_hand_control_cmd',
            self.handcore.hand_numjoints_l)

        self.publisher_angle_r = self.node.create_publisher(
            JointState,
            '/cb_right_hand_control_angle_cmd',
            self.handcore.hand_numjoints_r)
            
        self.publisher_angle_l = self.node.create_publisher(
            JointState,
            '/cb_left_hand_control_angle_cmd',
            self.handcore.hand_numjoints_l)

        # 创建订阅者，订阅/cb_left_hand_matrix_touch话题
        self.left_touch_subscription = self.node.create_subscription(
            String,
            '/cb_left_hand_matrix_touch',
            self.touch_left_callback,
            10  # QoS 队列深度
        )
        self.right_touch_subscription = self.node.create_subscription(
            String,
            '/cb_right_hand_matrix_touch', 
            self.touch_right_callback,
            10  # QoS 队列深度
        )

        if self.isdebugpub:
            pass

        # 初始化统计结果
        self.results = {
            'left':{},
            'right':{}
        } 
        self.leftforcesendcount = -1
        self.rightforcesendcount = -1

        # 状态变量
        self.pubprintcount = 0
        self.force_reader_left = None
        self.force_reader_right = None
        self.calibration = calibration

        # 力数据线程锁
        self.forcelock = threading.Lock()

        # 自动标定相关变量
        self.calibration_data_left = []
        self.calibration_data_right = []
        self.calibration_in_progress = False
        
        # ========== 调试：映射层跳变检测 ==========
        self.debug_enabled = True  # 设为 False 关闭调试
        self.debug_motor_jump_threshold = 20  # 电机值跳变阈值
        self.debug_last_motor_l = [255] * 6
        self.debug_last_motor_r = [255] * 6
        self.debug_last_raw_l = [0.0] * 21
        self.debug_last_raw_r = [0.0] * 21



    def touch_left_callback(self, msg):
        self.process_touch_data(msg.data,'left')   
           
    def touch_right_callback(self, msg):
        self.process_touch_data(msg.data,'right')

    def process_touch_data(self, json_str, hand_type):
        with self.forcelock:
            try:
                data = json.loads(json_str)    
                self.results[hand_type] = {}
                # 处理每个手指的矩阵
                for finger in ['thumb_matrix', 'index_matrix', 'middle_matrix', 'ring_matrix', 'little_matrix']:
                    matrix = np.array(data[finger])
                    # 计算接触面积（非零元素数量）
                    contact_area = np.count_nonzero(matrix)         
                    # 计算总接触力
                    total_force = np.sum(matrix)         
                    # 计算平均接触力（避免除以零）
                    avg_force = total_force / contact_area if contact_area > 0 else 0
                    max_force = np.max(matrix) if contact_area > 0 else 0
                    if max_force > 200:
                        max_force = 200
                    self.results[hand_type][finger] = {
                        'contact_area': contact_area,
                        'total_force': total_force,
                        'avg_force': avg_force,
                        'max_force': max_force
                    }
            except Exception as e:
                self.node.get_logger().error("Error processing touch data: %s" % str(e))
                return None

    def linkerforce_init(self):
        exclude_list = []
        baudrates = [2000000, 1000000, 921600, 460800]
        # 初始化 ForceSerialReader
        self.force_reader_left = ForceSerialReader(
                                    HandType.left,
                                    excludelist=exclude_list,
                                    baudrates=baudrates,
                                    isdebug=False
                                )
        self.leftport, self.leftbaudrate, errorcode = self.force_reader_left.find_valid_ports(timeout=0.001)
        if self.leftport:
            if self.force_reader_left.openserial(port=self.leftport,baudrate=self.leftbaudrate):
                self.force_reader_left.start()
                time.sleep(0.1)
                self.force_reader_left.serial_port.write(self.force_reader_left.pack_01_data())
                time.sleep(0.5)
                if self.force_reader_left.handtype.lower() == 'left':
                    self.node.get_logger().info(f"已搜索到左部力反馈手套,版本号{self.force_reader_left.version}")
                else:
                    self.node.get_logger().error("左手无法正常识别。")
            else:
                self.node.get_logger().error("启动失败!......")
            exclude_list.append(self.leftport)
        else:
            self.node.get_logger().error("未搜索到左部力反馈手套...")
        time.sleep(1)
        self.force_reader_right = ForceSerialReader(
                                    HandType.right,
                                    excludelist=exclude_list,
                                    baudrates=baudrates,
                                    isdebug=False
                                )
        self.rightport, self.rightbaudrate, errorcode = self.force_reader_right.find_valid_ports(timeout=0.001)
        if self.rightport:
            if self.force_reader_right.openserial(port=self.rightport,baudrate=self.rightbaudrate):
                self.force_reader_right.start()
                time.sleep(0.1)
                self.force_reader_right.serial_port.write(self.force_reader_right.pack_01_data())
                time.sleep(0.5)
                if self.force_reader_right.handtype == 'Right':
                    self.node.get_logger().info(f"已搜索到右部力反馈手套,版本号{self.force_reader_right.version}")
                else:
                    self.node.get_logger().error("右手无法正常识别。")
            else:
                self.node.get_logger().error("启动失败!......")
        else:
            self.node.get_logger().error("未搜索到右部力反馈手套...")
        time.sleep(1)

        # 标定流程
        if self.calibration is True:
            self.calibration = "auto_calibrate"
            self.node.get_logger().info("强制标定模式：将进行自动标定")
        else:
            if self._load_from_tmp() is True:
                self.node.get_logger().info("已加载缓存标定数据，跳过标定流程")
                self.calibration = -1
                self.righthand.initialize_mapper()
                self.lefthand.initialize_mapper()
            else:
                self.calibration = "auto_calibrate"
                self.node.get_logger().info("未找到有效缓存，将进行自动标定")
          
    def process_callback(self):
        self.pubprintcount += 1
        if self.force_reader_left is None and self.force_reader_right is None:
        #if self.force_reader_left.handtype != 'Left' and self.force_reader_right.handtype != 'Right':
            if self.pubprintcount % 20 == 0:
                self.node.get_logger().warn("无法检测到任意一只手套，系统退出！")
            return
        

        if self.force_reader_left.handtype == 'Left':
            # 读取左手位置数据
            left_positions = copy.deepcopy(self.force_reader_left.poslist)
            
            # 更新关节角度
            self.lefthand.joint_update(left_positions)
            
            # 速度环节处理
            self.lefthand.speed_update()
            # 力反馈处理
            with self.forcelock:
                if self.results['left']:
                    self.force_reader_left.forcelist = [
                            self.results['left']['thumb_matrix']['max_force'],
                            self.results['left']['index_matrix']['max_force'],
                            self.results['left']['middle_matrix']['max_force'],
                            self.results['left']['ring_matrix']['max_force'],
                            self.results['left']['little_matrix']['max_force']
                        ]
                    # print(self.results['left'] )
                    self.force_reader_left.serial_port.write(self.force_reader_left.pack_04_data())
            # 调试打印
            if self.lefthandpubprint and self.pubprintcount % 5 == 0:
                print(f"左手位置: {self.lefthand.g_jointpositions}")
            # 发布左手数据
            msg_l = JointState()
            msg_l.header.stamp = self.node.get_clock().now().to_msg()
            msg_l.name = [f'joint{i + 1}' for i in range(len(self.lefthand.g_jointpositions))]
            msg_l.position = [float(num) for num in self.lefthand.g_jointpositions]
            # msg_l.velocity = [float(num) for num in self.lefthand.g_jointvelocity]
            self.publisher_l.publish(msg_l)
            
            # 发布左手数据(映射弧度)
            # msg_arc_l = JointState()
            # msg_arc_l.header.stamp = self.node.get_clock().now().to_msg()
            # msg_arc_l.name = [f'joint{i + 1}' for i in range(len(self.lefthand.g_jointpositions_arc))]
            # msg_arc_l.position = [float(num) for num in self.lefthand.g_jointpositions_arc]
            # # msg_arc_l.velocity = [float(num) for num in self.lefthand.g_jointvelocity_arc]
            # self.publisher_angle_l.publish(msg_arc_l)


        if self.force_reader_right.handtype == 'Right':
            # 读取右手位置数据
            right_positions = copy.deepcopy(self.force_reader_right.poslist)

            # 更新关节角度
            self.righthand.joint_update(right_positions)
            
            # 速度环节处理
            self.righthand.speed_update()
            
            # 力反馈处理
            with self.forcelock:
                if self.results['right']:
                    self.force_reader_right.forcelist = [
                            self.results['right']['thumb_matrix']['max_force'],
                            self.results['right']['index_matrix']['max_force'],
                            self.results['right']['middle_matrix']['max_force'],
                            self.results['right']['ring_matrix']['max_force'],
                            self.results['right']['little_matrix']['max_force']
                        ]
                    # print(self.force_reader_right.forcelist)
                    self.force_reader_right.serial_port.write(self.force_reader_right.pack_04_data())
            # 调试打印
            if self.righthandpubprint and self.pubprintcount % 5 == 0:
                print(f"右手位置: {self.righthand.g_jointpositions}")

            # 发布右手数据
            msg_r = JointState()
            msg_r.header.stamp = self.node.get_clock().now().to_msg()
            msg_r.name = [f'joint{i + 1}' for i in range(len(self.righthand.g_jointpositions))]
            msg_r.position = [float(num) for num in self.righthand.g_jointpositions]
            msg_r.velocity = [float(num) for num in self.righthand.g_jointvelocity]
            self.publisher_r.publish(msg_r)

            # # 发布左手数据(映射弧度)
            # msg_arc_r = JointState()                                                                                                                                                         
            # msg_arc_r.header.stamp = self.node.get_clock().now().to_msg()
            # msg_arc_r.name = [f'joint{i + 1}' for i in range(len(self.righthand.g_jointpositions_arc))]
            # msg_arc_r.position = [float(num) for num in self.righthand.g_jointpositions_arc]
            # # msg_arc_l.velocity = [float(num) for num in self.lefthand.g_jointvelocity_arc]
            # self.publisher_angle_r.publish(msg_arc_r)
            
        self.pubprintcount += 1

    def _calculate_weighted_average(self, data_list):
        """
        计算加权平均值，后面的数据权重更高
        
        Args:
            data_list: 包含多帧数据的列表，每帧是21个关节值的列表
            
        Returns:
            加权平均后的21个关节值列表
        """
        if not data_list:
            return [0.0] * 21
        
        n = len(data_list)
        if n == 1:
            return data_list[0]
        
        # 生成权重：后面的数据权重更高
        weights = np.array([i + 1 for i in range(n)], dtype=float)
        weights = weights / weights.sum()
        
        # 转换为numpy数组进行计算
        data_array = np.array(data_list)
        
        # 加权平均
        weighted_avg = np.average(data_array, axis=0, weights=weights)
        
        return weighted_avg.tolist()

    def _calibration_with_progress(self, duration=5):
        """
        带进度条的标定数据采集
        
        Args:
            duration: 标定总时长（秒），前40%准备，后60%采集数据
        """
        prepare_ratio = 0.4
        collect_start = int(100 * prepare_ratio)
        
        with tqdm(total=100, desc=f"{Fore.CYAN}标定进度{Fore.RESET}",
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
            for i in range(100):
                time.sleep(duration / 100)
                
                # 后60%开始采集数据
                if i >= collect_start:
                    left_pos = copy.deepcopy(self.force_reader_left.poslist)
                    right_pos = copy.deepcopy(self.force_reader_right.poslist)
                    self.calibration_data_left.append(left_pos)
                    self.calibration_data_right.append(right_pos)
                
                pbar.update(1)

    def run_calibration(self):
        """
        执行自动标定流程
        """
        self.calibration_in_progress = True
        
        # ===== 第一步：五指张开标定 (对应255) =====
        self.calibration_data_left = []
        self.calibration_data_right = []
        print(f"\n{Fore.GREEN}{'='*50}{Fore.RESET}")
        print(f"{Fore.GREEN}【标定 1/3】请保持五指张开姿势 (对应电机值255){Fore.RESET}")
        print(f"{Fore.GREEN}{'='*50}{Fore.RESET}\n")
        
        self._calibration_with_progress(10)
        
        if len(self.calibration_data_left) > 0:
            avg_left_open = self._calculate_weighted_average(self.calibration_data_left)
            avg_right_open = self._calculate_weighted_average(self.calibration_data_right)
            self.lefthand.calibrationoriginal = avg_left_open
            self.righthand.calibrationoriginal = avg_right_open
        else:
            print(f"\n{Fore.RED}【标定失败】五指张开数据采集失败{Fore.RESET}\n")
            self.calibration_in_progress = False
            return False
        
        # ===== 第二步：握拳标定 (对应0) =====
        self.calibration_data_left = []
        self.calibration_data_right = []
        print(f"\n{Fore.YELLOW}{'='*50}{Fore.RESET}")
        print(f"{Fore.YELLOW}【标定 2/3】请握紧拳头 (对应电机值0){Fore.RESET}")
        print(f"{Fore.YELLOW}{'='*50}{Fore.RESET}\n")
        
        self._calibration_with_progress(10)
        
        if len(self.calibration_data_left) > 0:
            avg_left_fist = self._calculate_weighted_average(self.calibration_data_left)
            avg_right_fist = self._calculate_weighted_average(self.calibration_data_right)
            self.lefthand.calibrationfistpose = avg_left_fist
            self.righthand.calibrationfistpose = avg_right_fist
        else:
            print(f"\n{Fore.RED}【标定失败】握拳数据采集失败{Fore.RESET}\n")
            self.calibration_in_progress = False
            return False
        
        # ===== 第三步：O型标定 (对应中间值) =====
        self.calibration_data_left = []
        self.calibration_data_right = []
        print(f"\n{Fore.MAGENTA}{'='*50}{Fore.RESET}")
        print(f"{Fore.MAGENTA}【标定 3/3】请保持O型手势 (对应电机中间值){Fore.RESET}")
        print(f"{Fore.MAGENTA}{'='*50}{Fore.RESET}\n")
        
        self._calibration_with_progress(10)
        
        if len(self.calibration_data_left) > 0:
            avg_left_fist = self._calculate_weighted_average(self.calibration_data_left)
            avg_right_fist = self._calculate_weighted_average(self.calibration_data_right)
            self.lefthand.calibrationopose = avg_left_fist
            self.righthand.calibrationopose = avg_right_fist
        else:
            print(f"\n{Fore.RED}【标定失败】O型手势数据采集失败{Fore.RESET}\n")
            self.calibration_in_progress = False
            return False
        
        # ===== 保存标定数据 =====
        self._save_to_tmp()
        print(f"\n{Fore.GREEN}{'='*50}{Fore.RESET}")
        print(f"{Fore.GREEN}【标定完成】三个姿势数据已保存{Fore.RESET}")
        print(f"{Fore.GREEN}{'='*50}{Fore.RESET}\n")
        
        self.calibration_in_progress = False
        self.righthand.initialize_mapper()
        self.lefthand.initialize_mapper()
        return True

    def _save_to_tmp(self):
        """
        保存标定数据到临时文件 (JSON格式，与ROS2一致)
        - jointangleoriginal: 五指张开 (对应电机255)
        - jointanglefist: 握拳 (对应电机0)
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "jointangleoriginal_r": self.righthand.calibrationoriginal,
            "jointangleoriginal_l": self.lefthand.calibrationoriginal,
            "jointanglefist_r": self.righthand.calibrationfistpose,
            "jointanglefist_l": self.lefthand.calibrationfistpose,
            "jointangleopose_r": self.righthand.calibrationopose,
            "jointangleopose_l": self.lefthand.calibrationopose
        }

        try:
            TMP_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            if TMP_FILE_PATH.exists():
                content = TMP_FILE_PATH.read_text()
                historydata = json.loads(content)
                # 若左手未连接，标定内容无需存储
                if self.force_reader_left.handtype != 'Left':
                    data["jointangleoriginal_l"] = historydata["jointangleoriginal_l"]
                    data["jointanglefist_l"] = historydata["jointanglefist_l"]
                    data["jointangleopose_l"] = historydata["jointangleopose_l"]
                # 若右手未连接，标定内容无需存储
                if self.force_reader_right.handtype != 'Right':
                    data["jointangleoriginal_r"] = historydata["jointangleoriginal_r"]
                    data["jointanglefist_r"] = historydata["jointanglefist_r"]
                    data["jointangleopose_r"] = historydata["jointangleopose_r"]
            json_str = json.dumps(data, indent=2)
            TMP_FILE_PATH.write_text(json_str)
            self.node.get_logger().info("标定数据保存成功")
            return True
        except Exception as e:
            self.node.get_logger().erroror(f"保存失败: {e}")
            return False

    def _load_from_tmp(self):
        """
        从临时文件读取数据 (JSON格式，与ROS2一致)
        """
        if not TMP_FILE_PATH.exists():
            self.node.get_logger().warn("标定缓存文件不存在")
            return False
        
        try:
            content = TMP_FILE_PATH.read_text()
            data = json.loads(content)
        except Exception as e:
            self.node.get_logger().erroror(f"读取标定数据失败: {e}")
            return False

        # 检查时间戳
        if 'timestamp' not in data or not data['timestamp']:
            self.node.get_logger().warn("无效的时间戳...")
            return False

        # 检查是否超过30天
        try:
            saved_time = datetime.fromisoformat(data['timestamp'])
            current_time = datetime.now()
            time_diff = current_time - saved_time
            if time_diff > timedelta(days=30):
                self.node.get_logger().warn("标定数据已超过30天有效期，建议重新标定...")
        except:
            pass

        # 加载五指张开数据 (255)
        self.righthand.calibrationoriginal = data.get('jointangleoriginal_r')
        self.lefthand.calibrationoriginal = data.get('jointangleoriginal_l')
        
        # 加载握拳数据 (0)
        if data.get('jointanglefist_r'):
            self.righthand.calibrationfistpose = data['jointanglefist_r']
        if data.get('jointanglefist_l'):
            self.lefthand.calibrationfistpose = data['jointanglefist_l']
        
        # 加载O型手势数据
        if data.get('jointangleopose_r'):
            self.righthand.calibrationopose = data['jointangleopose_r']
        if data.get('jointangleopose_l'):
            self.lefthand.calibrationopose = data['jointangleopose_l']
        self.node.get_logger().info("标定数据加载成功")
        return True

    def process(self):
        """主处理函数"""
        # 初始化串口连接
        self.linkerforce_init()
        # 执行标定（如果需要）
        if self.calibration == "auto_calibrate":
            if not self.run_calibration():
                self.node.get_logger().error("标定失败，退出程序")
                return
            self.calibration = -1
        self.node.create_timer(1.0/30, self.process_callback)  # 120Hz
        rclpy.spin(self.node)
