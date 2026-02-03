#!/usr/bin/env python3
"""
测试脚本：Vision Node + Arm Node 完整集成
运行此脚本将启动视觉节点（摄像头输入）和手臂控制节点（6-DoF IK）
"""
import sys
import threading
import time


def run_vision_node():
    """在独立线程中运行视觉节点"""
    from src.nodes.vision_node import VisionNode

    print("🎥 [Thread] 启动视觉节点...")
    node = VisionNode(
        camera_id=0,
        udp_ip="127.0.0.1",
        udp_port=6001,
        scale=1.0  # 可调整灵敏度
    )
    node.run(show_window=True)


def run_arm_node():
    """在主线程中运行手臂控制节点"""
    from src.nodes.arm_node import ArmNode

    # 等待视觉节点启动
    time.sleep(2)

    print("🤖 [Main] 启动手臂控制节点...")
    node = ArmNode(visualize=True, dof=7, udp_port=6001)
    node.run(frequency=50)  # 50 Hz 控制频率


if __name__ == "__main__":
    print("=" * 60)
    print("VIST - Vision-based Intent-aware State Teleoperation")
    print("完整系统集成测试")
    print("=" * 60)
    print()
    print("📋 系统组件:")
    print("  1. Vision Node: MediaPipe Hands 手部检测")
    print("  2. Motion Mapper: 人体 → 机器人坐标映射")
    print("  3. IK Solver: 6-DoF 逆运动学求解")
    print("  4. Arm Node: 机器人控制节点")
    print("  5. MeshCat Visualizer: 3D 可视化")
    print()
    print("🎯 操作说明:")
    print("  - 将手放在摄像头前")
    print("  - 移动手部控制机械臂")
    print("  - 按 'q' 或 ESC 退出视觉窗口")
    print("  - 按 Ctrl+C 停止整个系统")
    print()
    print("=" * 60)
    print()

    try:
        # 在独立线程中启动视觉节点
        vision_thread = threading.Thread(target=run_vision_node, daemon=True)
        vision_thread.start()

        # 在主线程中运行手臂控制节点
        run_arm_node()

    except KeyboardInterrupt:
        print("\n⏹️ 收到停止信号，正在退出...")
        sys.exit(0)
