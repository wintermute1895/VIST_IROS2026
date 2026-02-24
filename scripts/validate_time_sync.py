#!/usr/bin/env python3
"""
时间同步验证脚本

功能：
1. 验证rosbag中多个话题的时间同步质量
2. 计算不同话题之间的时间差
3. 生成同步质量报告和评级
4. 检测潜在的时间戳问题

用法：
    python scripts/validate_time_sync.py <rosbag_path>
    python scripts/validate_time_sync.py data/recordings/rec_20260224_122434/rosbag
"""

import sys
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import json

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from analysis.core.rosbag_reader import RosbagReader


class TimeSyncValidator:
    """时间同步验证器"""

    # 同步质量阈值（秒）
    EXCELLENT_THRESHOLD = 0.010  # 10ms - 优秀
    GOOD_THRESHOLD = 0.033       # 33ms - 良好（一帧）
    ACCEPTABLE_THRESHOLD = 0.100 # 100ms - 可接受
    POOR_THRESHOLD = 0.200       # 200ms - 较差

    def __init__(self, rosbag_path: str):
        """
        初始化验证器

        Args:
            rosbag_path: rosbag目录路径
        """
        self.rosbag_path = Path(rosbag_path)
        self.reader = RosbagReader(rosbag_path)
        self.topics_data: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    def load_topics(self, topics: List[str] = None):
        """
        加载话题数据

        Args:
            topics: 要加载的话题列表，None表示加载所有话题
        """
        available_topics = self.reader.get_topics()

        if topics is None:
            topics = list(available_topics.keys())

        print(f"正在加载 {len(topics)} 个话题的数据...")

        for topic in topics:
            if topic not in available_topics:
                print(f"  ⚠️  话题 {topic} 不存在，跳过")
                continue

            data, timestamps = self.reader.read_topic(topic)

            if data is None or timestamps is None:
                print(f"  ⚠️  话题 {topic} 无法读取，跳过")
                continue

            self.topics_data[topic] = (data, timestamps)
            print(f"  ✓ {topic}: {len(timestamps)} 条消息")

        print(f"\n成功加载 {len(self.topics_data)} 个话题\n")

    def find_nearest_timestamps(self, ref_topic: str, target_topics: List[str]) -> Dict:
        """
        找到与参考话题时间戳最接近的其他话题时间戳

        Args:
            ref_topic: 参考话题（通常是相机话题）
            target_topics: 目标话题列表（通常是控制话题）

        Returns:
            同步分析结果字典
        """
        if ref_topic not in self.topics_data:
            raise ValueError(f"参考话题 {ref_topic} 未加载")

        _, ref_timestamps = self.topics_data[ref_topic]

        results = {
            'ref_topic': ref_topic,
            'ref_count': len(ref_timestamps),
            'comparisons': {}
        }

        for target_topic in target_topics:
            if target_topic not in self.topics_data:
                print(f"  ⚠️  目标话题 {target_topic} 未加载，跳过")
                continue

            _, target_timestamps = self.topics_data[target_topic]

            # 对每个参考时间戳，找到最近的目标时间戳
            time_diffs = []

            for ref_ts in ref_timestamps:
                # 找到最接近的目标时间戳
                idx = np.searchsorted(target_timestamps, ref_ts)

                # 检查前后两个时间戳，选择更近的
                candidates = []
                if idx > 0:
                    candidates.append(target_timestamps[idx - 1])
                if idx < len(target_timestamps):
                    candidates.append(target_timestamps[idx])

                if candidates:
                    nearest_ts = min(candidates, key=lambda t: abs(t - ref_ts))
                    time_diff = abs(ref_ts - nearest_ts)
                    time_diffs.append(time_diff)

            time_diffs = np.array(time_diffs)

            # 计算统计信息
            results['comparisons'][target_topic] = {
                'target_count': len(target_timestamps),
                'matched_count': len(time_diffs),
                'mean_diff': float(np.mean(time_diffs)),
                'median_diff': float(np.median(time_diffs)),
                'max_diff': float(np.max(time_diffs)),
                'min_diff': float(np.min(time_diffs)),
                'std_diff': float(np.std(time_diffs)),
                'p95_diff': float(np.percentile(time_diffs, 95)),
                'p99_diff': float(np.percentile(time_diffs, 99)),
            }

            # 计算同步成功率（不同阈值）
            for threshold_name, threshold_value in [
                ('excellent', self.EXCELLENT_THRESHOLD),
                ('good', self.GOOD_THRESHOLD),
                ('acceptable', self.ACCEPTABLE_THRESHOLD),
                ('poor', self.POOR_THRESHOLD)
            ]:
                success_rate = np.sum(time_diffs <= threshold_value) / len(time_diffs)
                results['comparisons'][target_topic][f'{threshold_name}_rate'] = float(success_rate)

        return results

    def calculate_quality_grade(self, sync_results: Dict) -> str:
        """
        计算整体同步质量评级

        Args:
            sync_results: 同步分析结果

        Returns:
            质量评级 (A/B/C/D/F)
        """
        if not sync_results['comparisons']:
            return 'F'

        # 使用中位数时间差作为主要指标
        median_diffs = [
            comp['median_diff']
            for comp in sync_results['comparisons'].values()
        ]

        avg_median_diff = np.mean(median_diffs)

        # 评级标准
        if avg_median_diff <= self.EXCELLENT_THRESHOLD:
            return 'A'  # 优秀：<10ms
        elif avg_median_diff <= self.GOOD_THRESHOLD:
            return 'B'  # 良好：<33ms
        elif avg_median_diff <= self.ACCEPTABLE_THRESHOLD:
            return 'C'  # 可接受：<100ms
        elif avg_median_diff <= self.POOR_THRESHOLD:
            return 'D'  # 较差：<200ms
        else:
            return 'F'  # 失败：>200ms

    def print_report(self, sync_results: Dict):
        """
        打印同步质量报告

        Args:
            sync_results: 同步分析结果
        """
        print("=" * 80)
        print("时间同步质量报告")
        print("=" * 80)
        print()

        print(f"参考话题: {sync_results['ref_topic']}")
        print(f"参考消息数: {sync_results['ref_count']}")
        print()

        # 计算整体评级
        grade = self.calculate_quality_grade(sync_results)
        grade_emoji = {
            'A': '🟢',
            'B': '🟡',
            'C': '🟠',
            'D': '🔴',
            'F': '⛔'
        }

        print(f"整体质量评级: {grade_emoji.get(grade, '❓')} {grade}")
        print()
        print("-" * 80)

        # 打印每个话题的详细信息
        for target_topic, comp in sync_results['comparisons'].items():
            print(f"\n目标话题: {target_topic}")
            print(f"  消息数: {comp['target_count']}")
            print(f"  匹配数: {comp['matched_count']}")
            print()
            print(f"  时间差统计:")
            print(f"    平均值: {comp['mean_diff']*1000:.2f} ms")
            print(f"    中位数: {comp['median_diff']*1000:.2f} ms")
            print(f"    最小值: {comp['min_diff']*1000:.2f} ms")
            print(f"    最大值: {comp['max_diff']*1000:.2f} ms")
            print(f"    标准差: {comp['std_diff']*1000:.2f} ms")
            print(f"    P95: {comp['p95_diff']*1000:.2f} ms")
            print(f"    P99: {comp['p99_diff']*1000:.2f} ms")
            print()
            print(f"  同步成功率:")
            print(f"    优秀 (<10ms):  {comp['excellent_rate']*100:.1f}%")
            print(f"    良好 (<33ms):  {comp['good_rate']*100:.1f}%")
            print(f"    可接受 (<100ms): {comp['acceptable_rate']*100:.1f}%")
            print(f"    较差 (<200ms): {comp['poor_rate']*100:.1f}%")
            print()

            # 给出建议
            if comp['median_diff'] <= self.EXCELLENT_THRESHOLD:
                print(f"  ✅ 同步质量优秀，适合用于训练")
            elif comp['median_diff'] <= self.GOOD_THRESHOLD:
                print(f"  ✅ 同步质量良好，可以用于训练")
            elif comp['median_diff'] <= self.ACCEPTABLE_THRESHOLD:
                print(f"  ⚠️  同步质量可接受，但可能影响训练效果")
            elif comp['median_diff'] <= self.POOR_THRESHOLD:
                print(f"  ⚠️  同步质量较差，建议检查时间戳配置")
            else:
                print(f"  ❌ 同步质量很差，不建议用于训练")

            print("-" * 80)

    def save_report(self, sync_results: Dict, output_path: str = None):
        """
        保存同步质量报告到JSON文件

        Args:
            sync_results: 同步分析结果
            output_path: 输出文件路径，None表示保存到rosbag目录
        """
        if output_path is None:
            output_path = self.rosbag_path.parent / "sync_validation_report.json"
        else:
            output_path = Path(output_path)

        # 添加评级信息
        report = sync_results.copy()
        report['quality_grade'] = self.calculate_quality_grade(sync_results)
        report['rosbag_path'] = str(self.rosbag_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n报告已保存到: {output_path}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python validate_time_sync.py <rosbag_path> [ref_topic] [target_topics...]")
        print()
        print("示例:")
        print("  python validate_time_sync.py data/recordings/rec_20260224_122434/rosbag")
        print("  python validate_time_sync.py data/recordings/rec_20260224_122434/rosbag /camera/color /joint_states")
        sys.exit(1)

    rosbag_path = sys.argv[1]

    # 创建验证器
    validator = TimeSyncValidator(rosbag_path)

    # 如果指定了话题，使用指定的话题
    if len(sys.argv) >= 3:
        ref_topic = sys.argv[2]
        target_topics = sys.argv[3:] if len(sys.argv) > 3 else []

        # 加载指定话题
        all_topics = [ref_topic] + target_topics
        validator.load_topics(all_topics)

        if not target_topics:
            # 如果没有指定目标话题，使用除参考话题外的所有话题
            target_topics = [t for t in validator.topics_data.keys() if t != ref_topic]

    else:
        # 自动检测话题
        print("未指定话题，自动检测...")
        validator.load_topics()

        # 尝试找到相机话题作为参考
        camera_topics = [t for t in validator.topics_data.keys() if 'camera' in t.lower() or 'image' in t.lower()]

        if camera_topics:
            ref_topic = camera_topics[0]
            print(f"使用 {ref_topic} 作为参考话题")
        else:
            # 使用第一个话题作为参考
            ref_topic = list(validator.topics_data.keys())[0]
            print(f"未找到相机话题，使用 {ref_topic} 作为参考话题")

        target_topics = [t for t in validator.topics_data.keys() if t != ref_topic]

    if not target_topics:
        print("错误: 没有找到目标话题进行比较")
        sys.exit(1)

    print(f"\n开始分析时间同步...")
    print(f"参考话题: {ref_topic}")
    print(f"目标话题: {', '.join(target_topics)}")
    print()

    # 执行同步分析
    sync_results = validator.find_nearest_timestamps(ref_topic, target_topics)

    # 打印报告
    validator.print_report(sync_results)

    # 保存报告
    validator.save_report(sync_results)


if __name__ == '__main__':
    main()

