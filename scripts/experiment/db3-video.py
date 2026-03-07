#!/usr/bin/env python3
"""
从 ROS2 bag 文件提取相机图像并生成视频
"""
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import get_typestore, Stores
from datetime import datetime

# ================= 配置区域 =================
# 1. rosbag 文件夹路径（自动查找最新的实验数据）
# 如果要指定特定实验，修改这里：
EXPERIMENT_NAME = None  # None = 自动使用最新的，或者指定如 "experiment_20260228_212001"

# 2. 数据目录配置
EXPERIMENTS_DIR = "/media/ilex/Cyan_data/data/VIST/VIST_0304_10group_round_2_data"  # 实验数据目录
OUTPUT_DIR = "/media/ilex/Cyan_data/data/VIST/VIST_0304_10group_round_2_video"      # 输出目录

# 3. 相机图像的话题名称（支持多个相机）
CAMERA_TOPICS = {
    'camera_d435i': '/camera_d435i/color/image_raw',
    'camera_d405': '/camera_d405/color/image_raw'
}

# 4. 输出设置
SAVE_IMAGES = False                      # 是否保存单张图片（会在 OUTPUT_DIR/frames/ 下）
SAVE_VIDEO = True                       # 是否保存视频
VIDEO_FPS = 30                          # 生成视频的帧率

# ============================================

def find_latest_experiment():
    """查找最新的实验数据文件夹"""
    if not os.path.exists(EXPERIMENTS_DIR):
        return None

    experiments = [d for d in os.listdir(EXPERIMENTS_DIR)
                   if os.path.isdir(os.path.join(EXPERIMENTS_DIR, d))]

    if not experiments:
        return None

    # 按时间排序，返回最新的
    experiments.sort(reverse=True)
    return os.path.join(EXPERIMENTS_DIR, experiments[0])


def process_camera(bag_path, camera_name, topic_name, experiment_name, timestamp):
    """处理单个相机的数据"""
    # 生成该相机的输出路径
    output_video = os.path.join(OUTPUT_DIR, f'{experiment_name}_{camera_name}_{timestamp}.mp4')
    frames_dir = os.path.join(OUTPUT_DIR, f'{experiment_name}_{camera_name}_frames_{timestamp}')

    if SAVE_IMAGES:
        os.makedirs(frames_dir, exist_ok=True)
        print(f"[{camera_name}] 图片保存目录: {frames_dir}")

    video_writer = None
    frame_count = 0

    try:
        # 创建类型存储（支持 ROS2 Humble）
        typestore = get_typestore(Stores.ROS2_HUMBLE)

        # 使用 AnyReader 读取 bag 包
        with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
            # 获取 bag 中所有的话题
            topics = [conn.topic for conn in reader.connections]

            if topic_name not in topics:
                print(f"[{camera_name}] 警告: 找不到话题 {topic_name}")
                return 0

            # 找到我们要读取的话题连接
            connections = [x for x in reader.connections if x.topic == topic_name]

            print(f"[{camera_name}] 开始提取图像数据...")
            print(f"[{camera_name}] 输出视频: {output_video}")

            # 逐条读取消息
            for connection, timestamp, rawdata in reader.messages(connections=connections):
                # 反序列化 ROS 消息
                msg = reader.deserialize(rawdata, connection.msgtype)

                # --- 将 ROS 图像格式转换为 OpenCV (NumPy) 格式 ---
                if connection.msgtype == 'sensor_msgs/msg/Image':
                    # 处理未压缩的原始图像
                    img_data = np.frombuffer(msg.data, dtype=np.uint8)
                    cv_image = img_data.reshape((msg.height, msg.width, -1))

                    # ROS默认通常是 rgb8，OpenCV使用 bgr8，需要转换颜色通道
                    if msg.encoding == 'rgb8':
                        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
                    elif msg.encoding == 'bgr8':
                        pass  # 已经是 BGR 格式
                    elif msg.encoding == 'mono8':
                        # 灰度图转为 BGR
                        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2BGR)

                elif connection.msgtype == 'sensor_msgs/msg/CompressedImage':
                    # 处理压缩图像 (jpeg/png)
                    img_data = np.frombuffer(msg.data, np.uint8)
                    cv_image = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
                else:
                    print(f"[{camera_name}] 不支持的消息类型: {connection.msgtype}")
                    continue

                height, width = cv_image.shape[:2]

                # --- 保存为单张图片 ---
                if SAVE_IMAGES:
                    img_name = os.path.join(frames_dir, f"{frame_count:06d}.jpg")
                    cv2.imwrite(img_name, cv_image)

                # --- 保存为视频文件 ---
                if SAVE_VIDEO:
                    if video_writer is None:
                        # 初始化视频写入器 (使用 mp4v 编码)
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        video_writer = cv2.VideoWriter(output_video, fourcc, VIDEO_FPS, (width, height))
                        print(f"[{camera_name}] 视频分辨率: {width}x{height}")

                    video_writer.write(cv_image)

                frame_count += 1
                if frame_count % 100 == 0:
                    print(f"[{camera_name}] 已处理 {frame_count} 帧...")

    except Exception as e:
        print(f"[{camera_name}] 错误: {e}")
        import traceback
        traceback.print_exc()
        return 0

    finally:
        # 释放视频写入器
        if video_writer is not None:
            video_writer.release()

    print(f"[{camera_name}] 提取完成！共提取 {frame_count} 帧")
    if SAVE_VIDEO and frame_count > 0:
        print(f"[{camera_name}] 视频已保存至: {output_video}")
    elif frame_count == 0:
        print(f"[{camera_name}] 警告: 没有提取到任何帧！")

    return frame_count


def main():
    # 确定 bag 路径
    if EXPERIMENT_NAME:
        experiment_dir = os.path.join(EXPERIMENTS_DIR, EXPERIMENT_NAME)
    else:
        experiment_dir = find_latest_experiment()

    if not experiment_dir or not os.path.exists(experiment_dir):
        print(f"错误: 找不到实验数据文件夹: {experiment_dir}")
        sys.exit(1)

    # rosbag 数据可能在 rosbag_data 子目录中
    rosbag_dir = os.path.join(experiment_dir, 'rosbag_data')
    if os.path.exists(rosbag_dir):
        bag_path = rosbag_dir
    else:
        bag_path = experiment_dir

    print(f"正在处理实验数据: {experiment_dir}")
    print(f"ROS bag 路径: {bag_path}")

    # 生成输出文件名（使用实验名称）
    experiment_name = os.path.basename(experiment_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"正在打开 Bag: {bag_path}")

    # 首先检查 bag 中包含哪些话题
    try:
        typestore = get_typestore(Stores.ROS2_HUMBLE)
        with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
            topics = [conn.topic for conn in reader.connections]
            print(f"Bag 中包含的话题有: {set(topics)}")
    except Exception as e:
        print(f"错误: 无法读取 bag 文件: {e}")
        return

    # 处理每个相机
    total_frames = 0
    for camera_name, topic_name in CAMERA_TOPICS.items():
        print(f"\n{'='*60}")
        print(f"开始处理相机: {camera_name}")
        print(f"话题: {topic_name}")
        print(f"{'='*60}")

        frame_count = process_camera(bag_path, camera_name, topic_name, experiment_name, timestamp)
        total_frames += frame_count

    print(f"\n{'='*60}")
    print(f"所有相机处理完成！")
    print(f"总共提取 {total_frames} 帧")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()