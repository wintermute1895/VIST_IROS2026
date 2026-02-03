import cv2
import socket
import json
import time
import numpy as np
# 引用核心感知库 (提示队友去完善 detector.py)
from src.perception.detector import ObjectTracker

class VisionNode:
    """
    视觉感知节点
    职责：
    1. 读取摄像头图像
    2. 调用算法识别 ArUco/孔位
    3. 通过 UDP 发送坐标给控制节点
    """
    def __init__(self, camera_id=0, udp_ip="127.0.0.1", udp_port=6000):
        # TODO: 队友需要检查摄像头 ID 是否正确
        self.cap = cv2.VideoCapture(camera_id)
        
        # 初始化检测器
        self.tracker = ObjectTracker()
        
        # 初始化网络
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (udp_ip, udp_port)
        self.running = False
        print(f"[VisionNode] Initialized on Camera {camera_id}, Target UDP: {self.addr}")

    def step(self):
        """执行一帧的处理逻辑"""
        ret, frame = self.cap.read()
        if not ret:
            print("[Error] Failed to read frame")
            return None

        # 1. 调用识别算法 (核心任务)
        # TODO: 队友需要在 src/perception/detector.py 里实现 detect_hole
        hole_pose, found = self.tracker.detect_hole(frame)
        
        # 2. 如果找到了，发送数据
        if found:
            # 数据格式: [x, y, z, qx, qy, qz, qw]
            # 这里先发个假数据或转换后的数据
            data = {
                "timestamp": time.time(),
                "target_pose": hole_pose.tolist() if isinstance(hole_pose, np.ndarray) else hole_pose
            }
            msg = json.dumps(data).encode()
            self.sock.sendto(msg, self.addr)
            
            # 画图示意
            cv2.putText(frame, "Target Found", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return frame

    def run(self):
        """独立运行时的循环"""
        self.running = True
        print("[VisionNode] Loop Started. Press 'ESC' to quit.")
        
        while self.running:
            frame = self.step()
            
            if frame is not None:
                cv2.imshow("VIST Vision Debug", frame)
            
            if cv2.waitKey(1) == 27: # ESC
                break
        
        self.cap.release()
        cv2.destroyAllWindows()