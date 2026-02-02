import pinocchio as pin
import pink
from pink.tasks import FrameTask, PostureTask
import numpy as np
import socket
import json
import time
import sys
import os
from scipy.signal import butter, lfilter


# ================= 路径修复 =================
# 获取当前脚本所在目录 (scripts/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (VIST/)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
# 将根目录加入 Python 搜索路径，这样才能 import src
sys.path.append(PROJECT_ROOT)
# ===========================================

# ================= 配置 =================
# 确保名字正确
ROBOT_SHOULDER_FRAME = "Right_Shoulder_Pitch_Link" 
ROBOT_ELBOW_FRAME    = "Right_Elbow_Pitch_Link"    
ROBOT_WRIST_FRAME    = "hand_base_link"            
ELBOW_JOINT_NAME     = "Right_Elbow_Pitch_Joint"
FINGER_KEYWORDS = ["index", "middle", "ring", "pinky", "thumb"]

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_ROBOT_URDF = os.path.join(CURRENT_DIR, "config/combined_robot/robot.urdf")
FULL_ROBOT_PKG = os.path.join(CURRENT_DIR, "config/combined_robot")
SERVER_ADDR = ("127.0.0.1", 6000)

DT = 0.01
DAMPING = 1e-2 
MAX_JOINT_VELOCITY = 1.0 

class SecondOrderFilter:
    def __init__(self, fps=60, cutoff=2.0): 
        self.b, self.a = butter(2, cutoff / (fps / 2), btype='low')
        self.zi = None
        self.initialized = False
    def apply(self, value):
        if self.zi is None:
            self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, value.shape[0]))
        if not self.initialized:
            self.zi = lfilter(self.b, self.a, value[None, :], axis=0, zi=self.zi * 0 + value)[1]
            self.initialized = True
            return value
        filtered, self.zi = lfilter(self.b, self.a, value[None, :], axis=0, zi=self.zi)
        return filtered[0]

