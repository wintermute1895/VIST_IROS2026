#!/usr/bin/env python3
"""
视觉数据回放工具
读取录制的数据文件，按照原始时间戳回放 UDP 数据

用途：
1. 离线调试控制算法
2. 消融实验（对比不同参数配置）
3. 可重复的性能测试

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


class VisionDataPlayer:
    """视觉数据回放器"""

    def __init__(self, input_file, udp_ip=None, udp_port=None):
        """
        初始化回放器

        Args:
            input_file: 输入文件路径
            udp_ip: UDP 目标 IP（None=从配置读取）
            udp_port: UDP 目标端口（None=从配置读取）
        """
        # 加载配置
        config = get_config()
        self.udp_ip = udp_ip if udp_ip is not None else config.udp_ip
        self.udp_port = udp_port if udp_port is not None else config.udp_port

        # 输入文件
        self.input_file = Path(input_file)
        if not self.input_file.exists():
            raise FileNotFoundError(f"文件不存在: {self.input_file}")

        # 创建 UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (self.udp_ip, self.udp_port)

        # 加载数据
        print("📂 加载数据文件...")
        self.data = self._load_data()
        print(f"✅ 加载完成: {len(self.data)} 帧")

        # 统计信息
        self.frame_count = 0
        self.start_time = None
        self.last_print_time = None

        print("=" * 80)
        print("▶️  视觉数据回放器")
        print("=" * 80)
        print(f"输入文件: {self.input_file}")
        print(f"总帧数: {len(self.data)}")
        print(f"目标地址: {self.udp_ip}:{self.udp_port}")
        print()
        print("⚠️  请确保控制器正在运行并监听 UDP 数据")
        print("   按 Ctrl+C 停止回放")
        print("=" * 80)

    def _load_data(self):
        """加载数据文件"""
        data = []
        with open(self.input_file, 'r') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    data.append(entry)
        return data

    def play(self, speed=1.0, loop=False, start_frame=0, countdown=0):
        """
        开始回放

        Args:
            speed: 回放速度（1.0=原速，2.0=2倍速，0.5=半速）
            loop: 是否循环播放
            start_frame: 起始帧（用于跳过前面的帧）
            countdown: 倒计时秒数（给操作员准备时间）
        """
        if start_frame >= len(self.data):
            print(f"⚠️  起始帧 {start_frame} 超出范围，从第 0 帧开始")
            start_frame = 0

        # 倒计时（给操作员准备时间）
        if countdown > 0:
            print(f"\n⏱️  {countdown} 秒后开始回放...")
            print("   请准备：")
            print("   1. 确保控制器已启动并等待UDP数据")
            print("   2. 控制器应显示'等待第一个UDP数据包'")
            print("   3. 倒计时结束后将立即发送第一帧")
            print("\n倒计时：")
            for i in range(countdown, 0, -1):
                print(f"   {i}...", end='\r', flush=True)
                time.sleep(1)
            print("   🚀 开始回放！" + " " * 20 + "\n")

        print(f"▶️  开始回放 (速度: {speed}x, 循环: {loop}, 起始帧: {start_frame})...")

        try:
            iteration = 0
            while True:
                iteration += 1
                if not loop and iteration > 1:
                    break

                print(f"\n{'=' * 80}")
                print(f"🔄 第 {iteration} 轮回放")
                print(f"{'=' * 80}")

                self.start_time = time.time()
                self.last_print_time = self.start_time
                self.frame_count = 0

                # 获取第一帧的时间戳作为基准
                # 优先使用data内部的timestamp（视觉节点时间戳），如果没有则使用外层timestamp（录制时间戳）
                first_entry = self.data[start_frame]
                if 'data' in first_entry and 'timestamp' in first_entry['data']:
                    base_timestamp = first_entry['data']['timestamp']
                    use_data_timestamp = True
                    print("   使用视觉节点时间戳（data.timestamp）")
                else:
                    base_timestamp = first_entry['timestamp']
                    use_data_timestamp = False
                    print("   使用录制时间戳（timestamp）")

                for i in range(start_frame, len(self.data)):
                    entry = self.data[i]

                    # 获取当前帧的时间戳
                    if use_data_timestamp and 'data' in entry and 'timestamp' in entry['data']:
                        current_timestamp = entry['data']['timestamp']
                    else:
                        current_timestamp = entry['timestamp']

                    # 计算应该等待的时间
                    target_time = (current_timestamp - base_timestamp) / speed
                    elapsed = time.time() - self.start_time

                    # 精确等待
                    wait_time = target_time - elapsed
                    if wait_time > 0:
                        time.sleep(wait_time)

                    # 发送 UDP 数据
                    packet = entry['data']
                    data = json.dumps(packet).encode('utf-8')
                    self.sock.sendto(data, self.udp_addr)

                    self.frame_count += 1

                    # 每秒打印一次统计
                    current_time = time.time()
                    if current_time - self.last_print_time >= 1.0:
                        elapsed = current_time - self.start_time
                        fps = self.frame_count / elapsed if elapsed > 0 else 0
                        progress = (i - start_frame + 1) / (len(self.data) - start_frame) * 100
                        print(f"📊 进度: {progress:.1f}% | "
                              f"帧数: {self.frame_count}/{len(self.data) - start_frame} | "
                              f"帧率: {fps:.1f} fps")
                        self.last_print_time = current_time

                # 一轮回放完成
                elapsed = time.time() - self.start_time
                fps = self.frame_count / elapsed if elapsed > 0 else 0
                print(f"\n✅ 第 {iteration} 轮回放完成")
                print(f"   帧数: {self.frame_count} | 时长: {elapsed:.1f}s | 帧率: {fps:.1f} fps")

                if not loop:
                    break

        except KeyboardInterrupt:
            print("\n\n⏹️  用户中断回放")
        finally:
            self.sock.close()

            # 打印摘要
            print("\n" + "=" * 80)
            print("📊 回放摘要")
            print("=" * 80)
            print(f"总轮数: {iteration}")
            print(f"总帧数: {self.frame_count}")
            print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="视觉数据回放工具")
    parser.add_argument("input", type=str,
                        help="输入文件路径（例如：data/recording_001.jsonl）")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="回放速度（1.0=原速，2.0=2倍速，0.5=半速）")
    parser.add_argument("--loop", action="store_true",
                        help="循环播放")
    parser.add_argument("--start", type=int, default=0,
                        help="起始帧（用于跳过前面的帧）")
    parser.add_argument("--countdown", type=int, default=0,
                        help="启动前倒计时（秒），用于与控制器同步")
    parser.add_argument("--ip", type=str, default=None,
                        help="UDP 目标 IP（默认从配置文件读取）")
    parser.add_argument("--port", type=int, default=None,
                        help="UDP 目标端口（默认从配置文件读取）")

    args = parser.parse_args()

    # 创建回放器
    player = VisionDataPlayer(
        input_file=args.input,
        udp_ip=args.ip,
        udp_port=args.port
    )

    # 开始回放
    player.play(
        speed=args.speed,
        loop=args.loop,
        start_frame=args.start,
        countdown=args.countdown
    )


if __name__ == "__main__":
    main()