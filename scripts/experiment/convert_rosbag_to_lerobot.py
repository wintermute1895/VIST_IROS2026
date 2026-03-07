#!/usr/bin/env python3
"""
将 ROS 2 bag (.db3) 文件转换为 LeRobotDataset 格式
集成"硬丢弃(Hard Reject)"时间对齐算法

使用方法:
    python convert_rosbag_to_lerobot.py \
        --bag-path /path/to/your/rosbag \
        --repo-id your_username/your_dataset_name \
        --fps 30 \
        --robot-type your_robot_type

依赖安装:
    pip install rosbags opencv-python numpy pillow lerobot tqdm
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional
import shutil
import yaml

import cv2
import numpy as np
from PIL import Image
from rosbags.rosbag2 import Reader
from rosbags.typesys import get_typestore, Stores
from tqdm import tqdm

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.utils.constants import HF_LEROBOT_HOME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# 全局配置：硬丢弃对齐算法参数
# ========================================
MAX_SYNC_DELTA = 0.04  # 最大允许时间偏差 (秒)，超过此值则丢弃该帧


def parse_args():
    parser = argparse.ArgumentParser(description="Convert ROS 2 bag to LeRobotDataset with Hard Reject alignment")
    parser.add_argument("--bag-path", type=str, help="Path to single ROS 2 bag directory (for single conversion)")
    parser.add_argument("--input-dir", type=str, help="Path to directory containing multiple experiment folders (for batch conversion)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: ~/.cache/huggingface/lerobot)")
    parser.add_argument("--repo-id", type=str, help="Dataset repo ID (e.g., username/dataset_name). For batch mode, will append experiment name")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second (default: 30)")
    parser.add_argument("--robot-type", type=str, default="vist_dual_arm", help="Robot type name")

    # Topic 配置（更新为双D435i相机系统）
    parser.add_argument("--state-topic", type=str, default="/joint_states", help="Joint state topic")
    parser.add_argument("--action-topic", type=str, default="/action", help="Action/command topic")
    parser.add_argument("--cam-global-topic", type=str,
                       default="/camera_global/camera_global/color/image_raw",
                       help="Global camera topic (baseline for alignment)")
    parser.add_argument("--cam-wrist-topic", type=str,
                       default="/camera_wrist/camera_wrist/color/image_raw",
                       help="Wrist camera topic")

    # 数据维度配置
    parser.add_argument("--state-dim", type=int, default=7, help="State dimension (e.g., 7 for 7-DOF arm)")
    parser.add_argument("--action-dim", type=int, default=7, help="Action dimension")
    parser.add_argument("--task-name", type=str, default="grab", help="Task name for the dataset (default: grab)")

    # 对齐算法配置
    parser.add_argument("--max-sync-delta", type=float, default=0.04,
                       help="Maximum time delta for synchronization (seconds, default: 0.04)")

    # Episode分割配置
    parser.add_argument("--episode-split-threshold", type=float, default=2.0,
                       help="Time gap (seconds) to split episodes (default: 2.0, set to 0 to disable)")

    return parser.parse_args()


def extract_timestamp(msg):
    """从 ROS 消息中提取时间戳（秒）"""
    if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
        return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    return None


def ros_image_to_numpy(msg) -> np.ndarray:
    """将 ROS Image 消息转换为 numpy 数组 (RGB 格式)"""
    if msg.encoding == "rgb8":
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
    elif msg.encoding == "bgr8":
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    elif msg.encoding == "mono8":
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    elif msg.encoding in ["compressed", "jpeg"]:
        img = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        logger.warning(f"Unsupported encoding: {msg.encoding}, trying default conversion")
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)

    return img


def extract_joint_positions(msg, num_joints=7):
    """从 JointState 消息中提取前 N 个关节位置"""
    if hasattr(msg, 'position') and len(msg.position) >= num_joints:
        return np.array(msg.position[:num_joints], dtype=np.float32)
    elif hasattr(msg, 'data') and len(msg.data) >= num_joints:
        return np.array(msg.data[:num_joints], dtype=np.float32)
    return None


def find_nearest_neighbor(target_time, timestamps):
    """
    在时间戳序列中找到最接近目标时间的索引

    Returns:
        tuple: (索引, 时间差的绝对值)
    """
    if len(timestamps) == 0:
        return None, float('inf')

    timestamps = np.array(timestamps)
    idx = np.argmin(np.abs(timestamps - target_time))
    time_diff = abs(timestamps[idx] - target_time)

    return idx, time_diff


def load_task_label_from_metadata(bag_path: Path) -> Optional[str]:
    """
    从实验元数据文件中读取任务标签

    Args:
        bag_path: rosbag文件夹路径

    Returns:
        str: 任务标签，如果未找到则返回None
    """
    metadata_path = bag_path / 'experiment_metadata.yaml'

    if not metadata_path.exists():
        logger.warning(f"未找到元数据文件: {metadata_path}")
        return None

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
            task_label = metadata.get('experiment', {}).get('task_label', '')

            if task_label:
                logger.info(f"从元数据读取任务标签: '{task_label}'")
                return task_label
            else:
                logger.warning("元数据中未找到任务标签")
                return None
    except Exception as e:
        logger.warning(f"读取元数据失败: {e}")
        return None
    """
    在时间戳序列中找到最接近目标时间的索引

    Returns:
        tuple: (索引, 时间差的绝对值)
    """
    if len(timestamps) == 0:
        return None, float('inf')

    timestamps = np.array(timestamps)
    idx = np.argmin(np.abs(timestamps - target_time))
    time_diff = abs(timestamps[idx] - target_time)

    return idx, time_diff


def extract_sensor_data_from_bag(
    bag_path: Path,
    state_topic: str,
    action_topic: str,
    cam_global_topic: str,
    cam_wrist_topic: str,
    state_dim: int,
    action_dim: int
):
    """
    从 ROS bag 中提取所有传感器数据（按时间序列组织）

    Returns:
        dict: 包含各传感器时间序列数据的字典
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"[1/3] 正在读取 rosbag: {bag_path}")
    logger.info(f"{'='*70}")

    # 初始化数据容器
    data = {
        'cam_global': {'timestamps': [], 'images': []},
        'cam_wrist': {'timestamps': [], 'images': []},
        'joint_states': {'timestamps': [], 'positions': []},
        'actions': {'timestamps': [], 'positions': []}
    }

    with Reader(bag_path) as reader:
        typestore = get_typestore(Stores.ROS2_HUMBLE)
        connections = list(reader.connections)
        topic_map = {conn.topic: conn for conn in connections}

        logger.info(f"可用话题: {list(topic_map.keys())}")

        # 检查必需话题
        required_topics = [state_topic, action_topic, cam_global_topic, cam_wrist_topic]
        missing_topics = [t for t in required_topics if t not in topic_map]

        if missing_topics:
            logger.warning(f"⚠️  警告: 缺少话题 {missing_topics}")
            raise ValueError(f"Missing required topics: {missing_topics}")

        # 收集所有消息
        all_messages = []
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic in required_topics:
                try:
                    msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
                    all_messages.append((connection.topic, msg))
                except Exception as e:
                    logger.warning(f"Failed to deserialize message from {connection.topic}: {e}")

        logger.info(f"总消息数: {len(all_messages)}")

        # 处理消息并提取数据
        for topic, msg in tqdm(all_messages, desc="  提取传感器数据", unit="msg"):
            # 提取时间戳
            ts = extract_timestamp(msg)
            if ts is None:
                continue

            # 根据话题分类处理
            if topic == cam_global_topic:
                try:
                    img = ros_image_to_numpy(msg)
                    data['cam_global']['timestamps'].append(ts)
                    data['cam_global']['images'].append(img)
                except Exception as e:
                    logger.warning(f"Failed to convert global camera image: {e}")

            elif topic == cam_wrist_topic:
                try:
                    img = ros_image_to_numpy(msg)
                    data['cam_wrist']['timestamps'].append(ts)
                    data['cam_wrist']['images'].append(img)
                except Exception as e:
                    logger.warning(f"Failed to convert wrist camera image: {e}")

            elif topic == state_topic:
                pos = extract_joint_positions(msg, num_joints=state_dim)
                if pos is not None:
                    data['joint_states']['timestamps'].append(ts)
                    data['joint_states']['positions'].append(pos)

            elif topic == action_topic:
                pos = extract_joint_positions(msg, num_joints=action_dim)
                if pos is not None:
                    data['actions']['timestamps'].append(ts)
                    data['actions']['positions'].append(pos)

    # 转换为 numpy 数组
    for key in data:
        data[key]['timestamps'] = np.array(data[key]['timestamps'])
        if key.startswith('cam'):
            if len(data[key]['images']) > 0:
                data[key]['images'] = np.array(data[key]['images'])
        else:
            if len(data[key]['positions']) > 0:
                data[key]['positions'] = np.array(data[key]['positions'])

    # 打印统计信息
    logger.info(f"\n  ✓ 全局相机: {len(data['cam_global']['timestamps'])} 帧")
    logger.info(f"  ✓ 腕部相机: {len(data['cam_wrist']['timestamps'])} 帧")
    logger.info(f"  ✓ 关节状态: {len(data['joint_states']['timestamps'])} 帧")
    logger.info(f"  ✓ 动作指令: {len(data['actions']['timestamps'])} 帧")

    return data


