import sys
import os
# 路径黑魔法
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.vision_node import VisionNode

if __name__ == "__main__":
    # 单独调试时，我可以看到 cv2.imshow 的窗口
    node = VisionNode(camera_id=0)
    print("👀 单独调试视觉模块...")
    node.run()