#!/usr/bin/env python3
"""
测试脚本：发送模拟的人体关键点数据到 ArmNode

这个脚本模拟 MediaPipe 捕捉到的人体关键点数据，
通过 UDP 发送给 arm_node.py 进行运动映射测试。

新版本：使用指关节（index_mcp, pinky_mcp）替代 palm，
避免手臂伸直时的奇异点问题。
"""

import socket
import json
import time
import numpy as np


def generate_test_keypoints(t):
    """
    生成测试用的人体关键点数据（包含指关节）

    测试场景：
    1. 手臂周期性伸直（测试奇异点鲁棒性）
    2. 指关节围绕前臂旋转（模拟拧螺丝动作）

    :param t: 时间（秒）
    :return: 关键点字典
    """
    # 肩部位置（固定）
    shoulder = np.array([0.0, 0.0, 0.0])

    # 伸直程度（0=弯曲, 1=完全伸直）
    # 周期性变化，测试手臂伸直时的鲁棒性
    straightness = 0.5 + 0.5 * np.sin(t * 0.3)  # 0到1之间变化

    # 肘部位置（上臂长度约 0.3m）
    # 伸直时角度减小
    angle_upper = 0.3 * np.sin(t * 0.5) * (1 - straightness * 0.8)
    elbow = shoulder + np.array([
        0.3 * np.cos(angle_upper),
        0.0,
        0.3 * np.sin(angle_upper)
    ])

    # 腕部位置（前臂长度约 0.25m）
    # 当 straightness 接近 1 时，手臂几乎伸直（前臂与上臂共线）
    angle_fore = 0.5 * np.sin(t * 0.8) * (1 - straightness * 0.9)
    wrist_direction = np.array([
        np.cos(angle_fore),
        0.0,
        np.sin(angle_fore)
    ])
    wrist = elbow + 0.25 * wrist_direction

    # ==========================================
    # 计算指关节位置（关键创新）
    # ==========================================
    # 1. 计算前臂方向
    forearm_vec = wrist - elbow
    forearm_norm = np.linalg.norm(forearm_vec)
    if forearm_norm < 0.001:
        forearm_dir = np.array([1, 0, 0])  # 退化情况
    else:
        forearm_dir = forearm_vec / forearm_norm

    # 2. 构建垂直于前臂的平面（两个正交基向量）
    # 找第一个垂直向量
    if abs(forearm_dir[2]) < 0.9:
        perp1 = np.cross(forearm_dir, np.array([0, 0, 1]))
    else:
        perp1 = np.cross(forearm_dir, np.array([1, 0, 0]))
    perp1 = perp1 / np.linalg.norm(perp1)

    # 第二个垂直向量（通过叉乘自动正交）
    perp2 = np.cross(forearm_dir, perp1)
    perp2 = perp2 / np.linalg.norm(perp2)

    # 3. 手掌宽度（食指到小指的距离）
    hand_width = 0.08  # 8cm

    # 4. Roll 角度（模拟拧螺丝动作：手掌围绕前臂旋转）
    roll_angle = t * 1.0  # 1 rad/s 旋转速度

    # 5. 在垂直平面上生成指关节位置
    # 食指根部（index MCP）
    index_mcp = wrist + (hand_width / 2) * (
        np.cos(roll_angle) * perp1 + np.sin(roll_angle) * perp2
    )

    # 小指根部（pinky MCP）
    pinky_mcp = wrist - (hand_width / 2) * (
        np.cos(roll_angle) * perp1 + np.sin(roll_angle) * perp2
    )

    return {
        'shoulder': shoulder.tolist(),
        'elbow': elbow.tolist(),
        'wrist': wrist.tolist(),
        'index_mcp': index_mcp.tolist(),
        'pinky_mcp': pinky_mcp.tolist()
    }


def main():
    """主函数：持续发送测试数据"""
    # 创建 UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = ("127.0.0.1", 6001)  # arm_node 的 UDP 端口

    print("🚀 开始发送测试关键点数据（新版：使用指关节）...")
    print(f"   目标地址: {target_addr}")
    print("   测试场景：")
    print("     1. 手臂周期性伸直（测试奇异点鲁棒性）")
    print("     2. 指关节围绕前臂旋转（模拟拧螺丝动作）")
    print("   按 Ctrl+C 停止")
    print()

    start_time = time.time()
    frame_count = 0

    try:
        while True:
            # 生成测试数据
            t = time.time() - start_time
            keypoints = generate_test_keypoints(t)

            # 转换为 JSON 并发送
            data = json.dumps(keypoints).encode('utf-8')
            sock.sendto(data, target_addr)

            frame_count += 1

            # 每秒打印一次状态
            if frame_count % 30 == 0:
                # 计算当前伸直程度
                straightness = 0.5 + 0.5 * np.sin(t * 0.3)
                print(f"✅ 已发送 {frame_count} 帧数据 (t={t:.2f}s)")
                print(f"   当前腕部位置: {np.array(keypoints['wrist'])}")
                print(f"   手臂伸直程度: {straightness*100:.1f}%")

            # 30 Hz 发送频率
            time.sleep(1.0 / 30.0)

    except KeyboardInterrupt:
        print("\n⏹️ 停止发送")
        print(f"   总共发送了 {frame_count} 帧数据")

    finally:
        sock.close()


if __name__ == "__main__":
    main()
