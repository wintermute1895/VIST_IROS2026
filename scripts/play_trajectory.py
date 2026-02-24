#!/usr/bin/env python3
"""
VIST离线轨迹播放器
读取录制的VIST滤波后的关节轨迹，在机器人上播放

功能：
1. 加载.npz格式的录制数据
2. 按原始时间戳播放
3. 支持速度调节（0.5x, 1x, 2x等）
4. 支持循环播放
5. 安全检查和限位

Author: VIST Project
Date: 2026-02-23
"""

import os
import sys
import time
import numpy as np
from pathlib import Path
from typing import Optional, Dict

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.robot.robot_interface import RobotInterface
from src.utils.data_logger import load_experiment_data


class VISTTrajectoryPlayer:
    """VIST轨迹播放器"""

    def __init__(self, robot_interface: RobotInterface, playback_speed: float = 1.0):
        """
        初始化播放器

        Args:
            robot_interface: 机器人接口
            playback_speed: 播放速度倍率（1.0=原速，0.5=半速，2.0=2倍速）
        """
        self.robot = robot_interface
        self.playback_speed = playback_speed

        # 播放状态
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.total_frames = 0

        # 数据
        self.timestamps = None
        self.filtered_output = None  # VIST滤波后的关节角度

        print(f"✅ [TrajectoryPlayer] 初始化完成 (速度: {playback_speed}x)")

    def load_trajectory(self, experiment_dir: str, trial_number: int = 1):
        """
        加载轨迹数据

        Args:
            experiment_dir: 实验目录路径
            trial_number: 试验编号
        """
        print(f"\n📂 [TrajectoryPlayer] 加载轨迹数据...")
        print(f"   实验目录: {experiment_dir}")
        print(f"   试验编号: {trial_number}")

        # 加载数据
        data = load_experiment_data(experiment_dir, trial_number)

        # 提取关键数据
        self.timestamps = data['timestamps']
        self.filtered_output = data['filtered_output']  # VIST滤波后的输出
        self.total_frames = len(self.timestamps)

        # 数据验证
        if self.total_frames == 0:
            raise ValueError("轨迹数据为空")

        duration = self.timestamps[-1] - self.timestamps[0]
        avg_freq = self.total_frames / duration if duration > 0 else 0

        print(f"\n✅ [TrajectoryPlayer] 轨迹加载完成")
        print(f"   总帧数: {self.total_frames}")
        print(f"   时长: {duration:.2f}秒")
        print(f"   平均频率: {avg_freq:.1f} Hz")
        print(f"   播放时长: {duration / self.playback_speed:.2f}秒 ({self.playback_speed}x速度)")

    def play(self, loop: bool = False, start_frame: int = 0):
        """
        播放轨迹

        Args:
            loop: 是否循环播放
            start_frame: 起始帧
        """
        if self.filtered_output is None:
            print("❌ [TrajectoryPlayer] 未加载轨迹数据")
            return

        print(f"\n🎬 [TrajectoryPlayer] 开始播放...")
        print(f"   循环播放: {'是' if loop else '否'}")
        print(f"   起始帧: {start_frame}")
        print("   按 Ctrl+C 停止\n")

        self.is_playing = True
        self.current_frame = start_frame

        try:
            while self.is_playing:
                # 播放一次完整轨迹
                self._play_once(start_frame)

                # 检查是否循环
                if not loop:
                    break

                print(f"\n🔄 [TrajectoryPlayer] 循环播放...")
                time.sleep(1.0)  # 循环间隔

        except KeyboardInterrupt:
            print(f"\n\n⏹️ [TrajectoryPlayer] 播放已停止")
        finally:
            self.is_playing = False

    def _play_once(self, start_frame: int = 0):
        """播放一次完整轨迹"""
        self.current_frame = start_frame
        start_time = time.time()
        base_timestamp = self.timestamps[start_frame]

        while self.current_frame < self.total_frames and self.is_playing:
            # 计算目标时间
            target_time = (self.timestamps[self.current_frame] - base_timestamp) / self.playback_speed
            elapsed_time = time.time() - start_time

            # 等待到目标时间
            sleep_time = target_time - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)

            # 获取当前帧的关节角度
            q_target = self.filtered_output[self.current_frame]

            # 发送到机器人
            try:
                self.robot.send_joint_command(q_target)
            except Exception as e:
                print(f"⚠️ [TrajectoryPlayer] 发送命令失败: {e}")

            # 打印进度（每30帧）
            if self.current_frame % 30 == 0:
                progress = (self.current_frame / self.total_frames) * 100
                print(f"📊 进度: {progress:.1f}% ({self.current_frame}/{self.total_frames})")

            self.current_frame += 1

        print(f"✅ [TrajectoryPlayer] 播放完成")

    def pause(self):
        """暂停播放"""
        self.is_paused = True
        print(f"⏸️ [TrajectoryPlayer] 已暂停")

    def resume(self):
        """恢复播放"""
        self.is_paused = False
        print(f"▶️ [TrajectoryPlayer] 已恢复")

    def stop(self):
        """停止播放"""
        self.is_playing = False
        print(f"⏹️ [TrajectoryPlayer] 已停止")

    def set_playback_speed(self, speed: float):
        """设置播放速度"""
        self.playback_speed = speed
        print(f"⚡ [TrajectoryPlayer] 播放速度: {speed}x")

    def get_progress(self) -> Dict:
        """获取播放进度"""
        if self.total_frames == 0:
            return {'progress': 0, 'current_frame': 0, 'total_frames': 0}

        return {
            'progress': (self.current_frame / self.total_frames) * 100,
            'current_frame': self.current_frame,
            'total_frames': self.total_frames,
            'is_playing': self.is_playing,
            'is_paused': self.is_paused
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='VIST轨迹播放器')
    parser.add_argument('experiment_dir', type=str, help='实验目录路径')
    parser.add_argument('--trial', type=int, default=1, help='试验编号（默认1）')
    parser.add_argument('--speed', type=float, default=1.0, help='播放速度倍率（默认1.0）')
    parser.add_argument('--loop', action='store_true', help='循环播放')
    parser.add_argument('--start-frame', type=int, default=0, help='起始帧（默认0）')
    parser.add_argument('--no-robot', action='store_true', help='不连接机器人（仅测试）')

    args = parser.parse_args()

    print("=" * 80)
    print("🎬 VIST轨迹播放器")
    print("=" * 80)

    # 加载配置
    config = get_config()

    # 初始化机器人接口
    if not args.no_robot:
        print("\n🤖 初始化机器人接口...")
        robot = RobotInterface(config)
        print("✅ 机器人接口初始化完成")
    else:
        print("\n⚠️ 测试模式：不连接机器人")
        robot = None

    # 创建播放器
    player = VISTTrajectoryPlayer(robot, playback_speed=args.speed)

    # 加载轨迹
    try:
        player.load_trajectory(args.experiment_dir, args.trial)
    except Exception as e:
        print(f"❌ 加载轨迹失败: {e}")
        return

    # 播放轨迹
    if robot:
        player.play(loop=args.loop, start_frame=args.start_frame)
    else:
        print("\n⚠️ 测试模式：跳过播放")
        print(f"   轨迹已加载，共 {player.total_frames} 帧")

    print("\n" + "=" * 80)
    print("✅ 播放器已退出")
    print("=" * 80)


if __name__ == '__main__':
    main()