def align_data_with_hard_reject(data, max_sync_delta=MAX_SYNC_DELTA):
    """
    使用"硬丢弃"算法对齐多传感器数据

    以全局相机时间戳为基准，使用最近邻算法匹配其他传感器数据。
    如果任何传感器的时间偏差超过 max_sync_delta，则丢弃该帧。

    Returns:
        list: 对齐后的帧列表，每帧包含所有传感器数据
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"[2/3] 正在对齐数据 (容差阈值: {max_sync_delta*1000:.1f}ms)")
    logger.info(f"{'='*70}")

    # 以全局相机为基准
    base_timestamps = data['cam_global']['timestamps']

    if len(base_timestamps) == 0:
        logger.error("  ❌ 全局相机无数据，无法对齐")
        return []

    aligned_frames = []
    rejected_count = 0

    # 遍历全局相机的每一帧
    for i in tqdm(range(len(base_timestamps)), desc="  对齐帧", unit="frame"):
        base_ts = base_timestamps[i]

        # 查找最近邻
        idx_wrist, diff_wrist = find_nearest_neighbor(base_ts, data['cam_wrist']['timestamps'])
        idx_joint, diff_joint = find_nearest_neighbor(base_ts, data['joint_states']['timestamps'])
        idx_action, diff_action = find_nearest_neighbor(base_ts, data['actions']['timestamps'])

        # 检查是否所有传感器都在容差范围内
        if (diff_wrist > max_sync_delta or
            diff_joint > max_sync_delta or
            diff_action > max_sync_delta):
            rejected_count += 1
            continue

        # 所有传感器都在容差范围内，保存这一组数据
        frame = {
            'timestamp': base_ts,
            'cam_global': data['cam_global']['images'][i],
            'cam_wrist': data['cam_wrist']['images'][idx_wrist],
            'joint_state': data['joint_states']['positions'][idx_joint],
            'action': data['actions']['positions'][idx_action],
        }
        aligned_frames.append(frame)

    # 打印统计信息
    original_count = len(base_timestamps)
    valid_count = len(aligned_frames)

    logger.info(f"\n  📊 对齐统计:")
    logger.info(f"     原始帧数: {original_count}")
    logger.info(f"     保留有效帧数: {valid_count}")
    logger.info(f"     剔除掉帧: {rejected_count}")
    logger.info(f"     保留率: {valid_count/original_count*100:.1f}%")

    return aligned_frames


def split_into_episodes(aligned_frames, split_threshold=2.0):
    """
    根据时间间隔将对齐后的帧分割成多个episodes

    Args:
        aligned_frames: 对齐后的帧列表
        split_threshold: 时间间隔阈值（秒），超过此值则分割为新episode

    Returns:
        list: episodes列表，每个episode是一个帧列表
    """
    if split_threshold <= 0 or len(aligned_frames) == 0:
        # 不分割，整个作为一个episode
        return [aligned_frames]

    episodes = []
    current_episode = []
    last_timestamp = None

    for frame in aligned_frames:
        current_ts = frame['timestamp']

        if last_timestamp is not None and (current_ts - last_timestamp) > split_threshold:
            # 时间间隔超过阈值，保存当前episode并开始新episode
            if len(current_episode) > 0:
                episodes.append(current_episode)
                logger.info(f"  Episode {len(episodes)} 完成: {len(current_episode)} 帧")
            current_episode = []

        current_episode.append(frame)
        last_timestamp = current_ts

    # 保存最后一个episode
    if len(current_episode) > 0:
        episodes.append(current_episode)
        logger.info(f"  Episode {len(episodes)} 完成: {len(current_episode)} 帧")

    logger.info(f"\n  总共分割为 {len(episodes)} 个episodes")
    return episodes


def create_features(state_dim: int, action_dim: int, image_shape=(480, 640, 3)) -> Dict:
    """创建 LeRobotDataset 的 features 定义"""
    features = {
        "observation.state": {
            "dtype": "float32",
            "shape": (state_dim,),
            "names": {
                "axes": [f"joint_{i}" for i in range(state_dim)],
            },
        },
        "action": {
            "dtype": "float32",
            "shape": (action_dim,),
            "names": {
                "axes": [f"joint_{i}" for i in range(action_dim)],
            },
        },
        "observation.images.camera_global": {
            "dtype": "video",
            "shape": image_shape,
            "names": ["height", "width", "channels"],
        },
        "observation.images.camera_wrist": {
            "dtype": "video",
            "shape": image_shape,
            "names": ["height", "width", "channels"],
        },
    }

    return features


def convert_to_lerobot(
    bag_path: str,
    repo_id: str,
    fps: int,
    robot_type: str,
    state_topic: str,
    action_topic: str,
    cam_global_topic: str,
    cam_wrist_topic: str,
    state_dim: int,
    action_dim: int,
    task_name: str = "grab",
    output_dir: Optional[str] = None,
    max_sync_delta: float = MAX_SYNC_DELTA,
    episode_split_threshold: float = 2.0,
):
    """主转换函数"""
    bag_path = Path(bag_path)

    if not bag_path.exists():
        raise FileNotFoundError(f"Bag path not found: {bag_path}")

    # 尝试从元数据读取任务标签（优先级高于命令行参数）
    metadata_task_label = load_task_label_from_metadata(bag_path)
    if metadata_task_label:
        task_name = metadata_task_label
        logger.info(f"使用元数据中的任务标签: '{task_name}'")
    else:
        # 确保 task_name 是字符串
        if isinstance(task_name, list):
            task_name = task_name[0] if task_name else ""
        task_name = str(task_name)
        if task_name:
            logger.info(f"使用命令行指定的任务标签: '{task_name}'")
        else:
            logger.warning("未指定任务标签，使用默认值: 'unknown_task'")

    # 步骤 1: 提取传感器数据
    data = extract_sensor_data_from_bag(
        bag_path,
        state_topic,
        action_topic,
        cam_global_topic,
        cam_wrist_topic,
        state_dim,
        action_dim
    )

    # 步骤 2: 对齐数据（硬丢弃算法）
    aligned_frames = align_data_with_hard_reject(data, max_sync_delta)

    if len(aligned_frames) == 0:
        raise ValueError("No valid frames after alignment. Check your sync threshold or data quality.")

    # 步骤 2.5: 分割episodes
    logger.info(f"\n{'='*70}")
    logger.info(f"[2.5/3] 分割episodes (阈值: {episode_split_threshold}s)")
    logger.info(f"{'='*70}")
    episodes = split_into_episodes(aligned_frames, episode_split_threshold)

    # 获取图像尺寸
    image_shape = episodes[0][0]['cam_global'].shape

    # 创建 features
    features = create_features(state_dim, action_dim, image_shape)

    logger.info(f"\n{'='*70}")
    logger.info(f"[3/3] 正在创建 LeRobotDataset")
    logger.info(f"{'='*70}")
    logger.info(f"Features: {list(features.keys())}")

    # 清理已存在的数据集目录
    dataset_root = Path(output_dir) if output_dir else HF_LEROBOT_HOME / repo_id
    if dataset_root.exists():
        logger.warning(f"数据集目录已存在，正在删除: {dataset_root}")
        shutil.rmtree(dataset_root)

    # 创建 LeRobotDataset
    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        robot_type=robot_type,
        features=features,
        root=output_dir,
        use_videos=True,
    )

    # 添加每个episode
    for ep_idx, episode_frames in enumerate(episodes):
        logger.info(f"\n正在添加 Episode {ep_idx + 1}/{len(episodes)} ({len(episode_frames)} 帧)...")

        for frame_data in tqdm(episode_frames, desc=f"  Episode {ep_idx + 1}", unit="frame"):
            # 构建 LeRobot 格式的帧
            frame = {
                "observation.state": frame_data['joint_state'],
                "action": frame_data['action'],
                "task": task_name,
                "observation.images.camera_global": frame_data['cam_global'],
                "observation.images.camera_wrist": frame_data['cam_wrist'],
            }

            # 添加帧到数据集
            dataset.add_frame(frame)

        # 保存episode
        dataset.save_episode()
        logger.info(f"  Episode {ep_idx + 1} 已保存")

    # 完成数据集创建
    logger.info("正在完成数据集...")
    dataset.finalize()

    logger.info(f"\n{'='*70}")
    logger.info(f"转换完成！")
    logger.info(f"{'='*70}")
    logger.info(f"数据集保存至: {dataset.root}")
    logger.info(f"总Episodes: {len(episodes)}")
    logger.info(f"总有效帧数: {sum(len(ep) for ep in episodes)}")
    logger.info(f"训练命令: lerobot-train --policy=act --dataset.repo_id={repo_id}")
    logger.info(f"{'='*70}\n")


def batch_convert(
    input_dir: str,
    base_repo_id: str,
    output_dir: Optional[str],
    **kwargs
):
    """
    批量转换多个experiment文件夹

    Args:
        input_dir: 包含多个experiment文件夹的根目录
        base_repo_id: 基础repo ID，会为每个experiment添加后缀
        output_dir: 输出目录
        **kwargs: 其他转换参数
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # 查找所有experiment文件夹
    experiment_dirs = sorted([d for d in input_path.iterdir()
                             if d.is_dir() and d.name.startswith('experiment_')])

    if len(experiment_dirs) == 0:
        logger.error(f"未找到任何experiment文件夹在: {input_dir}")
        return

    logger.info(f"\n{'='*70}")
    logger.info(f"批量转换模式")
    logger.info(f"{'='*70}")
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"找到 {len(experiment_dirs)} 个experiment文件夹")
    logger.info(f"{'='*70}\n")

    success_count = 0
    failed_count = 0

    for exp_dir in experiment_dirs:
        exp_name = exp_dir.name
        repo_id = f"{base_repo_id}_{exp_name}" if base_repo_id else exp_name

        logger.info(f"\n{'#'*70}")
        logger.info(f"处理: {exp_name}")
        logger.info(f"Repo ID: {repo_id}")
        logger.info(f"{'#'*70}\n")

        try:
            convert_to_lerobot(
                bag_path=str(exp_dir),
                repo_id=repo_id,
                output_dir=output_dir,
                **kwargs
            )
            success_count += 1
        except Exception as e:
            logger.error(f"\n❌ 转换失败: {exp_name}")
            logger.error(f"错误: {e}")
            import traceback
            traceback.print_exc()
            failed_count += 1

    # 打印总结
    logger.info(f"\n{'='*70}")
    logger.info(f"批量转换完成")
    logger.info(f"{'='*70}")
    logger.info(f"✓ 成功: {success_count}")
    logger.info(f"✗ 失败: {failed_count}")
    logger.info(f"总计: {success_count + failed_count}")
    logger.info(f"{'='*70}\n")


