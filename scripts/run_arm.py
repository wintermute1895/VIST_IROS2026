import pinocchio as pin
import pink
from pink.tasks import FrameTask, PostureTask
import numpy as np
import socket
import json
import time
import sys
import os

# ================= 路径与引用修复 =================
# 1. 获取当前脚本所在目录 (.../VIST/scripts)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 2. 获取项目根目录 (.../VIST)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
# 3. 将根目录加入 Python 搜索路径，这样才能 import src
sys.path.append(PROJECT_ROOT)

# 4. 引入模块化后的工具类
from src.utils.filter import SecondOrderFilter
# 5. 引入你的 IROS 核心创新算法
from src.core.estimator import IntentAdaptiveEstimator
# ================================================

# ================= 配置 =================
# 机器人关节与Frame名称
ROBOT_SHOULDER_FRAME = "Right_Shoulder_Pitch_Link" 
ROBOT_ELBOW_FRAME    = "Right_Elbow_Pitch_Link"    
ROBOT_WRIST_FRAME    = "hand_base_link"            
ELBOW_JOINT_NAME     = "Right_Elbow_Pitch_Joint"
FINGER_KEYWORDS = ["index", "middle", "ring", "pinky", "thumb"]

# 配置文件路径 (使用 PROJECT_ROOT 拼接)
FULL_ROBOT_URDF = os.path.join(PROJECT_ROOT, "config/combined_robot/robot.urdf")
FULL_ROBOT_PKG = os.path.join(PROJECT_ROOT, "config/combined_robot")

# 网络配置
SERVER_ADDR = ("127.0.0.1", 6000) # 发送给可视化服务器
MP_PORT = 5007                    # 接收 MediaPipe 数据

# 控制参数
DT = 0.01
DAMPING = 1e-2 
MAX_JOINT_VELOCITY = 1.0 

