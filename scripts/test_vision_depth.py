#!/usr/bin/env python3
"""
测试 VisionNodeWithDepth - 验证 RealSense 深度集成
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.nodes.vision_node_depth import VisionNodeWithDepth

if __name__ == "__main__":
    print("=" * 60)
    print("测试 VisionNodeWithDepth")
    print("=" * 60)
    print()
    print("功能：")
    print("  ✓ MediaPipe Pose 姿态检测")
    print("  ✓ RealSense 深度数据集成")
    print("  ✓ 自动 RGB-Depth 对齐")
    print("  ✓ 动态归零机制")
    print()
    print("显示信息：")
    print("  - 绿色骨架：MediaPipe 检测结果")
    print("  - 黄色标签：关键点名称 + 深度值（毫米）")
    print("  - 左下角：FPS 和平均深度")
    print()
    print("按 'q' 或 ESC 退出")
    print("=" * 60)
    print()

    try:
        # 创建节点（不发送 UDP，只显示）
        node = VisionNodeWithDepth(
            udp_ip="127.0.0.1",
            udp_port=6001,
            scale=1.0,
            width=640,
            height=480,
            fps=30
        )

        # 运行（显示窗口）
        node.run(show_window=True)

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
