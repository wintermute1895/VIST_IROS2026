import numpy as np
import cv2
import sys
import os

# 路径黑魔法
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.perception.detector import ObjectTracker

# ❌ 错误写法：直接在外面写逻辑
# obj_tracker = ObjectTracker()
# frame = cv2.imread("test.jpg")
# hole_pose, has_hole = obj_tracker.detect_hole(frame)  <-- 这里导致了报错

# ✅ 正确写法：封装进测试函数
def test_hole_detection_workflow():
    # 1. 准备数据
    tracker = ObjectTracker()
    
    # 创建一个假的黑白图像 (模拟相机帧)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 2. 运行功能
    # 这里我们只测试"代码不崩"，不指望它真的在黑图上检测出孔
    try:
        corners, found = tracker.detect_hole(fake_frame)
        print(f"Detection ran successfully. Found: {found}")
    except Exception as e:
        pytest.fail(f"Detector crashed with error: {e}")

    # 3. 如果你想测试真的检测，需要生成带 ArUco 的图
    # 但作为单元测试，只要跑通流程不报错就算 Pass