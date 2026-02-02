# scripts/test_vision.py
import cv2
import yaml
from src.perception.camera import CameraStream
from src.perception.detector import HumanTracker, ObjectTracker

# 读取配置
with open("config/hardware.yaml", "r") as f:
    config = yaml.safe_load(f)

cam = CameraStream(config)
human_tracker = HumanTracker()
obj_tracker = ObjectTracker(cam.K, cam.dist_coeffs)

while True:
    ret, frame, _ = cam.read()
    if not ret: break

    # 1. 检测人手 (噪声源)
    hand_pose, has_hand = human_tracker.detect(frame)
    if has_hand:
        print(f"Hand (Human Input): {hand_pose[:3]}")
        # 画个圈表示检测到了
        cv2.circle(frame, (320, 240), 10, (0, 255, 0), -1)

    # 2. 检测孔位 (虚拟观测源)
    hole_pose, has_hole = obj_tracker.detect_hole(frame)
    if has_hole:
        print(f"Hole (Virtual Fixture): {hole_pose[:3]}")

    cv2.imshow("VIST Perception Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.close()
cv2.destroyAllWindows()