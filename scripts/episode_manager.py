#!/usr/bin/env python3
"""
Episode管理器 - VIST数据采集系统的核心组件

功能：
1. 任务管理（创建、删除、查询）
2. Episode自动编号和录制控制
3. 元数据生成和管理
4. 数据质量验证
5. 训练数据转换

用法：
    # 创建任务
    python scripts/episode_manager.py create-task --name pick_and_place --config config/task_config.yaml

    # 交互式录制
    python scripts/episode_manager.py interactive --session session_20260224_153024

    # 验证Episode
    python scripts/episode_manager.py validate --episode episode_000000

    # 转换为训练格式
    python scripts/episode_manager.py convert --session session_20260224_153024 --format hdf5
"""

import sys
import json
import yaml
import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from analysis.core.rosbag_reader import RosbagReader


class EpisodeManager:
    """Episode管理器 - 统一数据采集接口"""

    def __init__(self, base_dir: str = "data/collection"):
        """
        初始化管理器

        Args:
            base_dir: 数据采集根目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 当前录制进程
        self.recording_process: Optional[subprocess.Popen] = None
        self.monitoring_processes: List[subprocess.Popen] = []

    def create_task(self, task_name: str, config: Dict) -> str:
        """
        创建新任务

        Args:
            task_name: 任务名称 (如 "pick_and_place")
            config: 任务配置 (相机、话题、参数等)

        Returns:
            session_id: 会话ID
        """
        # 创建任务目录
        task_dir = self.base_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)

        # 生成会话ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        session_dir = task_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存会话配置
        session_config = {
            "session_id": session_id,
            "task_name": task_name,
            "created_at": datetime.now().isoformat(),
            "config": config,
            "episodes": []
        }

        manifest_path = session_dir / "session_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(session_config, f, indent=2, ensure_ascii=False)

        print(f"✓ 任务创建成功")
        print(f"  任务名称: {task_name}")
        print(f"  会话ID: {session_id}")
        print(f"  会话目录: {session_dir}")

        return session_id

    def get_next_episode_number(self, session_dir: Path) -> int:
        """
        获取下一个Episode编号

        Args:
            session_dir: 会话目录

        Returns:
            下一个Episode编号
        """
        # 查找现有Episode
        existing_episodes = list(session_dir.glob("episode_*"))
        if not existing_episodes:
            return 0

        # 提取编号
        numbers = []
        for ep_dir in existing_episodes:
            try:
                num = int(ep_dir.name.split('_')[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue

        return max(numbers) + 1 if numbers else 0

    def start_episode(
        self,
        session_id: str,
        max_duration: int = 60,
        topics: List[str] = None
    ) -> str:
        """
        开始新Episode

        Args:
            session_id: 会话ID
            max_duration: 最大时长（秒）
            topics: 要录制的话题列表（None表示使用配置文件）

        Returns:
            episode_id: Episode ID
        """
        # 查找会话目录
        session_dir = self._find_session_dir(session_id)
        if not session_dir:
            raise ValueError(f"会话不存在: {session_id}")

        # 加载会话配置
        manifest_path = session_dir / "session_manifest.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            session_config = json.load(f)

        # 生成Episode ID
        episode_num = self.get_next_episode_number(session_dir)
        episode_id = f"episode_{episode_num:06d}"
        episode_dir = session_dir / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        # 确定要录制的话题
        if topics is None:
            topics = session_config['config'].get('topics', [])

        if not topics:
            raise ValueError("未指定要录制的话题")

        # 开始rosbag录制
        rosbag_dir = episode_dir / "rosbag"
        print(f"\n开始录制Episode: {episode_id}")
        print(f"  最大时长: {max_duration}秒")
        print(f"  话题数量: {len(topics)}")
        print(f"  录制目录: {rosbag_dir}")
        print()

        # 启动rosbag录制
        cmd = ["ros2", "bag", "record", "-o", str(rosbag_dir)] + topics
        self.recording_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 等待录制启动
        time.sleep(2)

        # 检查进程是否正常运行
        if self.recording_process.poll() is not None:
            raise RuntimeError("rosbag录制启动失败")

        print(f"✓ 录制已启动 (PID: {self.recording_process.pid})")

        # 保存Episode信息到会话清单
        episode_info = {
            "episode_id": episode_id,
            "started_at": datetime.now().isoformat(),
            "max_duration": max_duration,
            "topics": topics,
            "status": "recording"
        }

        session_config['episodes'].append(episode_info)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(session_config, f, indent=2, ensure_ascii=False)

        return episode_id

    def stop_episode(
        self,
        episode_id: str,
        quality_score: str = None,
        auto_validate: bool = True
    ):
        """
        停止Episode并生成报告

        Args:
            episode_id: Episode ID
            quality_score: 手动质量评分 (A/B/C/D/F)
            auto_validate: 是否自动验证数据质量
        """
        print(f"\n停止录制Episode: {episode_id}")

        # 停止rosbag录制
        if self.recording_process and self.recording_process.poll() is None:
            print("  停止rosbag录制...")
            self.recording_process.send_signal(signal.SIGINT)
            self.recording_process.wait(timeout=10)
            print("  ✓ rosbag录制已停止")

        # 停止监控进程
        for proc in self.monitoring_processes:
            if proc.poll() is None:
                proc.terminate()
        self.monitoring_processes.clear()

        # 等待文件写入完成
        time.sleep(2)

        # 查找Episode目录
        episode_dir = self._find_episode_dir(episode_id)
        if not episode_dir:
            raise ValueError(f"Episode不存在: {episode_id}")

        # 生成元数据
        print("  生成元数据...")
        self._generate_episode_metadata(episode_dir, quality_score)

        # 自动验证数据质量
        if auto_validate:
            print("  验证数据质量...")
            validation_report = self.validate_episode(episode_id)
            print(f"  ✓ 质量评级: {validation_report.get('quality_grade', 'N/A')}")

        print(f"\n✓ Episode录制完成: {episode_id}")
        print(f"  数据目录: {episode_dir}")

    def validate_episode(self, episode_id: str) -> Dict:
        """
        验证Episode数据质量

        Args:
            episode_id: Episode ID

        Returns:
            验证报告 (时间同步、数据完整性等)
        """
        episode_dir = self._find_episode_dir(episode_id)
        if not episode_dir:
            raise ValueError(f"Episode不存在: {episode_id}")

        rosbag_dir = episode_dir / "rosbag"
        if not rosbag_dir.exists():
            raise ValueError(f"rosbag目录不存在: {rosbag_dir}")

        # 运行时间同步验证
        print("    运行时间同步验证...")
        sync_report = self._run_sync_validation(rosbag_dir)

        # 保存验证报告
        report_path = episode_dir / "sync_validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(sync_report, f, indent=2, ensure_ascii=False)

        return sync_report

    def _run_sync_validation(self, rosbag_dir: Path) -> Dict:
        """
        运行时间同步验证

        Args:
            rosbag_dir: rosbag目录

        Returns:
            同步验证报告
        """
        # 导入验证器
        from validate_time_sync import TimeSyncValidator

        try:
            validator = TimeSyncValidator(str(rosbag_dir))
            validator.load_topics()

            # 自动检测参考话题
            camera_topics = [
                t for t in validator.topics_data.keys()
                if 'camera' in t.lower() or 'image' in t.lower()
            ]

            if camera_topics:
                ref_topic = camera_topics[0]
            else:
                ref_topic = list(validator.topics_data.keys())[0]

            target_topics = [t for t in validator.topics_data.keys() if t != ref_topic]

            if not target_topics:
                return {
                    "error": "没有找到目标话题进行比较",
                    "quality_grade": "F"
                }

            # 执行同步分析
            sync_results = validator.find_nearest_timestamps(ref_topic, target_topics)

            # 计算质量评级
            grade = validator.calculate_quality_grade(sync_results)
            sync_results['quality_grade'] = grade

            return sync_results

        except Exception as e:
            return {
                "error": str(e),
                "quality_grade": "F"
            }

    def _generate_episode_metadata(self, episode_dir: Path, quality_score: str = None):
        """
        生成Episode元数据

        Args:
            episode_dir: Episode目录
            quality_score: 手动质量评分
        """
        from generate_episode_metadata import EpisodeMetadataGenerator

        rosbag_dir = episode_dir / "rosbag"
        generator = EpisodeMetadataGenerator(str(rosbag_dir))

        # 提取任务名称
        task_name = episode_dir.parent.parent.name

        metadata = generator.generate_metadata(task_name, quality_score)
        generator.save_metadata(metadata)

    def _find_session_dir(self, session_id: str) -> Optional[Path]:
        """
        查找会话目录

        Args:
            session_id: 会话ID

        Returns:
            会话目录路径，如果不存在则返回None
        """
        for task_dir in self.base_dir.iterdir():
            if not task_dir.is_dir():
                continue

            session_dir = task_dir / session_id
            if session_dir.exists():
                return session_dir

        return None

    def _find_episode_dir(self, episode_id: str) -> Optional[Path]:
        """
        查找Episode目录

        Args:
            episode_id: Episode ID

        Returns:
            Episode目录路径，如果不存在则返回None
        """
        for task_dir in self.base_dir.iterdir():
            if not task_dir.is_dir():
                continue

            for session_dir in task_dir.iterdir():
                if not session_dir.is_dir() or not session_dir.name.startswith('session_'):
                    continue

                episode_dir = session_dir / episode_id
                if episode_dir.exists():
                    return episode_dir

        return None

    def interactive_mode(self, session_id: str):
        """
        交互式录制模式

        Args:
            session_id: 会话ID
        """
        print("=" * 80)
        print("Episode管理器 - 交互式模式")
        print("=" * 80)
        print()

        # 加载会话配置
        session_dir = self._find_session_dir(session_id)
        if not session_dir:
            print(f"错误: 会话不存在: {session_id}")
            return

        manifest_path = session_dir / "session_manifest.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            session_config = json.load(f)

        print(f"会话ID: {session_id}")
        print(f"任务名称: {session_config['task_name']}")
        print(f"已录制Episodes: {len(session_config['episodes'])}")
        print()

        try:
            while True:
                print("-" * 80)
                print("命令:")
                print("  [s] 开始新Episode")
                print("  [q] 退出")
                print()

                choice = input("请选择: ").strip().lower()

                if choice == 's':
                    # 开始新Episode
                    duration = input("录制时长（秒，默认30）: ").strip()
                    duration = int(duration) if duration else 30

                    episode_id = self.start_episode(session_id, max_duration=duration)

                    print()
                    print("录制中...")
                    print("按Enter停止录制")
                    input()

                    self.stop_episode(episode_id)

                elif choice == 'q':
                    print("退出交互模式")
                    break

                else:
                    print("无效的选择")

        except KeyboardInterrupt:
            print("\n\n中断录制")
            if self.recording_process and self.recording_process.poll() is None:
                self.recording_process.terminate()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Episode管理器")
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # create-task命令
    create_parser = subparsers.add_parser('create-task', help='创建新任务')
    create_parser.add_argument('--name', required=True, help='任务名称')
    create_parser.add_argument('--config', required=True, help='配置文件路径')

    # interactive命令
    interactive_parser = subparsers.add_parser('interactive', help='交互式录制模式')
    interactive_parser.add_argument('--session', required=True, help='会话ID')

    # validate命令
    validate_parser = subparsers.add_parser('validate', help='验证Episode')
    validate_parser.add_argument('--episode', required=True, help='Episode ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = EpisodeManager()

    if args.command == 'create-task':
        # 加载配置文件
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        session_id = manager.create_task(args.name, config)
        print()
        print("下一步:")
        print(f"  python scripts/episode_manager.py interactive --session {session_id}")

    elif args.command == 'interactive':
        manager.interactive_mode(args.session)

    elif args.command == 'validate':
        report = manager.validate_episode(args.episode)
        print()
        print("验证报告:")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()