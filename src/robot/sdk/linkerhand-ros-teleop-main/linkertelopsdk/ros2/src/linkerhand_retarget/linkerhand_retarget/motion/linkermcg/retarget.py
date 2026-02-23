
import time
import rospy
from sensor_msgs.msg import JointState
from datetime import datetime


from linkerhand.linkermcgcore import linkermcgScoketUdp,linkermcgData
from linkerhand.handcore import HandCore
from linkerhand.constants import RobotName, ROBOT_LEN_MAP



class Retarget():
    def __init__(self,node, ip, port, lefthand: RobotName, righthand: RobotName, handcore: HandCore,
                lefthandpubprint: bool, righthandpubprint: bool):
        self.node = node
        self.udp_ip = ip
        self.udp_port = port
        self.lefthandtype = lefthand
        self.righthandtype = righthand
        self.handcore = handcore
        self.runing = True
        self.lefthandpubprint = lefthandpubprint
        self.righthandpubprint = righthandpubprint
        
        # 根据右手类型初始化
        if self.righthandtype == RobotName.o7 \
            or self.righthandtype == RobotName.l7 \
            or self.righthandtype == RobotName.o7v1 \
            or self.righthandtype == RobotName.o7v3:
            from .hand.linkermcg_l7 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.o6:
            from .hand.linkermcg_o6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l6:
            from .hand.linkermcg_l6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        # elif self.righthandtype == RobotName.l25:
        #     from .hand.linkermcg_l25 import RightHand
        #     self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        # elif self.righthandtype == RobotName.t25:
        #     from .hand.linkermcg_t25 import RightHand
        #     self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l20:
            from .hand.linkermcg_l20 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l10v6 :
            from .hand.linkermcg_l10v6 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])        
        elif self.righthandtype == RobotName.l10 \
            or self.righthandtype == RobotName.l10v7 :
            from .hand.linkermcg_l10v7 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])
        elif self.righthandtype == RobotName.l21:
            from .hand.linkermcg_l21 import RightHand
            self.righthand = RightHand(handcore, length=ROBOT_LEN_MAP[righthand])

        # 根据LEFT手类型初始化
        if self.lefthandtype == RobotName.o7 \
            or self.lefthandtype == RobotName.l7 \
            or self.lefthandtype == RobotName.o7v1 \
            or self.lefthandtype == RobotName.o7v3:
            from .hand.linkermcg_l7 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.o6:
            from .hand.linkermcg_o6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l6:
            from .hand.linkermcg_l6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l25:
            from .hand.linkermcg_l25 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        # elif self.lefthandtype == RobotName.t25:
        #     from .hand.linkermcg_t25 import LeftHand
        #     self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l20:
            from .hand.linkermcg_l20 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l10v6 :
            from .hand.linkermcg_l10v6 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l10 \
            or self.lefthandtype == RobotName.l10v7 :
            from .hand.linkermcg_l10v7 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])
        elif self.lefthandtype == RobotName.l21:
            from .hand.linkermcg_l21 import LeftHand
            self.lefthand = LeftHand(handcore, length=ROBOT_LEN_MAP[lefthand])

        # ROS1 发布器
        self.publisher_r = rospy.Publisher('/cb_right_hand_control_cmd', JointState, queue_size=self.handcore.hand_numjoints_r)
        self.publisher_l = rospy.Publisher('/cb_left_hand_control_cmd', JointState, queue_size=self.handcore.hand_numjoints_l)
 
        # 创建ROS定时器，以固定频率处理数据
        # 参数1: period 周期(秒)
        # 参数2: callback 回调函数
        # 参数3: oneshot 是否只执行一次
        self.timer = rospy.Timer(rospy.Duration(1/60), self.process_callback)  # 120频率
        
        # 注册关闭回调
        rospy.on_shutdown(self.shutdown_callback)

        self.pubprintcount = 0
        self.udp_datacapture = None

    def initialize_udp(self):
        """初始化UDP连接"""
        self.udp_datacapture = linkermcgScoketUdp(
            host=self.udp_ip,
            port=self.udp_port)
        if self.udp_datacapture.udp_initial():
            rospy.loginfo("UDP连接初始化成功")
            self.running = True
        else:
            rospy.logerr("UDP连接初始化失败")
    
    def process_callback(self):
        if not self.running:
            return
    
        mocapdata = self.udp_datacapture.realmocapdata
        if not mocapdata.is_update:
            return
                    
        # 处理左右手原始数据
        self.lefthand.joint_update(mocapdata.jointangle_lHand)
        self.righthand.joint_update(mocapdata.jointangle_rHand)

        # 速度环节处理
        self.lefthand.speed_update()
        self.righthand.speed_update()

        # 调试打印
        if self.lefthandpubprint and self.pubprintcount % 50 == 0:
            rospy.loginfo(f"左手位置: {self.righthand.g_jointpositions}")
        if self.righthandpubprint and self.pubprintcount % 50 == 0:
            rospy.loginfo(f"右手位置: {self.righthand.g_jointpositions}")

        # 发布右手数据
        msg = JointState()
        msg.header.stamp = rospy.Time.now()
        msg.name = [f'joint{i + 1}' for i in range(len(self.righthand.g_jointpositions ))]
        msg.position = [float(num) for num in self.righthand.g_jointpositions ]
        msg.velocity = [float(num) for num in self.righthand.g_jointvelocity ]
        self.publisher_r.publish(msg)
 
        # 发布左手数据
        msg = JointState()
        msg.name = [f'joint{i + 1}' for i in range(len(self.lefthand.g_jointpositions ))]
        msg.position = [float(num) for num in self.lefthand.g_jointpositions ]
        msg.velocity = [float(num) for num in self.lefthand.g_jointvelocity ]
        self.publisher_l.publish(msg)
        self.pubprintcount += 1

    def process(self):
        """主处理函数"""
        self.initialize_udp()
        try:
            rospy.spin()  # 保持节点运行，等待回调
        except rospy.ROSInterruptException:
            pass

    def shutdown_callback(self):
        """ROS关闭时的回调"""
        self.running = False
        if self.udp_datacapture:
            self.udp_datacapture.udp_close()
        rospy.loginfo("节点已关闭")
