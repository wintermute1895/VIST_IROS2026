#!/usr/bin/env python3
"""
Episode分析脚本 - 统一的数据分析工具

功能：
1. 频率分析
2. 时间同步验证
3. 数据完整性检查
4. 轨迹可视化
5. 生成分析报告

用法：
    python scripts/analyze_episode.py <episode_path>
    python scripts/analyze_episode.py data/collection/task_name/session_*/episode_000000
    python scripts/analyze_episode.py data/collection/task_name/session_*/episode_000000 --output data/analysis/
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from analysis.core.rosbag_reader import RosbagReader
from validate_time_sync import TimeSyncValidator


class EpisodeAnalyzer:
    """Episode分析器"""

    def __init__(self, episode_path: str, output_dir: str = None):
        """
        初始化分析器

        Args:
            episode_path: Episode目录路径
            output_dir: 输出目录，None表示输出到episode目录
        """
        self.episode_path = Path(episode_path)
        self.rosbag_path = self.episode_path / "rosbag"

        if not self.rosbag_path.exists():
            raise ValueError(f"rosbag目录不存在: {self.rosbag_path}")

        # 输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # 默认输出到analysis目录
            task_name = self.episode_path.parent.parent.name
            session_name = self.episode_path.parent.name
            self.output_dir = Path("data/analysis") / task_name / session_name / self.episode_path.name

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 读取器
        self.reader = RosbagReader(str(self.rosbag_path))

    def analyze_frequency(self) -> dict:
        """
        分析话题频率

        Returns:
            频率分析结果
        """
        print("分析话题频率...")

        info = self.reader.get_info()
        frequency_analysis = {}

        for topic_name, topic_info in info['topics'].items():
            if topic_info.get('duration'):
                frequency = topic_info['count'] / topic_info['duration']
                frequency_analysis[topic_name] = {
                    'count': topic_info['count'],
                    'duration': topic_info['duration'],
                    'frequency': frequency,
                    'type': topic_info['type']
                }

        print(f"  ✓ 分析了 {len(frequency_analysis)} 个话题")
        return frequency_analysis

    def analyze_time_sync(self) -> dict:
        """
        分析时间同步质量

        Returns:
            时间同步分析结果
        """
        print("分析时间同步质量...")

        validator = TimeSyncValidator(str(self.rosbag_path))
        validator.load_topics()

        if not validator.topics_data:
            print("  ⚠️  没有可用的话题数据")
            return {}

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
            print("  ⚠️  没有目标话题进行比较")
            return {}

        sync_results = validator.find_nearest_timestamps(ref_topic, target_topics)
        sync_results['quality_grade'] = validator.calculate_quality_grade(sync_results)

        print(f"  ✓ 时间同步质量: {sync_results['quality_grade']}")
        return sync_results

    def check_data_integrity(self) -> dict:
        """
        检查数据完整性

        Returns:
            完整性检查结果
        """
        print("检查数据完整性...")

        info = self.reader.get_info()
        integrity_check = {
            'total_topics': len(info['topics']),
            'total_messages': 0,
            'empty_topics': [],
            'low_frequency_topics': [],
            'issues': []
        }

        for topic_name, topic_info in info['topics'].items():
            integrity_check['total_messages'] += topic_info['count']

            # 检查空话题
            if topic_info['count'] == 0:
                integrity_check['empty_topics'].append(topic_name)
                integrity_check['issues'].append(f"话题 {topic_name} 没有消息")

            # 检查低频话题（<1Hz）
            if topic_info.get('duration'):
                frequency = topic_info['count'] / topic_info['duration']
                if frequency < 1.0:
                    integrity_check['low_frequency_topics'].append({
                        'topic': topic_name,
                        'frequency': frequency
                    })

        # 检查元数据
        metadata_path = self.episode_path / "metadata.json"
        if not metadata_path.exists():
            integrity_check['issues'].append("缺少metadata.json")

        # 检查同步报告
        sync_report_path = self.episode_path / "sync_validation_report.json"
        if not sync_report_path.exists():
            integrity_check['issues'].append("缺少sync_validation_report.json")

        integrity_check['is_valid'] = len(integrity_check['issues']) == 0

        print(f"  ✓ 完整性检查完成，发现 {len(integrity_check['issues'])} 个问题")
        return integrity_check

    def visualize_frequency(self, frequency_analysis: dict):
        """
        可视化频率分析

        Args:
            frequency_analysis: 频率分析结果
        """
        print("生成频率分析图表...")

        if not frequency_analysis:
            print("  ⚠️  没有频率数据")
            return

        fig, ax = plt.subplots(figsize=(12, 6))

        topics = list(frequency_analysis.keys())
        frequencies = [data['frequency'] for data in frequency_analysis.values()]

        # 缩短话题名称
        short_topics = [t.split('/')[-1] if '/' in t else t for t in topics]

        bars = ax.bar(range(len(topics)), frequencies)

        # 根据频率着色
        for i, (bar, freq) in enumerate(zip(bars, frequencies)):
            if freq >= 25:
                bar.set_color('green')
            elif freq >= 10:
                bar.set_color('orange')
            else:
                bar.set_color('red')

        ax.set_xlabel('话题')
        ax.set_ylabel('频率 (Hz)')
        ax.set_title('话题频率分析')
        ax.set_xticks(range(len(topics)))
        ax.set_xticklabels(short_topics, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3)

        # 添加频率标签
        for i, freq in enumerate(frequencies):
            ax.text(i, freq, f'{freq:.1f}', ha='center', va='bottom')

        plt.tight_layout()

        output_path = self.output_dir / "frequency_analysis.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"  ✓ 图表已保存: {output_path}")

    def visualize_trajectory(self):
        """
        可视化轨迹数据
        """
        print("生成轨迹可视化...")

        # 查找关节状态话题
        topics = self.reader.get_topics()
        joint_topics = [t for t in topics.keys() if 'joint' in t.lower()]

        if not joint_topics:
            print("  ⚠️  没有找到关节话题")
            return

        fig, axes = plt.subplots(len(joint_topics), 1, figsize=(12, 4 * len(joint_topics)))
        if len(joint_topics) == 1:
            axes = [axes]

        for ax, topic in zip(axes, joint_topics):
            data, timestamps = self.reader.read_topic(topic)

            if data is None:
                continue

            # 绘制每个关节的轨迹
            for i in range(data.shape[1]):
                ax.plot(timestamps, data[:, i], label=f'Joint {i+1}', alpha=0.7)

            ax.set_xlabel('时间 (秒)')
            ax.set_ylabel('位置 (rad)')
            ax.set_title(f'{topic}')
            ax.legend(loc='upper right', ncol=3)
            ax.grid(alpha=0.3)

        plt.tight_layout()

        output_path = self.output_dir / "trajectory_visualization.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"  ✓ 图表已保存: {output_path}")

    def generate_report(
        self,
        frequency_analysis: dict,
        sync_results: dict,
        integrity_check: dict
    ):
        """
        生成分析报告

        Args:
            frequency_analysis: 频率分析结果
            sync_results: 时间同步结果
            integrity_check: 完整性检查结果
        """
        print("生成分析报告...")

        report = {
            'episode_path': str(self.episode_path),
            'analyzed_at': datetime.now().isoformat(),
            'frequency_analysis': frequency_analysis,
            'time_sync': sync_results,
            'integrity_check': integrity_check,
            'summary': {
                'total_topics': len(frequency_analysis),
                'sync_quality': sync_results.get('quality_grade', 'N/A'),
                'is_valid': integrity_check.get('is_valid', False),
                'issues_count': len(integrity_check.get('issues', []))
            }
        }

        # 保存JSON报告
        json_path = self.output_dir / "analysis_report.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 生成Markdown报告
        md_path = self.output_dir / "analysis_report.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Episode分析报告\n\n")
            f.write(f"**Episode**: {self.episode_path.name}\n")
            f.write(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write(f"## 摘要\n\n")
            f.write(f"- 话题数量: {report['summary']['total_topics']}\n")
            f.write(f"- 时间同步质量: {report['summary']['sync_quality']}\n")
            f.write(f"- 数据完整性: {'✅ 通过' if report['summary']['is_valid'] else '❌ 失败'}\n")
            f.write(f"- 问题数量: {report['summary']['issues_count']}\n\n")

            f.write(f"## 频率分析\n\n")
            f.write(f"| 话题 | 频率 (Hz) | 消息数 | 时长 (秒) |\n")
            f.write(f"|------|-----------|--------|----------|\n")
            for topic, data in frequency_analysis.items():
                f.write(f"| {topic} | {data['frequency']:.2f} | {data['count']} | {data['duration']:.2f} |\n")

            if sync_results:
                f.write(f"\n## 时间同步分析\n\n")
                f.write(f"**参考话题**: {sync_results.get('ref_topic', 'N/A')}\n\n")
                for target, comp in sync_results.get('comparisons', {}).items():
                    f.write(f"### {target}\n\n")
                    f.write(f"- 中位数时间差: {comp['median_diff']*1000:.2f} ms\n")
                    f.write(f"- 最大时间差: {comp['max_diff']*1000:.2f} ms\n")
                    f.write(f"- 同步成功率 (<33ms): {comp['good_rate']*100:.1f}%\n\n")

            if integrity_check.get('issues'):
                f.write(f"\n## 数据完整性问题\n\n")
                for issue in integrity_check['issues']:
                    f.write(f"- ⚠️  {issue}\n")

            f.write(f"\n## 可视化\n\n")
            f.write(f"- [频率分析图表](frequency_analysis.png)\n")
            f.write(f"- [轨迹可视化](trajectory_visualization.png)\n")

        print(f"  ✓ 报告已保存:")
        print(f"    - JSON: {json_path}")
        print(f"    - Markdown: {md_path}")

    def run_full_analysis(self):
        """运行完整分析"""
        print("=" * 80)
        print("Episode完整分析")
        print("=" * 80)
        print(f"Episode: {self.episode_path}")
        print(f"输出目录: {self.output_dir}")
        print()

        # 1. 频率分析
        frequency_analysis = self.analyze_frequency()
        print()

        # 2. 时间同步分析
        sync_results = self.analyze_time_sync()
        print()

        # 3. 完整性检查
        integrity_check = self.check_data_integrity()
        print()

        # 4. 可视化
        self.visualize_frequency(frequency_analysis)
        self.visualize_trajectory()
        print()

        # 5. 生成报告
        self.generate_report(frequency_analysis, sync_results, integrity_check)
        print()

        print("=" * 80)
        print("分析完成！")
        print("=" * 80)
        print()
        print(f"查看报告: cat {self.output_dir}/analysis_report.md")
        print(f"查看图表: ls {self.output_dir}/*.png")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Episode分析工具")
    parser.add_argument('episode_path', help='Episode目录路径')
    parser.add_argument('--output', help='输出目录（可选）')

    args = parser.parse_args()

    try:
        analyzer = EpisodeAnalyzer(args.episode_path, args.output)
        analyzer.run_full_analysis()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
