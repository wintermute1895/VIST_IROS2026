import cv2
import numpy as np
import time

def collect_data():
    """
    Step 1: 数据采集
    提示队友：
    1. 移动机器人到 N 个位置
    2. 记录 [Robot_Base_to_End] (从机械臂读)
    3. 记录 [Camera_to_Target] (从视觉读)
    """
    print("按 's' 保存一组数据，按 'q' 结束采集并开始计算...")
    # TODO: 实现采集循环
    pass

def solve_calibration(R_gripper2base, t_gripper2base, R_target2cam, t_target2cam):
    """
    Step 2: 求解手眼标定矩阵
    """
    print("开始求解标定矩阵...")
    
    # 核心函数: cv2.calibrateHandEye
    # method=cv2.CALIB_HAND_EYE_TSAI
    
    # R_cam2base, t_cam2base = ...
    
    return np.eye(3), np.zeros(3) # 占位符

if __name__ == "__main__":
    print("🔧 System Calibration Tool")
    # TODO: 队友来填充这里的逻辑