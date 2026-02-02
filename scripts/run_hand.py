import socket
import json
import numpy as np
import sys
import os

# 路径修复
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(PROJECT_ROOT)

from src.core.hand_retargeting import VectorHandController

# 配置
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config/hand_config.yaml")
SERVER_ADDR = ("127.0.0.1", 6000)
LISTEN_PORT = 5006
MIRROR_LEFT_TO_RIGHT = True

def main():
    # 初始化控制器
    controller = VectorHandController(CONFIG_PATH, PROJECT_ROOT)
    
    # 网络
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", LISTEN_PORT))
    sock.setblocking(False)
    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"🖐️ 等待手部数据 (Port {LISTEN_PORT})...")
    
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            # 解析数据
            kp = np.array(json.loads(data.decode())["hand_keypoints_21"])
            
            # 镜像处理 (如果操作者用左手控制右手)
            if MIRROR_LEFT_TO_RIGHT: 
                kp[:, 0] = -kp[:, 0]
            
            # 调用核心算法
            full_joints = controller.process(kp)
            
            # 发送结果
            packet = {"type": "hand", "joints": full_joints}
            out_sock.sendto(json.dumps(packet).encode(), SERVER_ADDR)
            
        except BlockingIOError:
            pass
        except Exception as e:
            # print(f"Error: {e}")
            pass

if __name__ == "__main__":
    main()