class FinalArmController:
    def __init__(self):
        print("🛡️ 启动 VIST 核心控制器 (Intent-Adaptive Enabled)...")
        
        # 1. 初始化机器人模型
        self.robot = pin.RobotWrapper.BuildFromURDF(FULL_ROBOT_URDF, package_dirs=[FULL_ROBOT_PKG])
        self.model, self.data = self.robot.model, self.robot.data
        self.q = pin.neutral(self.model).copy()
        
        # 预设肘部角度避免奇异
        if self.model.existJointName(ELBOW_JOINT_NAME):
            self.q[self.model.joints[self.model.getJointId(ELBOW_JOINT_NAME)].idx_q] = 1.5

        # 2. 初始化 IK 求解器 (Pink)
        self.configuration = pink.Configuration(self.model, self.data, self.q)
        
        # 3. 定义任务 (Tasks)
        self.task_wrist = FrameTask(ROBOT_WRIST_FRAME, position_cost=5.0, orientation_cost=0.0) 
        self.task_wrist.gain = 5.0
        
        self.task_elbow = FrameTask(ROBOT_ELBOW_FRAME, position_cost=2.0, orientation_cost=0.0)
        self.task_elbow.gain = 3.0
        
        self.task_posture = PostureTask(cost=1e-3) 
        self.task_posture.set_target(self.q)
        self.task_posture.gain = 1.0
        
        self.tasks = [self.task_wrist, self.task_elbow, self.task_posture]
        
        # 4. 初始化滤波器
        # 肩部和肘部使用普通二阶低通滤波
        self.filter_shoulder = SecondOrderFilter(fps=int(1/DT), cutoff=2.0)
        self.filter_elbow = SecondOrderFilter(fps=int(1/DT), cutoff=2.0)
        
        # 🔥 手腕使用自适应估计器 (核心创新)
        self.estimator = IntentAdaptiveEstimator(dt=DT)
        
        # 用于计算意图的速度缓存
        self.last_raw_wrist = None
        
        # 5. 初始化网络
        self.mp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mp_sock.bind(("127.0.0.1", MP_PORT))
        self.mp_sock.setblocking(False)
        self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 6. 测量机器人几何尺寸
        self._measure_robot_geometry()
        self.warmup_counter = 0

    def _measure_robot_geometry(self):
        """测量上臂和前臂长度，用于重构目标点"""
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)
        p_s = self.data.oMf[self.model.getFrameId(ROBOT_SHOULDER_FRAME)].translation
        p_e = self.data.oMf[self.model.getFrameId(ROBOT_ELBOW_FRAME)].translation
        p_w = self.data.oMf[self.model.getFrameId(ROBOT_WRIST_FRAME)].translation
        self.robot_upper_arm_len = np.linalg.norm(p_e - p_s)
        self.robot_fore_arm_len = np.linalg.norm(p_w - p_e)
        self.robot_shoulder_pos_world = p_s 
        print(f"📏 机器人几何测量完成: 上臂={self.robot_upper_arm_len:.3f}m, 前臂={self.robot_fore_arm_len:.3f}m")

    def run(self):
        print("💪 等待 MediaPipe 右臂数据...")
        while True:
            try:
                # 1. 接收数据
                data, _ = self.mp_sock.recvfrom(65535)
                packet = json.loads(data.decode())
                
                if "body_pose" not in packet or "right_arm" not in packet["body_pose"]: 
                    continue
                
                # arm_data shape: (3, 3) -> [shoulder_xyz, elbow_xyz, wrist_xyz]
                arm_data = np.array(packet["body_pose"]["right_arm"])
                raw_wrist = arm_data[2]
                
                # 2. 预热 (跳过前几帧不稳定数据)
                if self.warmup_counter < 30:
                    self.warmup_counter += 1
                    self.last_raw_wrist = raw_wrist
                    continue

                # ================= 🔥 意图识别与滤波核心逻辑 =================
                
                # A. 计算手腕瞬时速度 (用于判断意图)
                if self.last_raw_wrist is None: self.last_raw_wrist = raw_wrist
                wrist_vel = np.linalg.norm(raw_wrist - self.last_raw_wrist) / DT
                self.last_raw_wrist = raw_wrist
                
                # B. 映射意图分数 (0.0=快速移动, 1.0=精细操作)
                # 逻辑：速度越慢，分越高。这里的参数 5.0 可调
                intent_score = 1.0 / (1.0 + 5.0 * wrist_vel)
                
                # C. 执行滤波
                # 肩肘用普通滤波
                f_s = self.filter_shoulder.apply(arm_data[0])
                f_e = self.filter_elbow.apply(arm_data[1])
                
                # 手腕用自适应滤波 (传入意图分)
                f_w = self.estimator.update(raw_wrist, intent_score)
                
                # ==========================================================

                # 3. 向量重构 (Human -> Robot Mapping)
                vec_upper = f_e - f_s 
                vec_fore  = f_w - f_e 
                
                if np.linalg.norm(vec_upper) > 0: vec_upper /= np.linalg.norm(vec_upper)
                if np.linalg.norm(vec_fore) > 0:  vec_fore /= np.linalg.norm(vec_fore)
                
                # 坐标系旋转矩阵 (根据你的需求保留)
                # Cam X (人向右) -> Robot -Y (机向右)
                # Cam Y (人向下) -> Robot -Z (机向下)
                # Cam Z (人向后) -> Robot -X (机向后)
                R_cam2robot = np.array([
                    [ 0,  0, -1],
                    [-1,  0,  0],
                    [ 0, -1,  0]
                ])
                
                vec_upper_rob = R_cam2robot @ vec_upper
                vec_fore_rob  = R_cam2robot @ vec_fore
                
                # 计算机器人任务空间目标点
                target_elbow_pos = self.robot_shoulder_pos_world + vec_upper_rob * self.robot_upper_arm_len
                target_wrist_pos = target_elbow_pos + vec_fore_rob * self.robot_fore_arm_len
                
                # 4. 更新 IK 任务目标
                tf_e = self.configuration.get_transform_frame_to_world(ROBOT_ELBOW_FRAME).copy()
                tf_e.translation = target_elbow_pos
                self.task_elbow.set_target(tf_e)
                
                tf_w = self.configuration.get_transform_frame_to_world(ROBOT_WRIST_FRAME).copy()
                tf_w.translation = target_wrist_pos
                self.task_wrist.set_target(tf_w)
                
                # 5. 求解 IK 并积分
                vel = pink.solve_ik(self.configuration, self.tasks, DT, solver="quadprog", damping=DAMPING)
                vel = np.clip(vel, -MAX_JOINT_VELOCITY, MAX_JOINT_VELOCITY)
                self.configuration.integrate_inplace(vel, DT)
                self.q = self.configuration.q
                
                # 6. 打包发送给可视化端
                joints_dict = {}
                for name in self.model.names:
                    if name == "universe": continue
                    # 过滤手指关节，只发送手臂关节
                    is_finger = False
                    for kw in FINGER_KEYWORDS:
                        if kw in name: 
                            is_finger = True; break
                    if is_finger: continue
                    
                    joint_id = self.model.getJointId(name)
                    if self.model.joints[joint_id].nq == 1:
                        joints_dict[name] = float(self.q[self.model.joints[joint_id].idx_q])
                
                # 调试可视化包
                viz_packet = {
                    "s": self.robot_shoulder_pos_world.tolist(),
                    "e": target_elbow_pos.tolist(),
                    "w": target_wrist_pos.tolist(),
                    "intent": float(intent_score) # 发送意图分，方便前端可视化调试
                }
                
                packet = {
                    "type": "arm", 
                    "joints": joints_dict,
                    "debug_viz": viz_packet
                }
                self.out_sock.sendto(json.dumps(packet).encode(), SERVER_ADDR)
                
                time.sleep(DT)
                
            except BlockingIOError:
                pass
            except Exception as e:
                print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    FinalArmController().run()