import multiprocessing
from src.nodes.vision_node import VisionNode
from src.nodes.arm_node import ArmNode # 假设你也重构了手臂

def launch_vision():
    # 可以在这里关掉 debug 窗口，或者传入不同的配置
    node = VisionNode()
    node.run()

def launch_arm():
    node = ArmNode()
    node.run()

if __name__ == "__main__":
    print("🚀 启动 VIST 全系统...")
    
    # 使用多进程 (Multiprocessing) 并行运行
    # 这样视觉卡顿不会影响手臂控制
    p_vision = multiprocessing.Process(target=launch_vision)
    p_arm = multiprocessing.Process(target=launch_arm)
    
    p_vision.start()
    p_arm.start()
    
    p_vision.join()
    p_arm.join()