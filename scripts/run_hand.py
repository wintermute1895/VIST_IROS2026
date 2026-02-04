import cv2
import mediapipe as mp
import numpy as np
import yaml
import time
from robot.hand_driver import HandDriver
from src.hand_retargeting import HandRetargeter

def main():
    # 1. 环境准备
    with open("configs/hand_config.yaml", 'r') as f:
        hw_cfg = yaml.safe_load(f)
    
    driver = HandDriver(
        mock_mode=hw_cfg['hand']['mock_mode'], 
        can_channel=hw_cfg['hand']['can_interface']
    )
    retargeter = HandRetargeter("configs/hand_retargeting_config.yaml")
    
    # 2. 视觉初始化
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    cap = cv2.VideoCapture(0)
    
    print("\n🚀 遥操作已启动！按 ESC 退出...")
    
    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success: break
            
            frame = cv2.flip(frame, 1) # 镜像处理
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(img_rgb)
            
            # 初始化 10 维指令列表
            cmd_10 = [0.0] * 10
            
            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    # 1. 提取 3D 坐标
                    points = np.array([[lm.x, lm.y, lm.z] for lm in hand_lms.landmark])
                    
                    # 2. 运行重定向算法 (得到弧度字典)
                    joint_map = retargeter.process(points)
                    
                    # 3. 协议转换 (字典 -> 10维列表)
                    mapping = hw_cfg['hand']['mapping']
                    scaling = hw_cfg['hand']['scaling_factor']
                    limits = hw_cfg['hand']['safety']
                    
                    for name, rad in joint_map.items():
                        if name in mapping:
                            idx, sign, offset = mapping[name]
                            # 计算逻辑: (弧度 * 方向 + 偏置) * 57.3
                            val = (rad * sign + offset) * scaling
                            # 限制在 0-180 度
                            val = max(limits['min_limit'], min(val, limits['max_limit']))
                            cmd_10[idx] = val
                    
                    # 绘制
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, hand_lms, mp_hands.HAND_CONNECTIONS)
            
            # 4. 发送给硬件 (即使检测不到手也持续发送，保持位置)
            driver.move(cmd_10)
            
            cv2.imshow('VIST Teleop', frame)
            if cv2.waitKey(1) & 0xFF == 27: break
            
    finally:
        driver.close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()