# src/perception/camera.py

import cv2
import numpy as np

class CameraStream:
    def __init__(self, config):
        self.device_id = config['camera']['device_id']
        self.width = config['camera']['width']
        self.height = config['camera']['height']
        
        # 初始化摄像头
        self.cap = cv2.VideoCapture(self.device_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # 内参矩阵 (Intrinsics) - 暂时用近似值，以后可以标定
        # fx, fy, cx, cy
        self.K = np.array([
            [600, 0, self.width/2],
            [0, 600, self.height/2],
            [0, 0, 1]
        ])
        self.dist_coeffs = np.zeros(5) # 假设无畸变

    def read(self):
        """返回 (ret, rgb_image, depth_image)"""
        ret, frame = self.cap.read()
        # 如果是普通WebCam，Depth就是None
        return ret, frame, None

    def close(self):
        self.cap.release()