#!/usr/bin/env python3
"""
重新生成 rosbag2 metadata.yaml 文件
当 metadata.yaml 被意外覆盖时使用
"""

import sys
import sqlite3
from pathlib import Path
import yaml


def get_topics_from_db(db_path):
    """从 sqlite3 数据库中提取话题信息"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取话题信息
    cursor.execute("""
        SELECT id, name, type, serialization_format, offered_qos_profiles
        FROM topics
    """)
    topics = cursor.fetchall()

    # 获取消息数量
    topic_message_counts = {}
    for topic_id, name, _, _, _ in topics:
        cursor.execute("""
            SELECT COUNT(*) FROM messages WHERE topic_id = ?
        """, (topic_id,))
        count = cursor.fetchone()[0]
        topic_message_counts[topic_id] = count

    conn.close()
    return topics, topic_message_counts


def generate_metadata(bag_dir):
    """生成 rosbag2 metadata.yaml"""
    bag_path = Path(bag_dir)

    # 查找 db3 文件
    db_files = list(bag_path.glob("*.db3"))
    if not db_files:
        print(f"错误: 在 {bag_dir} 中未找到 .db3 文件")
        sys.exit(1)

    db_file = db_files[0]
    print(f"分析数据库: {db_file.name}")

    # 从数据库提取信息
    topics, topic_message_counts = get_topics_from_db(str(db_file))

    # 构建 metadata
    metadata = {
        'rosbag2_bagfile_information': {
            'version': 9,  # ROS2 Humble 使用版本 9
            'storage_identifier': 'sqlite3',
            'relative_file_paths': [db_file.name],
            'duration': {
                'nanoseconds': 0  # 需要从数据库计算
            },
            'starting_time': {
                'nanoseconds_since_epoch': 0  # 需要从数据库计算
            },
            'message_count': sum(topic_message_counts.values()),
            'topics_with_message_count': [],
            'compression_format': '',
            'compression_mode': '',
            'files': [
                {
                    'path': db_file.name,
                    'starting_time': {
                        'nanoseconds_since_epoch': 0
                    },
                    'duration': {
                        'nanoseconds': 0
                    },
                    'message_count': sum(topic_message_counts.values())
                }
            ]
        }
    }

    # 添加话题信息
    for topic_id, name, msg_type, serialization, qos in topics:
        topic_info = {
            'topic_metadata': {
                'name': name,
                'type': msg_type,
                'serialization_format': serialization,
                'offered_qos_profiles': qos if qos else ''
            },
            'message_count': topic_message_counts[topic_id]
        }
        metadata['rosbag2_bagfile_information']['topics_with_message_count'].append(topic_info)

    # 从数据库获取时间信息
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages")
    min_time, max_time = cursor.fetchone()
    conn.close()

    if min_time and max_time:
        metadata['rosbag2_bagfile_information']['starting_time']['nanoseconds_since_epoch'] = min_time
        metadata['rosbag2_bagfile_information']['duration']['nanoseconds'] = max_time - min_time
        metadata['rosbag2_bagfile_information']['files'][0]['starting_time']['nanoseconds_since_epoch'] = min_time
        metadata['rosbag2_bagfile_information']['files'][0]['duration']['nanoseconds'] = max_time - min_time

    # 写入 metadata.yaml
    metadata_path = bag_path / 'metadata.yaml'
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)

    print(f"✓ 已生成 metadata.yaml")
    print(f"  话题数量: {len(topics)}")
    print(f"  消息总数: {sum(topic_message_counts.values())}")
    print(f"  时长: {(max_time - min_time) / 1e9:.2f} 秒")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 regenerate_metadata.py <bag_directory>")
        sys.exit(1)

    generate_metadata(sys.argv[1])