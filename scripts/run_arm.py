import sys
import os

# 路径黑魔法
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.arm_node import ArmNode

if __name__ == "__main__":
    print("🦾 Starting Arm Control Node...")
    
    # 指向配置文件
    config_path = os.path.join(os.path.dirname(__file__), "../config/hardware.yaml")
    
    node = ArmNode(config_path)
    node.run()