class FinalArmController:
    def __init__(self):
        print("🛡️ 启动最终版手臂控制器 (修正矩阵 + 只控右臂)...")
        
        self.robot = pin.RobotWrapper.BuildFromURDF(FULL_ROBOT_URDF, package_dirs=[FULL_ROBOT_PKG])
        self.model, self.data = self.robot.model, self.robot.data
        self.q = pin.neutral(self.model).copy()
        
        if self.model.existJointName(ELBOW_JOINT_NAME):
            self.q[self.model.joints[self.model.getJointId(ELBOW_JOINT_NAME)].idx_q] = 1.5

        self.configuration = pink.Configuration(self.model, self.data, self.q)
        
        self.task_wrist = FrameTask(ROBOT_WRIST_FRAME, position_cost=5.0, orientation_cost=0.0) 
        self.task_wrist.gain = 5.0
        self.task_elbow = FrameTask(ROBOT_ELBOW_FRAME, position_cost=2.0, orientation_cost=0.0)
        self.task_elbow.gain = 3.0
        self.task_posture = PostureTask(cost=1e-3) 
        self.task_posture.set_target(self.q)
        self.task_posture.gain = 1.0
        self.tasks = [self.task_wrist, self.task_elbow, self.task_posture]
        
        self.filter_shoulder = SecondOrderFilter()
        self.filter_elbow = SecondOrderFilter()
        self.filter_wrist = SecondOrderFilter()
        
        self.mp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mp_sock.bind(("127.0.0.1", 5007))
        self.mp_sock.setblocking(False)
        self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self._measure_robot_geometry()
        self.warmup_counter = 0

    def _measure_robot_geometry(self):
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)
        p_s = self.data.oMf[self.model.getFrameId(ROBOT_SHOULDER_FRAME)].translation
        p_e = self.data.oMf[self.model.getFrameId(ROBOT_ELBOW_FRAME)].translation
        p_w = self.data.oMf[self.model.getFrameId(ROBOT_WRIST_FRAME)].translation
        self.robot_upper_arm_len = np.linalg.norm(p_e - p_s)
        self.robot_fore_arm_len = np.linalg.norm(p_w - p_e)
        self.robot_shoulder_pos_world = p_s 

    def run(self):
        print("💪 等待 MediaPipe 右臂数据...")
        while True:
            try:
                data, _ = self.mp_sock.recvfrom(65535)
                packet = json.loads(data.decode())
                
                # 只接收 right_arm 数据
                if "body_pose" not in packet or "right_arm" not in packet["body_pose"]: 
                    continue
                
                arm_data = np.array(packet["body_pose"]["right_arm"])
                
                f_s = self.filter_shoulder.apply(arm_data[0])
                f_e = self.filter_elbow.apply(arm_data[1])
                f_w = self.filter_wrist.apply(arm_data[2])
                
                if self.warmup_counter < 30:
                    self.warmup_counter += 1
                    continue

                # 向量计算
                vec_upper = f_e - f_s 
                vec_fore  = f_w - f_e 
                
                if np.linalg.norm(vec_upper) > 0: vec_upper /= np.linalg.norm(vec_upper)
                if np.linalg.norm(vec_fore) > 0:  vec_fore /= np.linalg.norm(vec_fore)
                
                # ================= 🔴 修正后的矩阵 =================
                # Cam X (人向右) -> Robot -Y (机向右)
                # Cam Y (人向下) -> Robot -Z (机向下)
                # Cam Z (人向后) -> Robot -X (机向后)
                R_cam2robot = np.array([
                    [ 0,  0, -1],  # Cam Z -> Robot -X
                    [-1,  0,  0],  # Cam X -> Robot -Y
                    [ 0, -1,  0]   # Cam Y -> Robot -Z
                ])
                # ==================================================
                
                vec_upper_rob = R_cam2robot @ vec_upper
                vec_fore_rob  = R_cam2robot @ vec_fore
                
                target_elbow_pos = self.robot_shoulder_pos_world + vec_upper_rob * self.robot_upper_arm_len
                target_wrist_pos = target_elbow_pos + vec_fore_rob * self.robot_fore_arm_len
                
                # 更新任务
                tf_e = self.configuration.get_transform_frame_to_world(ROBOT_ELBOW_FRAME).copy()
                tf_e.translation = target_elbow_pos
                self.task_elbow.set_target(tf_e)
                
                tf_w = self.configuration.get_transform_frame_to_world(ROBOT_WRIST_FRAME).copy()
                tf_w.translation = target_wrist_pos
                self.task_wrist.set_target(tf_w)
                
                # IK 求解
                vel = pink.solve_ik(self.configuration, self.tasks, DT, solver="quadprog", damping=DAMPING)
                vel = np.clip(vel, -MAX_JOINT_VELOCITY, MAX_JOINT_VELOCITY)
                self.configuration.integrate_inplace(vel, DT)
                self.q = self.configuration.q
                
                # 过滤手指
                joints_dict = {}
                for name in self.model.names:
                    if name == "universe": continue
                    is_finger = False
                    for kw in FINGER_KEYWORDS:
                        if kw in name: 
                            is_finger = True; break
                    if is_finger: continue
                    
                    joint_id = self.model.getJointId(name)
                    if self.model.joints[joint_id].nq == 1:
                        joints_dict[name] = float(self.q[self.model.joints[joint_id].idx_q])
                
                # 可视化包
                viz_packet = {
                    "s": self.robot_shoulder_pos_world.tolist(),
                    "e": target_elbow_pos.tolist(),
                    "w": target_wrist_pos.tolist()
                }
                
                packet = {
                    "type": "arm", 
                    "joints": joints_dict,
                    "debug_viz": viz_packet
                }
                self.out_sock.sendto(json.dumps(packet).encode(), SERVER_ADDR)
                
                time.sleep(DT)
                
            except Exception as e:
                pass

if __name__ == "__main__":
    FinalArmController().run()