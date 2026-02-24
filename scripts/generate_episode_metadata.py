#!/usr/bin/env python3
"""
Episode元数据生成器

功能：
1. 为现有rosbag录制生成Episode元数据
2. 自动提取录制信息（时长、消息数、话题等）
3. 生成标准化的metadata.json文件
4. 支持批量处理多个录制

用法：
    python scripts/generate_episode_metadata.py <rosbag_path>
    python scripts/generate_episode_metadata.py data/recordings/rec_20260224_122434/rosbag
    python scripts/generate_episode_metadata.py data/recordings --batch  # 批量处理
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from analysis.core.rosbag_reader import RosbagReader


class EpisodeMetadataGenerator:
    """Episode元数据生成器"""

    def __init__(self, rosbag_path: str):
        """
        初始化生成器

        Args:
            rosbag_path: rosbag目录路径
        """
        self.rosbag_path = Path(rosbag_path)
        self.reader = RosbagReader(rosbag_path)

    def extract_timestamp_from_path(self) -> Optional[str]:
        """
        从路径中提取时间戳

        Returns:
            ISO格式时间戳字符串，如果无法提取则返回None
        """
        # 尝试从目录名提取时间戳（格式：rec_YYYYMMDD_HHMMSS）
        parent_dir = self.rosbag_path.parent.name

        if parent_dir.startswith('rec_'):
            parts = parent_dir.split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS

                try:
                    # 解析时间戳
                    dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                    return dt.isoformat()
                except ValueError:
                    pass

        return None

    def generate_metadata(self, task_name: str = None, quality_score: str = None) -> Dict:
        """
        生成Episode元数据

        Args:
            task_name: 任务名称（可选）
            quality_score: 质量评分（可选，A/B/C/D/F）

        Returns:
            元数据字典
        """
        # 获取rosbag信息
        info = self.reader.get_info()

        # 提取基本信息
        episode_id = self.rosbag_path.parent.name
        timestamp = self.extract_timestamp_from_path()

        # 计算总时长和消息数
        total_duration = 0
        total_messages = 0
        topics_info = {}

        for topic_name, topic_data in info['topics'].items():
            total_messages += topic_data['count']

            if topic_data.get('duration'):
                total_duration = max(total_duration, topic_data['duration'])

            topics_info[topic_name] = {
                'type': topic_data['type'],
                'count': topic_data['count'],
                'frequency': topic_data['count'] / topic_data['duration'] if topic_data.get('duration') else 0
            }

        # 构建元数据
        metadata = {
            'episode_id': episode_id,
            'format': 'rosbag2',
            'timestamp': timestamp or datetime.now().isoformat(),
            'task_name': task_name or 'unknown',
            'duration_sec': round(total_duration, 2),
            'total_messages': total_messages,
            'db_files': info['db_files'],
            'topics': topics_info,
            'rosbag_path': str(self.rosbag_path),
            'generated_at': datetime.now().isoformat()
        }

        # 添加质量评分（如果提供）
        if quality_score:
            metadata['quality_score'] = quality_score

        return metadata

    def save_metadata(self, metadata: Dict, output_path: str = None):
        """
        保存元数据到JSON文件

        Args:
            metadata: 元数据字典
            output_path: 输出文件路径，None表示保存到rosbag父目录
        """
        if output_path is None:
            output_path = self.rosbag_path.parent / "metadata.json"
        else:
            output_path = Path(output_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"✓ 元数据已保存到: {output_path}")

    def print_metadata(self, metadata: Dict):
        """
        打印元数据摘要

        Args:
            metadata: 元数据字典
        """
        print("=" * 80)
        print("Episode元数据")
        print("=" * 80)
        print()
        print(f"Episode ID: {metadata['episode_id']}")
        print(f"任务名称: {metadata['task_name']}")
        print(f"时间戳: {metadata['timestamp']}")
        print(f"时长: {metadata['duration_sec']:.2f} 秒")
        print(f"总消息数: {metadata['total_messages']}")
        print(f"数据库文件数: {metadata['db_files']}")

        if 'quality_score' in metadata:
            print(f"质量评分: {metadata['quality_score']}")

        print()
        print(f"话题信息 ({len(metadata['topics'])} 个话题):")
        print()

        for topic_name, topic_info in metadata['topics'].items():
            print(f"  {topic_name}")
            print(f"    类型: {topic_info['type']}")
            print(f"    消息数: {topic_info['count']}")
            print(f"    频率: {topic_info['frequency']:.2f} Hz")
            print()


def process_single_rosbag(rosbag_path: str, task_name: str = None, quality_score: str = None):
    """
    处理单个rosbag

    Args:
        rosbag_path: rosbag目录路径
        task_name: 任务名称（可选）
        quality_score: 质量评分（可选）
    """
    print(f"正在处理: {rosbag_path}")
    print()

    try:
        generator = EpisodeMetadataGenerator(rosbag_path)
        metadata = generator.generate_metadata(task_name, quality_score)
        generator.print_metadata(metadata)
        generator.save_metadata(metadata)
        print()
        return True

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        print()
        return False


def process_batch(recordings_dir: str, task_name: str = None):
    """
    批量处理多个录制

    Args:
        recordings_dir: 录制目录路径
        task_name: 任务名称（可选）
    """
    recordings_path = Path(recordings_dir)

    if not recordings_path.exists():
        print(f"错误: 目录不存在: {recordings_dir}")
        sys.exit(1)

    # 查找所有rosbag目录
    rosbag_dirs = []

    for rec_dir in recordings_path.iterdir():
        if rec_dir.is_dir():
            # 检查是否包含rosbag子目录
            rosbag_subdir = rec_dir / "rosbag"
            if rosbag_subdir.exists() and rosbag_subdir.is_dir():
                rosbag_dirs.append(rosbag_subdir)
            # 或者直接是rosbag目录（包含.db3文件）
            elif list(rec_dir.glob("*.db3")):
                rosbag_dirs.append(rec_dir)

    if not rosbag_dirs:
        print(f"错误: 在 {recordings_dir} 中未找到rosbag目录")
        sys.exit(1)

    print(f"找到 {len(rosbag_dirs)} 个rosbag目录")
    print()

    success_count = 0
    fail_count = 0

    for rosbag_dir in rosbag_dirs:
        if process_single_rosbag(str(rosbag_dir), task_name):
            success_count += 1
        else:
            fail_count += 1

    print("=" * 80)
    print("批量处理完成")
    print("=" * 80)
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总计: {len(rosbag_dirs)}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python generate_episode_metadata.py <rosbag_path> [options]")
        print()
        print("选项:")
        print("  --batch              批量处理模式")
        print("  --task <name>        指定任务名称")
        print("  --quality <score>    指定质量评分 (A/B/C/D/F)")
        print()
        print("示例:")
        print("  python generate_episode_metadata.py data/recordings/rec_20260224_122434/rosbag")
        print("  python generate_episode_metadata.py data/recordings/rec_20260224_122434/rosbag --task pick_and_place")
        print("  python generate_episode_metadata.py data/recordings --batch --task demo")
        sys.exit(1)

    path = sys.argv[1]

    # 解析选项
    batch_mode = '--batch' in sys.argv
    task_name = None
    quality_score = None

    if '--task' in sys.argv:
        task_idx = sys.argv.index('--task')
        if task_idx + 1 < len(sys.argv):
            task_name = sys.argv[task_idx + 1]

    if '--quality' in sys.argv:
        quality_idx = sys.argv.index('--quality')
        if quality_idx + 1 < len(sys.argv):
            quality_score = sys.argv[quality_idx + 1]

    # 执行处理
    if batch_mode:
        process_batch(path, task_name)
    else:
        process_single_rosbag(path, task_name, quality_score)


if __name__ == '__main__':
    main()