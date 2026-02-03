# src/nodes/vision_node.py
import cv2
import socket
# 引用你的 core
from src.perception.detector import ObjectTracker 

class VisionNode:
    def __init__(self, camera_id=0, udp_ip="127.0.0.1", udp_port=6000):
        self.cap = cv2.VideoCapture(camera_id)
        self.tracker = ObjectTracker()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (udp_ip, udp_port)
        self.running = False

    def step(self):
        """执行一帧的逻辑"""
        ret, frame = self.cap.read()
        if not ret: return
        
        # 核心识别逻辑
        res = self.tracker.process(frame)
        
        # 发送数据
        self.sock.sendto(str(res).encode(), self.addr)
        
        return frame

    def run(self):
        """独立运行时的死循环"""
        self.running = True
        while self.running:
            frame = self.step()
            cv2.imshow("Debug", frame)
            if cv2.waitKey(1) == 27: break
        self.cap.release()