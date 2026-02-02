import cv2
import mediapipe as mp
import socket
import json
import numpy as np
import pyrealsense2 as rs

# ================= 配置 =================
DESTINATIONS = [("127.0.0.1", 5006), ("127.0.0.1", 5007)]

def main():
    print(f"📷 启动最终修正版视觉源 (物理右手 + 镜像显示)...")
    
    # 1. RealSense 60FPS
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 60)
    pipeline.start(config)

    # 2. MediaPipe Lite (速度最快)
    mp_holistic = mp.solutions.holistic
    holistic = mp_holistic.Holistic(
        model_complexity=0, 
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame: continue
            
            # A. 镜像翻转 (保持照镜子体验)
            image = np.asanyarray(color_frame.get_data())
            image = cv2.flip(image, 1) 
            
            image.flags.writeable = False
            results = holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            image.flags.writeable = True
            
            packet = {}
            
            # --- B. 核心修改：提取【MP左臂】数据来对应【物理右手】 ---
            # 在镜像画面中，你的物理右手位于屏幕右侧，
            # 对 MediaPipe 来说，那是“画面中人的左手”。
            # 左肩(11), 左肘(13), 左腕(15)
            
            if results.pose_landmarks:
                lm = results.pose_landmarks.landmark
                
                # 提取 "Left" (其实是物理 Right)
                virtual_right_arm_data = [
                    [lm[11].x, lm[11].y, lm[11].z], # 肩
                    [lm[13].x, lm[13].y, lm[13].z], # 肘
                    [lm[15].x, lm[15].y, lm[15].z]  # 腕
                ]
                
                # 🔥 伪装成 right_arm 发送
                # 这样 03_arm_ik 脚本接收到后，会以为这是右手数据，直接驱动右臂
                # 因为向量的方向（右移、上抬、前伸）在镜像世界里是一致的，
                # 我们上一轮推导的矩阵 R_cam2robot 依然适用！
                packet["body_pose"] = {
                    "right_arm": virtual_right_arm_data 
                }
                
                # 画骨架
                mp.solutions.drawing_utils.draw_landmarks(
                    image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)

            # --- C. 核心修改：提取【MP左手】数据 ---
            # 同样原理，镜像后的物理右手，看起来是左手
            
            if results.left_hand_landmarks:
                kp = []
                for lm in results.left_hand_landmarks.landmark:
                    kp.append([lm.x, lm.y, lm.z])
                packet["hand_keypoints_21"] = kp
                
                mp.solutions.drawing_utils.draw_landmarks(
                    image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
            
            # --- 发送 ---
            if "body_pose" in packet:
                data_str = json.dumps(packet).encode()
                for dest in DESTINATIONS:
                    sock.sendto(data_str, dest)

            cv2.imshow('Physical Right Hand Control', image)
            if cv2.waitKey(1) & 0xFF == 27: break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()