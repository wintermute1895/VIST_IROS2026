#!/usr/bin/env python3
"""
测试UDP发送器 - 模拟视觉节点发送关键点数据

用途：在没有摄像头的情况下测试仿真脚本
"""
import socket
import json
import time
import numpy as np

def send_test_data(udp_ip="127.0.0.1", udp_port=6001, duration=60):
    """
    发送测试关键点数据

    Args:
        udp_ip: 目标IP
        udp_port: 目标端口
        duration: 运行时长（秒）
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"📡 开始发送测试数据到 {udp_ip}:{udp_port}")
    print(f"   运行时长: {duration}秒")
    print(f"   按 Ctrl+C 停止\n")

    start_time = time.time()
    frame_count = 0

    try:
        while time.time() - start_time < duration:
            # 生成测试关键点数据（肩膀坐标系）
            t = time.time() - start_time

            # 模拟手臂运动（圆周运动）
            radius = 0.3  # 30cm半径
            omega = 0.5   # 角速度

            # 肩部位置（原点）
            shoulder = [0.0, 0.0, 0.0]

            # 肘部位置（上臂长度约0.29m）
            elbow = [
                0.29 * np.cos(omega * t),
                0.29 * np.sin(omega * t),
                0.0
            ]

            # 手腕位置（前臂长度约0.24m）
            wrist = [
                elbow[0] + 0.24 * np.cos(omega * t + np.pi/4),
                elbow[1] + 0.24 * np.sin(omega * t + np.pi/4),
                0.0
            ]

            # 构造数据包
            packet = {
                "keypoints": {
                    "shoulder": shoulder,
                    "elbow": elbow,
                    "wrist": wrist
                },
                "timestamp": time.time(),
                "frame": frame_count
            }

            # 发送数据
            data = json.dumps(packet).encode('utf-8')
            sock.sendto(data, (udp_ip, udp_port))

            frame_count += 1

            # 每秒打印一次状态
            if frame_count % 30 == 0:
                print(f"✅ 已发送 {frame_count} 帧 | "
                      f"手腕位置: [{wrist[0]:.3f}, {wrist[1]:.3f}, {wrist[2]:.3f}]")

            # 30 FPS
            time.sleep(1/30)

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")

    finally:
        sock.close()
        print(f"\n📊 统计:")
        print(f"   总帧数: {frame_count}")
        print(f"   运行时长: {time.time() - start_time:.1f}秒")
        print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")
        print("\n✅ 测试发送器已退出")


if __name__ == "__main__":
    send_test_data()