"""
RosbagReader - 统一的rosbag读取模块

功能：
1. 直接读取sqlite数据库，不依赖ROS2环境
2. 自动检测消息类型
3. 支持多种消息格式（JointState, FollowJoint等）
4. 提供统一的数据接口
"""
import sqlite3
import struct
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import json


class RosbagReader:
    """统一的rosbag读取器"""

    def __init__(self, rosbag_path: str):
        """
        初始化rosbag读取器

        Args:
            rosbag_path: rosbag目录路径
        """
        self.rosbag_path = Path(rosbag_path)
        self.db_files = self._find_db_files()

        if not self.db_files:
            raise FileNotFoundError(f"在 {rosbag_path} 中未找到数据库文件")

    def _find_db_files(self) -> List[Path]:
        """查找所有数据库文件"""
        return sorted(self.rosbag_path.glob("*.db3"))

    def get_topics(self) -> Dict[str, str]:
        """
        获取所有可用话题

        Returns:
            {topic_name: message_type} 字典
        """
        topics = {}
        conn = sqlite3.connect(str(self.db_files[0]))
        cursor = conn.cursor()

        cursor.execute("SELECT name, type FROM topics")
        for name, msg_type in cursor.fetchall():
            topics[name] = msg_type

        conn.close()
        return topics

    def read_topic(self, topic_name: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        读取指定话题的数据

        Args:
            topic_name: 话题名称

        Returns:
            (trajectory, timestamps) 元组
            - trajectory: (N, M) 数组，N是样本数，M是关节数
            - timestamps: (N,) 数组，时间戳（秒）
        """
        all_positions = []
        all_timestamps = []

        for db_file in self.db_files:
            positions, timestamps = self._read_from_db(db_file, topic_name)
            if positions is not None:
                all_positions.extend(positions)
                all_timestamps.extend(timestamps)

        if not all_positions:
            return None, None

        trajectory = np.array(all_positions)
        timestamps = np.array(all_timestamps)

        return trajectory, timestamps

    def _read_from_db(self, db_file: Path, topic_name: str) -> Tuple[List, List]:
        """从单个数据库文件读取数据"""
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # 获取话题ID和类型
        cursor.execute("SELECT id, type FROM topics WHERE name = ?", (topic_name,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return [], []

        topic_id, msg_type = result

        # 读取消息
        cursor.execute("""
            SELECT timestamp, data
            FROM messages
            WHERE topic_id = ?
            ORDER BY timestamp
        """, (topic_id,))

        positions = []
        timestamps = []

        for timestamp, data in cursor.fetchall():
            try:
                # 解析消息数据
                parsed_data = self._parse_message(data, msg_type)
                if parsed_data is not None:
                    positions.append(parsed_data)
                    timestamps.append(timestamp / 1e9)  # 转换为秒
            except Exception:
                # 静默跳过解析错误
                continue

        conn.close()
        return positions, timestamps

    def _parse_message(self, data: bytes, msg_type: str) -> Optional[np.ndarray]:
        """
        解析消息数据

        支持的消息类型：
        - sensor_msgs/msg/JointState
        - lbot_arm_interfaces/msg/FollowJoint
        """
        try:
            if 'JointState' in msg_type:
                return self._parse_joint_state(data)
            elif 'FollowJoint' in msg_type:
                return self._parse_follow_joint(data)
            else:
                return None
        except Exception:
            return None

    def _parse_joint_state(self, data: bytes) -> Optional[np.ndarray]:
        """
        解析JointState消息

        JointState格式（简化）：
        - CDR header (4 bytes) - 跳过
        - header (跳过)
        - name[] (跳过)
        - position[] (我们需要的)
        - velocity[] (跳过)
        - effort[] (跳过)
        """
        try:
            offset = 0

            # 跳过CDR头部（4字节）
            offset += 4

            # 跳过header（时间戳 + frame_id）
            # stamp: int32 sec + uint32 nanosec = 8 bytes
            offset += 8
            # frame_id: uint32 length + string
            frame_id_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4 + frame_id_len
            # 对齐到4字节边界
            if frame_id_len % 4 != 0:
                offset += 4 - (frame_id_len % 4)

            # 跳过name数组
            name_count = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            for _ in range(name_count):
                name_len = struct.unpack_from('<I', data, offset)[0]
                offset += 4 + name_len
                # 对齐到4字节边界
                if name_len % 4 != 0:
                    offset += 4 - (name_len % 4)

            # 读取position数组
            position_count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            if position_count == 0:
                return None

            positions = struct.unpack_from(f'<{position_count}d', data, offset)
            return np.array(positions)

        except Exception as e:
            # 调试：打印错误信息
            # print(f"解析JointState失败: {e}")
            return None

    def _parse_follow_joint(self, data: bytes) -> Optional[np.ndarray]:
        """
        解析FollowJoint消息

        FollowJoint格式：
        - CDR header (4 bytes) - 跳过
        - joints[] (double数组)
        """
        try:
            offset = 0

            # 跳过CDR头部（4字节）
            offset += 4

            # 读取joints数组长度
            joint_count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            if joint_count == 0:
                return None

            # 读取joints数据
            joints = struct.unpack_from(f'<{joint_count}d', data, offset)
            return np.array(joints)

        except Exception as e:
            # 调试：打印错误信息
            # print(f"解析FollowJoint失败: {e}")
            return None

    def get_info(self) -> Dict:
        """
        获取rosbag信息

        Returns:
            包含话题、消息数、时长等信息的字典
        """
        info = {
            'db_files': len(self.db_files),
            'topics': {}
        }

        for db_file in self.db_files:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # 获取话题信息
            cursor.execute("SELECT id, name, type FROM topics")
            for topic_id, name, msg_type in cursor.fetchall():
                if name not in info['topics']:
                    info['topics'][name] = {
                        'type': msg_type,
                        'count': 0,
                        'start_time': None,
                        'end_time': None
                    }

                # 获取消息数量
                cursor.execute("SELECT COUNT(*) FROM messages WHERE topic_id = ?", (topic_id,))
                count = cursor.fetchone()[0]
                info['topics'][name]['count'] += count

                # 获取时间范围
                cursor.execute("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM messages WHERE topic_id = ?
                """, (topic_id,))
                min_ts, max_ts = cursor.fetchone()

                if min_ts and max_ts:
                    if info['topics'][name]['start_time'] is None:
                        info['topics'][name]['start_time'] = min_ts / 1e9
                    else:
                        info['topics'][name]['start_time'] = min(
                            info['topics'][name]['start_time'], min_ts / 1e9
                        )

                    if info['topics'][name]['end_time'] is None:
                        info['topics'][name]['end_time'] = max_ts / 1e9
                    else:
                        info['topics'][name]['end_time'] = max(
                            info['topics'][name]['end_time'], max_ts / 1e9
                        )

            conn.close()

        # 计算时长
        for topic_info in info['topics'].values():
            if topic_info['start_time'] and topic_info['end_time']:
                topic_info['duration'] = topic_info['end_time'] - topic_info['start_time']

        return info


if __name__ == '__main__':
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python rosbag_reader.py <rosbag_path>")
        sys.exit(1)

    reader = RosbagReader(sys.argv[1])

    print("=" * 60)
    print("Rosbag信息")
    print("=" * 60)

    info = reader.get_info()
    print(f"数据库文件数: {info['db_files']}")
    print(f"\n话题列表:")

    for topic_name, topic_info in info['topics'].items():
        print(f"\n  {topic_name}")
        print(f"    类型: {topic_info['type']}")
        print(f"    消息数: {topic_info['count']}")
        if topic_info.get('duration'):
            print(f"    时长: {topic_info['duration']:.2f} 秒")
            print(f"    频率: {topic_info['count'] / topic_info['duration']:.2f} Hz")