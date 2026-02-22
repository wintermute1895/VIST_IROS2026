#!/usr/bin/env python3
"""
UDP通信测试脚本
"""
import socket
import json
import time

# 配置
UDP_IP = "127.0.0.1"
UDP_PORT = 6001

# 创建socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 测试数据
test_data = {
    "keypoints": {
        "wrist": [0.1, -0.3, 0.8],
        "elbow": [0.0, -0.2, 0.6]
    },
    "timestamp": time.time()
}

print(f"发送测试数据到 {UDP_IP}:{UDP_PORT}")
print(f"数据: {test_data}")

# 发送10次
for i in range(10):
    data = json.dumps(test_data).encode('utf-8')
    sock.sendto(data, (UDP_IP, UDP_PORT))
    print(f"  发送第 {i+1} 次")
    time.sleep(0.1)

print("✅ 测试完成")
sock.close()