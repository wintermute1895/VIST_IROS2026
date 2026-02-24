#!/usr/bin/env python3
"""
配置化数据采集和分析管理器

功能：
1. 根据配置文件录制数据
2. 根据配置文件分析数据
3. 根据配置文件控制真机
4. 完全配置化，灵活可扩展

用法：
    # 录制数据
    python scripts/configurable_manager.py record --config config/full_config.yaml

    # 分析数据
    python scripts/configurable_manager.py analyze --config config/full_config.yaml --episode <path>

    # 完整流程（录制+分析）
    python scripts/configurable_manager.py run --config config/full_config.yaml
"""

import sys
import yaml
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List
import time

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))


class ConfigurableManager:
    """配置化管理器"""

    def __init__(self, config_path: str):
        """
        初始化管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        print(f"✓ 已加载配置: {config_path}")
        print(f"  任务: {self.config['task_info']['name']}")
        print()

    def get_enabled_topics(self) -> List[str]:
        """
        获取启用的话题列表

        Returns:
            话题列表
        """
        topics = []
        recording_config = self.config.get('recording', {})
        topics_config = recording_config.get('topics', {})

        for category, category_config in topics_config.items():
            if category_config.get('enabled', False):
                topics.extend(category_config.get('topics', []))

        return topics

    def check_control_mode(self) -> bool:
        """
        检查控制模式并启动相应节点

        Returns:
            是否需要控制真机
        """
        control_config = self.config.get('control', {})
        mode = control_config.get('mode', 'none')
        use_real_robot = control_config.get('use_real_robot', False)

        print(f"控制模式: {mode}")
        print(f"连接真机: {use_real_robot}")

        if mode == 'none':
            print("  ⚠️  无控制模式，仅录制数据")
            return False

        if not use_real_robot:
            print("  ⚠️  未启用真机连接")
            return False

        # 检查控制节点是否运行
        result = subprocess.run(
            ['ros2', 'node', 'list'],
            capture_output=True,
            text=True
        )

        if 'linkerta_node' in result.stdout or 'lbot_driver' in result.stdout:
            print("  ✓ 检测到运行的控制节点")
            return True
        else:
            print("  ❌ 未检测到控制节点")
            print("  请先启动控制系统")
            return False

    def record_data(self) -> str:
        """
        录制数据

        Returns:
            Episode路径
        """
        recording_config = self.config.get('recording', {})

        if not recording_config.get('enabled', True):
            print("录制未启用")
            return None

        # 获取参数
        task_name = self.config['task_info']['name']
        duration = recording_config.get('duration', 30)
        topics = self.get_enabled_topics()

        if not topics:
            print("错误: 没有启用的话题")
            return None

        print(f"开始录制...")
        print(f"  任务: {task_name}")
        print(f"  时长: {duration}秒")
        print(f"  话题数: {len(topics)}")
        print()

        # 检查控制模式
        if not self.check_control_mode():
            response = input("控制节点未运行，是否继续录制？(y/n): ")
            if response.lower() != 'y':
                print("取消录制")
                return None

        print()

        # 使用Episode管理器或直接录制
        use_episode_manager = self.config.get('advanced', {}).get('use_episode_manager', True)

        if use_episode_manager:
            # 使用Episode管理器
            from episode_manager import EpisodeManager

            manager = EpisodeManager()

            # 创建任务
            task_dir = Path('data/collection') / task_name
            if not task_dir.exists():
                session_id = manager.create_task(task_name, self.config)
            else:
                # 使用最新session
                sessions = sorted(task_dir.glob('session_*'))
                if sessions:
                    session_id = sessions[-1].name
                else:
                    session_id = manager.create_task(task_name, self.config)

            print(f"Session ID: {session_id}")

            # 开始录制
            episode_id = manager.start_episode(session_id, max_duration=duration, topics=topics)
            print(f"Episode ID: {episode_id}")

            # 等待录制完成
            print(f"\n录制中... ({duration}秒)")
            time.sleep(duration)

            # 停止录制
            auto_validate = recording_config.get('automation', {}).get('auto_validate', True)
            manager.stop_episode(episode_id, auto_validate=auto_validate)

            # 获取Episode路径
            episode_dir = manager._find_episode_dir(episode_id)
            return str(episode_dir)

        else:
            # 直接录制
            cmd = [
                'bash', 'scripts/record_data.sh',
                '--task', task_name,
                '--config', str(self.config_path),
                '--duration', str(duration),
                '--no-episode-manager'
            ]

            result = subprocess.run(cmd)

            if result.returncode != 0:
                print("录制失败")
                return None

            # 查找最新的Episode
            task_dir = Path('data/collection') / task_name
            if task_dir.exists():
                sessions = sorted(task_dir.glob('session_*'))
                if sessions:
                    episodes = sorted(sessions[-1].glob('episode_*'))
                    if episodes:
                        return str(episodes[-1])

            return None

    def analyze_data(self, episode_path: str):
        """
        分析数据

        Args:
            episode_path: Episode路径
        """
        analysis_config = self.config.get('analysis', {})

        if not analysis_config.get('enabled', True):
            print("分析未启用")
            return

        print(f"开始分析...")
        print(f"  Episode: {episode_path}")
        print()

        # 使用analyze_episode.py
        from analyze_episode import EpisodeAnalyzer

        analyzer = EpisodeAnalyzer(episode_path)

        # 根据配置执行分析
        metrics_config = analysis_config.get('metrics', {})

        # 频率分析
        if metrics_config.get('frequency', {}).get('enabled', True):
            frequency_analysis = analyzer.analyze_frequency()
        else:
            frequency_analysis = {}

        # 时间同步分析
        if metrics_config.get('time_sync', {}).get('enabled', True):
            sync_results = analyzer.analyze_time_sync()
        else:
            sync_results = {}

        # 完整性检查
        if metrics_config.get('integrity', {}).get('enabled', True):
            integrity_check = analyzer.check_data_integrity()
        else:
            integrity_check = {}

        # 可视化
        viz_config = analysis_config.get('visualization', {})
        if viz_config.get('enabled', True):
            if frequency_analysis:
                analyzer.visualize_frequency(frequency_analysis)
            if metrics_config.get('trajectory', {}).get('enabled', True):
                analyzer.visualize_trajectory()

        # 生成报告
        reporting_config = analysis_config.get('reporting', {})
        if reporting_config.get('enabled', True):
            analyzer.generate_report(frequency_analysis, sync_results, integrity_check)

        print()
        print("分析完成！")

    def run_full_pipeline(self):
        """运行完整流程：录制 + 分析"""
        print("=" * 80)
        print("配置化数据采集和分析流程")
        print("=" * 80)
        print()

        # 1. 录制数据
        episode_path = self.record_data()

        if not episode_path:
            print("录制失败，终止流程")
            return

        print()
        print("=" * 80)
        print()

        # 2. 分析数据（如果启用）
        auto_analyze = self.config.get('recording', {}).get('automation', {}).get('auto_analyze', False)

        if auto_analyze:
            self.analyze_data(episode_path)
        else:
            print("自动分析未启用")
            print(f"手动分析: python scripts/analyze_episode.py {episode_path}")

        print()
        print("=" * 80)
        print("流程完成！")
        print("=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="配置化数据采集和分析管理器")
    parser.add_argument('command', choices=['record', 'analyze', 'run'],
                        help='命令: record(录制) | analyze(分析) | run(完整流程)')
    parser.add_argument('--config', required=True, help='配置文件路径')
    parser.add_argument('--episode', help='Episode路径（analyze命令需要）')

    args = parser.parse_args()

    try:
        manager = ConfigurableManager(args.config)

        if args.command == 'record':
            episode_path = manager.record_data()
            if episode_path:
                print(f"\n录制完成: {episode_path}")

        elif args.command == 'analyze':
            if not args.episode:
                print("错误: analyze命令需要指定 --episode 参数")
                sys.exit(1)
            manager.analyze_data(args.episode)

        elif args.command == 'run':
            manager.run_full_pipeline()

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
