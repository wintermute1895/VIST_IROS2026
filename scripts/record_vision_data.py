#!/usr/bin/env python3
"""
视觉数据录制工具
监听 UDP 数据流，带时间戳保存到文件

用途：
1. 录制标准的遥操作动作序列
2. 用于离线调试卡尔曼滤波参数
3. 用于消融实验和性能对比

Author: VIST Project
Date: 2026-02-22
"""

import socket
import json
import time
import argparse
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config


class VisionDataRecorder:
    """视觉数据录制器"""

    def __init__(self, output_file, udp_ip=None, udp_port=None):
        """
        初始化录制器

        Args:
            output_file: 输出文件路径
            udp_ip: UDP 监听 IP（None=从配置读取）
            udp_port: UDP 监听端口（None=从配置读取）
        """
        # 加载配置
        config = get_config()
        self.udp_ip = udp_ip if udp_ip is not None else config.udp_ip
        self.udp_port = udp_port if udp_port is not None else config.udp_port

        # 输出文件
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # 创建 UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)  # 100ms 超时，用于响应 Ctrl+C

        # 统计信息
        self.frame_count = 0
        self.start_time = None
        self.last_print_time = None

        print("=" * 80)
        print("📹 视觉数据录制器")
        print("=" * 80)
        print(f"监听地址: {self.udp_ip}:{self.udp_port}")
        print(f"输出文件: {self.output_file}")
        print(f"数据格式: JSONL (每行一个 JSON 对象)")
        print()
        print("⚠️  请确保视觉节点正在运行并发送数据")
        print("   按 Ctrl+C 停止录制")
        print("=" * 80)

    def record(self, duration=None, countdown=10, stabilize=3):
        """
        开始录制

        Args:
            duration: 录制时长（秒），None=无限录制
            countdown: 录制前倒计时（秒），默认10秒
            stabilize: 稳定期（秒），倒计时结束后等待姿势稳定，默认3秒
        """
        # 倒计时
        if countdown > 0:
            print("\n" + "=" * 80)
            print("⏰ 录制倒计时")
            print("=" * 80)
            print(f"⏱️  {countdown} 秒后开始录制")
            print("\n请利用这段时间：")
            print("  1. 从电脑前走到摄像头视野内")
            print("  2. 调整站位，确保身体在摄像头中心")
            print("  3. 确认手臂在摄像头视野内")
            print("  4. 准备开始操作")
            print("\n倒计时：")

            for i in range(countdown, 0, -1):
                print(f"   {i}...", end='\r', flush=True)
                time.sleep(1)
            print("   🔴 开始录制！" + " " * 20)
            print()

        print("🔴 正在录制...")
        self.start_time = time.time()
        self.last_print_time = self.start_time

        try:
            with open(self.output_file, 'w') as f:
                while True:
                    # 检查是否超时
                    if duration is not None:
                        elapsed = time.time() - self.start_time
                        if elapsed >= duration:
                            print(f"\n⏱️  达到录制时长 {duration}s，停止录制")
                            break

                    # 接收 UDP 数据
                    try:
                        data, addr = self.sock.recvfrom(65536)
                    except socket.timeout:
                        continue

                    # 解析 JSON
                    try:
                        packet = json.loads(data.decode('utf-8'))
                    except json.JSONDecodeError:
                        print(f"⚠️  无效的 JSON 数据，跳过")
                        continue

                    # 添加录制时间戳
                    record_entry = {
                        'timestamp': time.time(),
                        'frame_id': self.frame_count,
                        'data': packet
                    }

                    # 写入文件（每行一个 JSON 对象）
                    f.write(json.dumps(record_entry) + '\n')
                    f.flush()  # 立即写入磁盘

                    self.frame_count += 1

                    # 每秒打印一次统计
                    current_time = time.time()
                    if current_time - self.last_print_time >= 1.0:
                        elapsed = current_time - self.start_time
                        fps = self.frame_count / elapsed if elapsed > 0 else 0
                        print(f"📊 帧数: {self.frame_count} | "
                              f"时长: {elapsed:.1f}s | "
                              f"帧率: {fps:.1f} fps")
                        self.last_print_time = current_time

        except KeyboardInterrupt:
            print("\n\n⏹️  用户中断录制")
        finally:
            self.sock.close()

            # 打印摘要
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0

            print("\n" + "=" * 80)
            print("📊 录制摘要")
            print("=" * 80)
            print(f"总帧数: {self.frame_count}")
            print(f"录制时长: {elapsed:.1f}s")
            print(f"平均帧率: {fps:.1f} fps")
            print(f"输出文件: {self.output_file}")
            print(f"文件大小: {self.output_file.stat().st_size / 1024:.1f} KB")
            print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="视觉数据录制工具")
    parser.add_argument("output", type=str,
                        help="输出文件路径（例如：data/recording_001.jsonl）")
    parser.add_argument("--duration", type=float, default=None,
                        help="录制时长（秒），默认无限录制")
    parser.add_argument("--countdown", type=int, default=10,
                        help="录制前倒计时（秒），默认10秒")
    parser.add_argument("--ip", type=str, default=None,
                        help="UDP 监听 IP（默认从配置文件读取）")
    parser.add_argument("--port", type=int, default=None,
                        help="UDP 监听端口（默认从配置文件读取）")

    args = parser.parse_args()

    # 创建录制器
    recorder = VisionDataRecorder(
        output_file=args.output,
        udp_ip=args.ip,
        udp_port=args.port
    )

    # 开始录制
    recorder.record(duration=args.duration, countdown=args.countdown)


if __name__ == "__main__":
    main()