def main():
    args = parse_args()

    # 更新全局配置
    global MAX_SYNC_DELTA
    MAX_SYNC_DELTA = args.max_sync_delta

    # 检查是批量模式还是单个转换模式
    if args.input_dir:
        # 批量转换模式
        if not args.repo_id:
            logger.error("批量模式需要指定 --repo-id 作为基础repo ID")
            return

        batch_convert(
            input_dir=args.input_dir,
            base_repo_id=args.repo_id,
            output_dir=args.output_dir,
            fps=args.fps,
            robot_type=args.robot_type,
            state_topic=args.state_topic,
            action_topic=args.action_topic,
            cam_global_topic=args.cam_global_topic,
            cam_wrist_topic=args.cam_wrist_topic,
            state_dim=args.state_dim,
            action_dim=args.action_dim,
            task_name=args.task_name,
            max_sync_delta=args.max_sync_delta,
            episode_split_threshold=args.episode_split_threshold,
        )
    elif args.bag_path:
        # 单个转换模式
        if not args.repo_id:
            logger.error("单个转换模式需要指定 --repo-id")
            return

        convert_to_lerobot(
            bag_path=args.bag_path,
            repo_id=args.repo_id,
            fps=args.fps,
            robot_type=args.robot_type,
            state_topic=args.state_topic,
            action_topic=args.action_topic,
            cam_global_topic=args.cam_global_topic,
            cam_wrist_topic=args.cam_wrist_topic,
            state_dim=args.state_dim,
            action_dim=args.action_dim,
            task_name=args.task_name,
            output_dir=args.output_dir,
            max_sync_delta=args.max_sync_delta,
            episode_split_threshold=args.episode_split_threshold,
        )
    else:
        logger.error("请指定 --bag-path (单个转换) 或 --input-dir (批量转换)")
        return


if __name__ == "__main__":
    main()
