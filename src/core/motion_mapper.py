import numpy as np
from scipy.spatial.transform import Rotation as R

class ArmMotionMapper:
    """
    负责将人类手臂的 3D 关键点 映射为 机器人的末端位姿 (Cartesian Pose)
    使用经典的 '三向量法' (Three-Vector Method)
    """
    def __init__(self, robot_upper_len, robot_fore_len):
        self.L_upper = robot_upper_len
        self.L_fore = robot_fore_len
        
        # 定义相机到机器人的旋转矩阵 (这是你的 R_cam2robot)
        # 建议从 config 传入，这里简化写
        self.R_align = np.array([[0,0,-1], [-1,0,0], [0,-1,0]]) 

    def human_to_robot_cartesian(self, shoulder, elbow, wrist, palm):
        """
        输入: 人类关键点 (World Frame)
        输出: 机器人目标 (Elbow Pos, Wrist Pos, Wrist Rot)
        """
        # 1. 计算人类向量
        v_upper_h = elbow - shoulder
        v_fore_h = wrist - elbow
        v_palm_h = palm - wrist
        
        # 2. 旋转对齐 (Align)
        v_upper = self.R_align @ v_upper_h
        v_fore = self.R_align @ v_fore_h
        v_palm = self.R_align @ v_palm_h
        
        # 3. 归一化方向 (Direction)
        d_upper = v_upper / (np.linalg.norm(v_upper) + 1e-6)
        d_fore = v_fore / (np.linalg.norm(v_fore) + 1e-6)
        
        # 4. 映射长度 (Scaling) - 这里的 shoulder 是机器人坐标系下的原点(假设)
        # 实际使用时，通常机器人shoulder是固定在 (0,0,height) 的
        robot_shoulder = np.array([0, 0, 0]) 
        
        target_elbow = robot_shoulder + d_upper * self.L_upper
        target_wrist = target_elbow + d_fore * self.L_fore
        
        # 5. 计算姿态 (Orientation)
        # 构建旋转矩阵: X=法线, Y=掌心, Z=前臂 (根据你的定义调整)
        z_axis = d_fore
        y_axis = v_palm / (np.linalg.norm(v_palm) + 1e-6)
        x_axis = np.cross(y_axis, z_axis)
        # 重新正交化 Y
        y_axis = np.cross(z_axis, x_axis)
        
        rot_matrix = np.stack([x_axis, y_axis, z_axis], axis=1)
        
        return target_elbow, target_wrist, rot_matrix