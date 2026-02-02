# src/perception/detector.py

import cv2
import mediapipe as mp
import numpy as np
from src.utils.transformations import to_homogeneous

class HumanTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )

    def detect(self, image):
        """
        使用 MediaPipe 检测手部
        返回: 关键点 3D 坐标 (相对于相机系)
        注意: MediaPipe 默认输出的是归一化坐标，需要转换
        """
        results = self.hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        if results.multi_hand_landmarks:
            # 这里简化处理，取腕关节(Wrist, index 0)作为手的粗略位置
            # 实际上你需要结合 Dex-Retargeting 获取更精细的位姿
            landmark = results.multi_hand_landmarks[0].landmark[0] 
            
            # 简单的投影 (假设深度固定或由RealSense提供，这里演示用纯视觉估计)
            # 这是一个极度简化的 Mock 数据，实际项目需要 PNP 解算或深度图
            h, w, _ = image.shape
            x = (landmark.x - 0.5) * 0.5 # 映射到米
            y = (landmark.y - 0.5) * 0.5
            z = 0.5 # 假设手离相机 0.5米
            
            # 返回 [x, y, z, qx, qy, qz, qw]
            return np.array([x, y, z, 0, 0, 0, 1]), True
            
        return None, False

class ObjectTracker:
    def __init__(self, intrinsic_matrix, dist_coeffs):
        self.K = intrinsic_matrix
        self.D = dist_coeffs
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()

    def detect_hole(self, image):
        """
        检测贴在孔附近的 ArUco Marker
        返回: 孔的 6D 位姿 (相对于相机系) -> z_virtual
        """
        corners, ids, rejected = cv2.aruco.detectMarkers(
            image, self.aruco_dict, parameters=self.parameters
        )
        
        if ids is not None and len(ids) > 0:
            # 估计姿态
            # markerLength 0.05m
            rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners[0], 0.05, self.K, self.D
            )
            
            # 将旋转向量 rvec 转为 四元数
            # ... (需要 cv2.Rodrigues 转矩阵再转四元数，这里略写)
            # 假设我们得到了 pose
            pose = np.concatenate([tvec[0][0], [0, 0, 0, 1]]) 
            return pose, True
            
        return None, False