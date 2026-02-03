import sys
import os

# 路径黑魔法：把项目根目录加入 python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.vision_node import VisionNode

if __name__ == "__main__":
    # 队友可以直接运行这个脚本来调试视觉
    print("👀 Starting Vision Module Standalone...")
    
    # 这里可以改参数，比如 camera_id=2 (如果是 RealSense)
    node = VisionNode(camera_id=0) 
    node.run()