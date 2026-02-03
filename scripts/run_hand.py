import sys
import os
import time
import numpy as np

# 路径黑魔法
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.robot.hand_driver import MockHandDriver, RealHandDriver

if __name__ == "__main__":
    print("🖐️ Starting Hand Driver Test...")
    
    # 指向配置文件
    config_path = os.path.join(os.path.dirname(__file__), "../config/hand_config.yaml")
    
    # 切换驱动模式：调试时用 Mock，上真机改用 Real
    driver = MockHandDriver() 
    # driver = RealHandDriver(config_path)
    
    try:
        while True:
            # 模拟一个“握拳-张开”的测试动作
            # 0.0 = 张开, 1.5 = 握拳
            test_cmd = np.sin(time.time()) * 0.7 + 0.7 
            
            # 假设我们有4根手指
            cmd = {'index': test_cmd, 'middle': test_cmd, 'ring': test_cmd, 'thumb': test_cmd}
            
            driver.send_hand_cmd(cmd)
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n🛑 Hand Test Stopped.")