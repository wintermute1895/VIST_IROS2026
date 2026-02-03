#!/usr/bin/env python3
"""
集成测试：验证 IK 求解器在 arm_node 中的工作情况

测试流程：
1. 启动 arm_node（不启用可视化，避免阻塞）
2. 发送测试关键点数据
3. 观察 IK 求解是否正常工作
"""

import time
import socket
import json
import numpy as np
from src.nodes.arm_node import ArmNode
import threading


def send_test_keypoints(duration=5):
    """发送测试关键点数据"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = ("127.0.0.1", 6001)

    print("\n📡 开始发送测试关键点数据...")
    time.sleep(1)  # 等待 arm_node 启动

    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < duration:
        t = time.time() - start_time

        # 生成简单的测试数据（手臂在前方画圆）
        radius = 0.1
        center = np.array([0.3, 0.0, 0.3])

        # 肩部（固定）
        shoulder = np.array([0.0, 0.0, 0.0])

        # 肘部（固定）
        elbow = np.array([0.15, 0.0, 0.15])

        # 腕部（画圆）
        wrist = center + radius * np.array([np.cos(t), np.sin(t), 0])

        # 指关节（简单设置）
        index_mcp = wrist + np.array([0.04, 0.0, 0.0])
        pinky_mcp = wrist + np.array([-0.04, 0.0, 0.0])

        keypoints = {
            'shoulder': shoulder.tolist(),
            'elbow': elbow.tolist(),
            'wrist': wrist.tolist(),
            'index_mcp': index_mcp.tolist(),
            'pinky_mcp': pinky_mcp.tolist()
        }

        # 发送数据
        data = json.dumps(keypoints).encode('utf-8')
        sock.sendto(data, target_addr)

        frame_count += 1
        time.sleep(1.0 / 30.0)  # 30 Hz

    print(f"✅ 发送完成，共 {frame_count} 帧")
    sock.close()


def main():
    print("🧪 IK 集成测试")
    print("="*60)

    # 创建 arm_node（不启用可视化）
    print("\n1️⃣ 初始化 ArmNode...")
    node = ArmNode(visualize=False)

    # 在后台线程发送测试数据
    print("\n2️⃣ 启动测试数据发送线程...")
    sender_thread = threading.Thread(target=send_test_keypoints, args=(5,))
    sender_thread.daemon = True
    sender_thread.start()

    # 运行 arm_node（5秒）
    print("\n3️⃣ 运行 ArmNode (5秒)...")
    print("="*60)

    start_time = time.time()
    try:
        while time.time() - start_time < 5:
            node.spin_once()
            time.sleep(0.02)  # 50 Hz
    except KeyboardInterrupt:
        pass

    print("\n" + "="*60)
    print("✅ 测试完成！")
    print("\n如果看到 IK 求解成功的消息，说明集成正常工作。")


if __name__ == "__main__":
    main()
