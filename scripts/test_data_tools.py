#!/usr/bin/env python3
"""
数据录制与回放功能测试
验证录制和回放工具是否正常工作

Author: VIST Project
Date: 2026-02-22
"""

import socket
import json
import time
import subprocess
import sys
from pathlib import Path

# 测试配置
TEST_UDP_IP = "127.0.0.1"
TEST_UDP_PORT = 5005
TEST_DURATION = 5  # 秒
TEST_FILE = "data/test_recording.jsonl"


def test_recording():
    """测试录制功能"""
    print("=" * 80)
    print("🧪 测试 1: 数据录制")
    print("=" * 80)

    # 启动录制进程
    print("\n📹 启动录制进程...")
    record_proc = subprocess.Popen([
        sys.executable,
        "scripts/record_vision_data.py",
        TEST_FILE,
        "--duration", str(TEST_DURATION),
        "--ip", TEST_UDP_IP,
        "--port", str(TEST_UDP_PORT)
    ])

    # 等待录制进程启动
    time.sleep(1)

    # 发送测试数据
    print("📡 发送测试数据...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    for i in range(TEST_DURATION * 17):  # 模拟 17Hz
        packet = {
            'keypoints': {
                'shoulder': [0.0, 0.0, 0.0],
                'elbow': [0.1, 0.2, 0.3],
                'wrist': [0.2, 0.4, 0.6],
                'index_mcp': [0.3, 0.6, 0.9],
                'pinky_mcp': [0.4, 0.8, 1.2]
            },
            'timestamp': time.time()
        }
        data = json.dumps(packet).encode('utf-8')
        sock.sendto(data, (TEST_UDP_IP, TEST_UDP_PORT))
        time.sleep(1.0 / 17)  # 17Hz

    sock.close()

    # 等待录制完成
    print("⏳ 等待录制完成...")
    record_proc.wait()

    # 验证文件
    test_file = Path(TEST_FILE)
    if not test_file.exists():
        print("❌ 测试失败: 录制文件不存在")
        return False

    # 检查文件内容
    with open(test_file, 'r') as f:
        lines = f.readlines()

    if len(lines) == 0:
        print("❌ 测试失败: 录制文件为空")
        return False

    print(f"✅ 测试通过: 录制了 {len(lines)} 帧")
    return True


def test_playback():
    """测试回放功能"""
    print("\n" + "=" * 80)
    print("🧪 测试 2: 数据回放")
    print("=" * 80)

    # 创建 UDP 接收器
    print("\n📡 启动 UDP 接收器...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((TEST_UDP_IP, TEST_UDP_PORT))
    sock.settimeout(1.0)

    # 启动回放进程
    print("▶️  启动回放进程...")
    playback_proc = subprocess.Popen([
        sys.executable,
        "scripts/playback_vision_data.py",
        TEST_FILE,
        "--ip", TEST_UDP_IP,
        "--port", str(TEST_UDP_PORT)
    ])

    # 接收数据
    print("📥 接收回放数据...")
    received_count = 0
    start_time = time.time()

    while time.time() - start_time < TEST_DURATION + 2:
        try:
            data, addr = sock.recvfrom(65536)
            packet = json.loads(data.decode('utf-8'))
            received_count += 1
        except socket.timeout:
            continue
        except json.JSONDecodeError:
            print("⚠️  收到无效的 JSON 数据")
            continue

    sock.close()

    # 终止回放进程
    playback_proc.terminate()
    playback_proc.wait()

    # 验证结果
    if received_count == 0:
        print("❌ 测试失败: 未收到回放数据")
        return False

    print(f"✅ 测试通过: 接收了 {received_count} 帧")
    return True


def cleanup():
    """清理测试文件"""
    print("\n🧹 清理测试文件...")
    test_file = Path(TEST_FILE)
    if test_file.exists():
        test_file.unlink()
        print("✅ 清理完成")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🧪 数据录制与回放功能测试")
    print("=" * 80)
    print(f"测试配置:")
    print(f"  UDP 地址: {TEST_UDP_IP}:{TEST_UDP_PORT}")
    print(f"  测试时长: {TEST_DURATION}s")
    print(f"  测试文件: {TEST_FILE}")
    print("=" * 80)

    try:
        # 测试录制
        if not test_recording():
            print("\n❌ 录制测试失败")
            return 1

        # 测试回放
        if not test_playback():
            print("\n❌ 回放测试失败")
            return 1

        # 所有测试通过
        print("\n" + "=" * 80)
        print("✅ 所有测试通过！")
        print("=" * 80)
        return 0

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())