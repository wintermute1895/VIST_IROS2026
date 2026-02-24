#!/usr/bin/env python3
"""
简单的UDP数据监听器
用于测试vision_node是否正常发送数据
"""

import socket
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import get_config

def main():
    # 从配置文件读取UDP设置
    config = get_config()
    udp_host = config.udp_host  # 0.0.0.0
    udp_port = config.udp_port  # 6001

    print("=" * 60)
    print("UDP数据监听器")
    print("=" * 60)
    print(f"监听地址: {udp_host}:{udp_port}")
    print()
    print("等待接收数据...")
    print("请在另一个终端运行: python src/nodes/vision_node_depth.py")
    print("按 Ctrl+C 停止")
    print()

    # 创建UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_host, udp_port))
    sock.settimeout(1.0)

    packet_count = 0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65536)
                packet_count += 1

                # 解析JSON
                try:
                    json_data = json.loads(data.decode('utf-8'))

                    print(f"\n✅ 收到数据包 #{packet_count} (来自 {addr})")
                    print(f"   时间戳: {json_data.get('timestamp', 0):.3f}")

                    # 显示关键点数据
                    if 'wrist' in json_data:
                        wrist = json_data['wrist']
                        print(f"   手腕: x={wrist['x']:.3f}, y={wrist['y']:.3f}, z={wrist['z']:.3f}")

                    if 'elbow' in json_data:
                        elbow = json_data['elbow']
                        print(f"   肘部: x={elbow['x']:.3f}, y={elbow['y']:.3f}, z={elbow['z']:.3f}")

                    if 'shoulder' in json_data:
                        shoulder = json_data['shoulder']
                        print(f"   肩部: x={shoulder['x']:.3f}, y={shoulder['y']:.3f}, z={shoulder['z']:.3f}")

                except json.JSONDecodeError:
                    print(f"\n⚠️  收到非JSON数据: {data[:100]}")

            except socket.timeout:
                # 超时，继续等待
                print("⏳ 等待数据...", end='\r')
                continue

    except KeyboardInterrupt:
        print("\n\n停止监听")
    finally:
        sock.close()

if __name__ == '__main__':
    main()
