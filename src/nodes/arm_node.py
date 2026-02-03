import time
# 引用 core (大脑)
from src.core.estimator import IntentAdaptiveEstimator
from src.core.intent import IntentInference
# 引用 driver (手脚)
from src.robot.arm_driver import UdpArmDriver

class ArmNode:
    def __init__(self):
        # 1. 初始化所有组件
        self.driver = UdpArmDriver()
        self.estimator = IntentAdaptiveEstimator(dt=0.01)
        self.intent = IntentInference()

    def spin_once(self):
        # 2. 调度流程 (The Business Logic)
        
        # A. 听 (IO)
        q_curr = self.driver.get_state()
        
        # B. 想 (Core Logic)
        alpha = self.intent.compute_alpha(...)
        q_cmd = self.estimator.update(..., alpha)
        
        # C. 做 (IO)
        self.driver.send_command(q_cmd)

    def run(self):
        # 3. 负责循环和频率控制
        while True:
            self.spin_once()
            time.sleep(0.01)